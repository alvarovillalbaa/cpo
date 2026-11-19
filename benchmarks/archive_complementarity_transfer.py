"""Rank archive prompts using only earlier, already paid qualification replies."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import fixed_pool_cycle_replay as fixed
from benchmarks import gepa_paid_cap_transfer as controls
from benchmarks import prompteval_archive_cycles as archive
from benchmarks import prompteval_continuous as continuous
from benchmarks import prompteval_paid_witness as paid
from benchmarks import prompteval_validation_size as smaller
from cpo import Observation, Row
from cpo._contract import digest, unique_object
from cpo.fixed_pool_cycle import run_fixed_pool_cycle


ROOT = Path(__file__).resolve().parents[1]
PAID_CAP_SHA256 = '96dad2679ba03a45fc026c01900ea84c74f7211c68c3f835abfb827c26631bdb'
FIXED_POOL_SHA256 = '74923c70e1c69bbcf7603229b30512eb8b3a3607ef309398a4a8b920d4242905'
POLICIES = ('recency', 'paired-wins', 'require-win', 'archive-disabled')
CPO = controls.CPO


def nominate_complement(incumbent, history, attempted, evidence, *, require_win):
    """Rank the original eligible archive by observed paired gains."""
    eligible = []
    for previous in reversed(history):
        prompt = (previous['incumbent'] if previous['incumbent'] != previous['selected']
                  else previous['challenger'])
        if prompt is not None and prompt != incumbent and (incumbent, prompt) not in attempted:
            if prompt not in eligible:
                eligible.append(prompt)
    current = evidence.get(incumbent, {})
    ranked = []
    for prompt in eligible:
        challenger = evidence.get(prompt, {})
        shared = current.keys() & challenger.keys()
        wins = sum(challenger[case] and not current[case] for case in shared)
        if wins or not require_win:
            losses = sum(current[case] and not challenger[case] for case in shared)
            denominator = 2 + len(shared)
            ranked.append((prompt, Fraction(wins, denominator), Fraction(wins - losses, denominator)))
    first = max(ranked, key=lambda item: item[1:], default=None)
    return first[0] if first is not None else None


def episode(matrix, held, seed, original, plan, policy):
    incumbent, layouts = smaller.narrow_schedule(
        *continuous.schedule(len(matrix[0]), len(matrix), held, seed, original), plan['validationRows'])
    history, attempted, cache, evidence = [], set(), {}, {}
    totals = Counter(searchLogical=0, searchPaid=0, qualificationPaid=0, archiveAttempts=0,
                     archivePromotions=0, changedNomination=0, skippedRecencyNominee=0)
    journals = []
    for layout in layouts:
        recent = archive.nominate(incumbent, history, attempted, 'runner-up')
        if policy == 'archive-disabled':
            nominee = None
        elif policy == 'recency':
            nominee = recent
        else:
            nominee = nominate_complement(incumbent, history, attempted, evidence, require_win=policy == 'require-win')
        candidates, qualification_rows = layout['alternatives'], layout['qualify']
        allowed_search = {incumbent, *candidates}
        allowed_qualification = allowed_search | {nominee}
        charged_search, charged_qualification, requested = {}, {}, []
        old_cache_size = len(cache)
        archive_promoted, reserved = False, 0

        def qualify(prompt, case):
            if prompt not in allowed_qualification or case not in qualification_rows:
                raise ValueError('Qualification left the sealed prompt roster or case set')
            key = (prompt, case)
            if key not in charged_qualification:
                charged_qualification[key] = matrix[int(prompt)][case] == '1'
            return charged_qualification[key]

        def qualify_fresh(prompt, row, repeat):
            if repeat != 0:
                raise ValueError('The transfer uses one qualification repeat')
            reply = qualify(prompt, int(row.id))
            requested.append((prompt, row.id, repeat, reply))
            return reply

        def evaluate(prompt, row):
            case = int(row.id)
            key = (prompt, case)
            if case not in layout['validation'] or prompt not in allowed_search:
                raise ValueError('Validation left the sealed prompt roster or case set')
            if key not in cache:
                cache[key] = matrix[int(prompt)][case] == '1'
            charged_search[key] = cache[key]
            return Observation(cache[key], {'correct': cache[key]})

        if nominee is not None:
            attempted.add((incumbent, nominee))
            archive_promoted, reserved, _ = archive.qualify_archived(
                incumbent, nominee, qualification_rows, qualify)
        if archive_promoted:
            challenger = selected = nominee
        else:
            validation = [Row(str(case), 'task') for case in layout['validation']]
            qual_rows = [Row(str(case), 'task') for case in qualification_rows]
            result = run_fixed_pool_cycle(incumbent, candidates, validation, qual_rows, evaluate,
                                          metric_limit=plan['searchCap'] - reserved,
                                          qualify=qualify_fresh, seed=layout['seed'])
            challenger, selected = result.search.prompt, result.prompt
            if (result.search.evaluations != len(charged_search) or
                    result.qualification_evaluations != len(requested) or
                    (result.qualification is not None and result.qualification.status == 'undecided')):
                raise ValueError('The accounted lookup costs differ from the public cycle')
        if len(charged_search) + len(charged_qualification) > plan['searchCap'] + 2 * len(qualification_rows):
            raise ValueError('The original combined ceiling was exceeded')
        totals.update(searchLogical=len(charged_search), searchPaid=len(cache) - old_cache_size,
                      qualificationPaid=len(charged_qualification), archiveAttempts=int(nominee is not None),
                      archivePromotions=int(archive_promoted), changedNomination=int(nominee != recent),
                      skippedRecencyNominee=int(recent is not None and nominee is None))
        step = {'incumbent': incumbent, 'challenger': challenger, 'selected': selected,
                'archiveNominee': nominee, 'archivePromoted': archive_promoted, 'searchSha256': digest(
                    [(prompt, case, outcome) for (prompt, case), outcome in charged_search.items()])}
        journals.append({'decision': step, 'observedQualification': requested,
                         'paidQualification': len(charged_qualification)})
        for (prompt, case), passed in charged_qualification.items():
            rows = evidence.setdefault(prompt, {})
            if case in rows:
                raise ValueError('Qualification rows may not recur within an episode')
            rows[case] = passed
        history.append(step)
        incumbent = selected
    totals['holdoutPasses'] = sum(matrix[int(incumbent)][case] == '1' for case in held)
    return totals, journals


def checked_report(name, expected, phase):
    raw = (ROOT / 'docs' / name).read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError('An archived report differs from its verified source')
    return json.loads(raw, object_pairs_hook=unique_object)['runs'][phase]['report']


def prepare(phase):
    gepa = checked_report('gepa-paid-cap-transfer-results-v1.json', PAID_CAP_SHA256, phase)
    prior = checked_report('fixed-pool-cycle-replay-results-v1.json', FIXED_POOL_SHA256, phase)
    parent, original, data, _, _ = controls.prepare(phase)
    fixed_plan, *_ = fixed.prepare(phase)
    if digest(parent) != gepa['planSha256'] or digest(fixed_plan) != prior['planSha256']:
        raise ValueError('A baseline plan differs from the published replay')
    plan = {
        'protocol': 'cpo-archive-complementarity-transfer-v1', 'phase': phase,
        'parentPlanSha256': digest(parent), 'gepaReportSha256': PAID_CAP_SHA256,
        'fixedPoolReportSha256': FIXED_POOL_SHA256, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'gepaVersion': parent['gepaVersion'], 'searchCap': parent['searchCap'],
        'validationRows': parent['validationRows'], 'policies': list(POLICIES), 'primary': 'paired-wins',
        'exploratoryControl': 'archive-disabled',
        'gate': parent['gate'], 'scope': 'Rank the same archive using only earlier actual paired qualification replies.',
    }
    return plan, original, data, gepa['panels'], prior['panels']


def replay(plan, original, data, gepa, prior):
    results = {}
    for panel in data:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        methods = {}
        for policy in POLICIES:
            total, traces = Counter(), []
            for seed in original['seeds']:
                measured, trace = episode(matrix, held, seed, original, plan, policy)
                total.update(measured)
                traces.append(trace)
            methods[policy] = {**total, 'paidLookups': total['searchPaid'] + total['qualificationPaid'],
                               'callbackTraceSha256': digest(traces)}
        previous = prior[name][CPO]
        current = methods['recency']
        if (current['callbackTraceSha256'] != previous['callbackTraceSha256'] or
                current['holdoutPasses'] != previous['totals']['holdoutPasses'] or
                current['paidLookups'] != previous['totals']['paidLookups']):
            raise ValueError('The recency control differs from the published fixed-pool trace')
        matched = gepa[name]['reinvested']
        results[name] = {
            'policies': methods, 'gepa': {m: {k: x[k] for k in ('holdoutPasses', 'paidLookups')}
                                         for m, x in matched.items()},
            'gates': {policy: {m: paid.meets_gate(totals, stats) for m, stats in matched.items()}
                      for policy, totals in methods.items()},
        }
    qualified = {p: [name for name, row in results.items() if all(row['gates'][p].values())] for p in POLICIES}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': results, 'panelsClearingBothGates': qualified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=controls.reference.transfer.SOURCES, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current phase seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
