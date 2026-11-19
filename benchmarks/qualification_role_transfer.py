"""Attribute short-panel losses and test shortening just one qualification role."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import four_case_qualification_transfer as transfer
from benchmarks import gepa_paid_cap_transfer as gepa
from benchmarks import independent_mmlu_cost_frontier as frontier
from benchmarks import qualification_repeat_sensitivity as earlier
from benchmarks import starting_prompt_margin as margins
from benchmarks.independent_mmlu_transfer import read_json
from benchmarks.prompteval_transfer import holdout
from cpo import Row, fixed_pool_cycle
from cpo._contract import digest
from cpo.paired_qualification import QualificationDecision, QualificationObservation


ROOT = Path(__file__).resolve().parents[1]
PHASES = ('development', 'replication', 'transfer')
MODES = ('eight', 'four', 'short-fresh', 'short-archive', 'short-retired', 'short-rejected', 'extend-ties')
TRANSFER_SHA256 = '4373085f2d598b2c17407bfa5f3718690f99a9e302248f9d01aad7e70991325e'
SCORE_FIELDS = ('holdoutPasses', 'paidLookups')
GEPA = {'gepaBatched': True, 'gepaSequential': False}
FRESH = fixed_pool_cycle.certify_paired_qualification
RETRY = archive.archive.qualify_archived


def retry_width(mode, retired):
    return 4 if (mode in ('four', 'short-archive') or (mode == 'short-retired' and retired) or
                 (mode == 'short-rejected' and not retired)) else 8


def qualify_ties(incumbent, challenger, rows, qualify, *, seed=None):
    """Resolve the initial panel's sign, then read the second panel only on a tie."""
    rows = tuple(rows)
    if len(rows) != 8 or len({row.id for row in rows}) != 8 or len({row.family for row in rows}) != 1 or any(
            row.critical for row in rows):
        raise ValueError('Tie extension requires eight distinct, unlabelled cases from one family')
    if incumbent == challenger:
        return QualificationDecision('rejected', incumbent, (), 0, 0), False
    prompts = incumbent, challenger
    evidence = []
    rng = Random(seed)

    for extended, panel in enumerate((rows[:4], rows[4:])):
        low, high = -len(panel), len(panel)
        if seed is None:
            orders = [(side, row) for side in range(2) for row in panel]
        else:
            orders = []
            for row in panel:
                sides = [0, 1]
                rng.shuffle(sides)
                orders.extend((side, row) for side in sides)
        for side, row in orders:
            prompt = prompts[side]
            passed = qualify(prompt, row, 0)
            if type(passed) is not bool:
                raise ValueError('Qualification requires exact boolean replies')
            evidence.append(QualificationObservation(prompt, row.id, 0, passed))
            if passed == bool(side):
                low += 1
            else:
                high -= 1
            if low > 0:
                return QualificationDecision('promoted', challenger, tuple(evidence), low, high), bool(extended)
            if high < 0 or (extended and high == 0):
                return QualificationDecision('rejected', incumbent, tuple(evidence), low, high), bool(extended)
    raise RuntimeError('A fully observed extension must produce a decision')


def run(matrix, held, seed, original, plan, mode):
    incumbents = set()
    usage = Counter(freshShortPanels=0, archiveShortPanels=0, archiveRetiredNominees=0,
                    freshTieExtensions=0, archiveTieExtensions=0)

    def cycle(incumbent, *args, **kwargs):
        incumbents.add(incumbent)
        return fixed_pool_cycle.run_fixed_pool_cycle(incumbent, *args, **kwargs)

    def fresh(incumbent, challenger, rows, qualify, *, repeats, minimum_gain, seed, evaluation_limit):
        if mode == 'extend-ties':
            if (repeats, minimum_gain, evaluation_limit) != (1, 1, None):
                raise ValueError('Tie extension expects one uncapped qualification repeat')
            decision, extended = qualify_ties(incumbent, challenger, rows, qualify, seed=seed)
            usage.update(freshTieExtensions=int(extended))
            return decision
        width = 4 if mode in ('four', 'short-fresh') else 8
        usage.update(freshShortPanels=int(width == 4))
        return FRESH(incumbent, challenger, rows[:width], qualify, repeats=repeats, minimum_gain=minimum_gain,
                     seed=seed, evaluation_limit=evaluation_limit)

    def retry(incumbent, nominee, cohort, qualify):
        incumbents.add(incumbent)
        retired = nominee in incumbents
        usage.update(archiveRetiredNominees=int(retired))
        if mode == 'extend-ties':
            rows = [Row(str(case), 'task') for case in cohort]
            decision, extended = qualify_ties(incumbent, nominee, rows, lambda p, r, _: qualify(p, int(r.id)))
            usage.update(archiveTieExtensions=int(extended))
            observed = [(row.prompt, int(row.row_id), row.passed) for row in decision.observations]
            return decision.status == 'promoted', sum(prompt == nominee for prompt, _, _ in observed), observed
        width = retry_width(mode, retired)
        usage.update(archiveShortPanels=int(width == 4))
        return RETRY(incumbent, nominee, cohort[:width], qualify)

    with (patch.object(archive, 'run_fixed_pool_cycle', cycle),
          patch.object(fixed_pool_cycle, 'certify_paired_qualification', fresh),
          patch.object(archive.archive, 'qualify_archived', retry)):
        total, journal = archive.episode(matrix, held, seed, original, plan, 'recency')
    total.update(usage)
    return total, journal


def first_divergence(matrix, short, full, layouts):
    for left, right, layout in zip(short, full, layouts, strict=True):
        a, b = left['decision'], right['decision']
        incumbent = a['incumbent']
        if incumbent != b['incumbent'] or a['archiveNominee'] != b['archiveNominee']:
            raise ValueError('The matched prefix already diverged before this qualification')
        if a['archivePromoted'] != b['archivePromoted']:
            role, candidate = 'archive', a['archiveNominee']
            direction = 'four-only' if a['archivePromoted'] else 'eight-only'
        elif a['challenger'] != b['challenger']:
            return {'kind': 'search-nomination'}
        elif a['selected'] != b['selected']:
            role, candidate = 'fresh', a['challenger']
            direction = 'four-only' if a['selected'] != incumbent else 'eight-only'
        else:
            continue
        old, new = matrix[int(incumbent)], matrix[int(candidate)]
        margins = [int(new[row]) - int(old[row]) for row in layout['qualify']]
        prefix, full_panel = sum(margins[:4]), sum(margins)
        if (prefix > 0, full_panel > 0) != (direction == 'four-only', direction == 'eight-only'):
            raise ValueError('The first changed qualification decision differs from the complete archived scores')
        return {'kind': f'{role}-{direction}', 'fourCaseGain': prefix, 'eightCaseGain': full_panel}
    return {'kind': 'same-decisions'}


def prepare(phase):
    if phase == 'transfer':
        original_plan = transfer.design()
        corpus = (ROOT / 'benchmarks/data/four-case-qualification-transfer-v1.json').read_bytes()
        past = (ROOT / 'docs/four-case-qualification-transfer-results-v1.json').read_bytes()
        report = read_json(past)
        if (sha256(past).hexdigest() != TRANSFER_SHA256 or report['planSha256'] != digest(original_plan)
                or report['corpusSha256'] != sha256(corpus).hexdigest()):
            raise ValueError('The prospective report or captured corpus differs')
        data = read_json(corpus)['panels']
        reference = {name: {'four': row['methods']['cpo-four-52'], 'eight': row['methods']['cpo-eight-52'],
                            'gepaBatched': row['methods']['gepa-batched-eight-52'],
                            'gepaSequential': row['methods']['gepa-sequential-eight-52']}
                     for name, row in report['panels'].items()}
        original, parent_sha = original_plan['schedule'], TRANSFER_SHA256
    else:
        original_plan, original, data, _ = earlier.prepare(phase)
        past = (ROOT / 'docs/qualification-repeat-sensitivity-results-v1.json').read_bytes()
        parent_sha = transfer.REFERENCE_SHA256
        report = read_json(past)[phase]
        if sha256(past).hexdigest() != parent_sha or report['planSha256'] != digest(original_plan):
            raise ValueError('The retrospective report differs')
        reference = {name: {'four': row['0']['cpo/four-cases'], 'eight': row['0']['cpo/eight-cases'],
                            'gepaBatched': row['0']['gepa-batched/eight-cases']}
                     for name, row in report['panels'].items()}
    plan = {
        'protocol': 'cpo-qualification-role-transfer-v1', 'phase': phase, 'policies': list(MODES),
        'parentPlanSha256': digest(original_plan), 'parentReportSha256': parent_sha, 'searchCap': 52,
        'validationRows': original_plan['validationRows'], 'gepaVersion': original_plan['gepaVersion'],
        'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in (
            'benchmarks/qualification_role_transfer.py', 'benchmarks/archive_complementarity_transfer.py',
            'benchmarks/prompteval_archive_cycles.py', 'benchmarks/starting_prompt_margin.py',
            'benchmarks/gepa_paid_cap_transfer.py', 'cpo/fixed_pool_cycle.py', 'cpo/paired_qualification.py')},
        'scope': ('Measure only previously archived outcomes. Attribute the first different decision between '
                  'four and eight cases, then vary the qualification role or extend the four-case panel on ties. '
                  'Archive nominees count as retired only after serving as an incumbent in this episode.'),
    }
    return plan, original, data, reference


def audit_gepa_losses(matrix, held, original, plan, baseline_journals, reference):
    """Replay both real GEPA controls and diagnose lost episodes after selection."""
    counts, traces, losses = {label: Counter() for label in GEPA}, {label: [] for label in GEPA}, []
    for seed, baseline in zip(original['seeds'], baseline_journals, strict=True):
        cpo, journal, state = margins.run_cpo(matrix, held, seed, original, plan, 'seeded')
        if journal != baseline:
            raise ValueError('The diagnostic CPO rerun must reproduce every archived decision')
        for label, batched in GEPA.items():
            final, measured, peak, trace = gepa.reinvest_episode(matrix, held, seed, original, plan, batched=batched)
            if peak > plan['searchCap']:
                raise ValueError('The diagnostic GEPA rerun exceeded its source paid cap')
            traces[label].append(trace)
            counts[label].update(measured)
            deficit = measured['holdoutPasses'] - cpo['holdoutPasses']
            if deficit > 0:
                losses.append({'seed': seed, 'control': label, 'passDeficit': deficit,
                               **margins.attribute_loss(matrix, held, state, final)})
    for label, measured in counts.items():
        point = dict(measured, paidLookups=measured['searchPaid'] + measured['qualificationPaid'],
                     traceSha256=digest(traces[label]))
        frontier.expect_reference(point, reference[label])
    return losses


def replay(plan, original, data, reference):
    panels, aggregate, changes = {}, {}, {}
    for item in data:
        subject, model, matrix = (item[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = holdout(subject, len(matrix[0]))
        totals = {mode: Counter() for mode in MODES}
        journals = {mode: [] for mode in MODES}
        audit = []
        for seed in original['seeds']:
            _, schedule = archive.continuous.schedule(len(matrix[0]), len(matrix), held, seed, original)
            paths = {}
            for mode in MODES:
                count, trace = run(matrix, held, seed, original, plan, mode)
                totals[mode].update(count)
                journals[mode].append(trace)
                paths[mode] = count, trace
            short, short_trace = paths['four']
            full, full_trace = paths['eight']
            result = first_divergence(matrix, short_trace, full_trace, schedule)
            difference = short['holdoutPasses'] - full['holdoutPasses']
            paid_difference = short['searchPaid'] + short['qualificationPaid'] - full['searchPaid'] - full['qualificationPaid']
            if result['kind'] == 'same-decisions' and difference:
                raise ValueError('Identical choices must have the same holdout score')
            changes.setdefault(result['kind'], Counter()).update(episodes=1, gainedPasses=max(0, difference),
                                                                 lostPasses=max(0, -difference), lookupDelta=paid_difference)
            audit.append(dict(result, seed=seed, passDelta=difference, lookupDelta=paid_difference))
        points = {mode: dict(count, paidLookups=count['searchPaid'] + count['qualificationPaid'],
                             traceSha256=digest(journals[mode])) for mode, count in totals.items()}
        for mode in ('four', 'eight'):
            frontier.expect_reference(points[mode], reference[name][mode])
        for key, ref in reference[name].items():
            if key.startswith('gepa'):
                points[key] = {field: ref[field] for field in SCORE_FIELDS}
        for label, point in points.items():
            aggregate.setdefault(label, Counter()).update({field: point[field] for field in SCORE_FIELDS})
        panels[name] = {'methods': points, 'firstDivergences': audit}
        if plan['phase'] == 'transfer':
            panels[name]['eightCaseCpoLosses'] = audit_gepa_losses(matrix, held, original, plan, journals['eight'],
                                                                  reference[name])
    return {'plan': plan, 'planSha256': digest(plan), 'totals': aggregate, 'panels': panels, 'attribution': changes}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--phase', choices=PHASES, required=True)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Execution requires the current seal and a fresh report path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
