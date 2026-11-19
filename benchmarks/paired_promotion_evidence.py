"""Compare a discordance-aware qualification gate with fixed exact gains."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from math import comb
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import independent_mmlu_cost_frontier as frontier
from benchmarks import paid_incumbent_credit as replication
from benchmarks import starting_prompt_margin as margin
from cpo import Row, fixed_pool_cycle
from cpo._contract import digest
from cpo.paired_qualification import QualificationDecision, QualificationObservation


ROOT = Path(__file__).resolve().parents[1]
PHASES = (*margin.PHASES, 'replication')
POLICIES = ('seeded', 'all-gain-two', 'paired-evidence', 'paired-win-ratio')


def evidence_passes(wins, losses):
    """Use an exact one-sided sign-test tail at most one quarter as the gate."""
    count = wins + losses
    return wins > losses and 4 * sum(comb(count, k) for k in range(wins, count + 1)) <= 1 << count


def win_ratio_passes(wins, losses):
    return wins > 0 and wins >= 2 * losses


def certify(incumbent, challenger, rows, qualify, *, accepts=evidence_passes, seed=None):
    """Stop only when all completions of the binary pairs agree on the decision."""
    rows = tuple(rows)
    if not rows or len({row.id for row in rows}) != len(rows) or len({row.family for row in rows}) != 1:
        raise ValueError('The replay gate needs distinct rows in one family')
    if incumbent == challenger:
        return QualificationDecision('rejected', incumbent, (), 0, 0)

    pairs = [[None, None] for _ in rows]
    observations = []
    prompts = incumbent, challenger
    if seed is None:
        order = [(index, side) for side in range(2) for index in range(len(rows))]
    else:
        # Use the original paired reader's shuffle so the first dispatch for
        # every row is the same even when the stopping rule differs.
        rng = Random(seed)
        order = []
        for index in range(len(rows)):
            sides = [0, 1]
            rng.shuffle(sides)
            order.extend((index, side) for side in sides)

    for index, side in order:
        prompt, row = prompts[side], rows[index]
        passed = qualify(prompt, row, 0)
        if type(passed) is not bool:
            raise ValueError('Qualification requires exact boolean replies')
        observations.append(QualificationObservation(prompt, row.id, 0, passed))
        pairs[index][side] = passed

        wins = losses = possible_wins = possible_losses = 0
        critical_loss = critical_open = False
        for candidate_row, (old, new) in zip(rows, pairs, strict=True):
            if old is not None and new is not None:
                wins += new and not old
                loss = old and not new
                losses += loss
                critical_loss |= loss and candidate_row.critical
            else:
                could_lose = old is not False and new is not True
                possible_wins += old is not True and new is not False
                possible_losses += could_lose
                critical_open |= could_lose and candidate_row.critical
        low, high = wins - losses - possible_losses, wins + possible_wins - losses
        if critical_loss or not accepts(wins + possible_wins, losses):
            return QualificationDecision('rejected', incumbent, tuple(observations), low, high)
        if not critical_open and accepts(wins, losses + possible_losses):
            return QualificationDecision('promoted', challenger, tuple(observations), low, high)
    raise RuntimeError('A complete paired evidence panel must give a decision')


def paired_episode(matrix, held, seed, original, settings, *, accepts):
    def fresh(incumbent, challenger, rows, qualify, *, repeats, minimum_gain, seed, evaluation_limit):
        if (repeats, minimum_gain, evaluation_limit) != (1, 1, None):
            raise ValueError('The replay expects a single uncapped qualification panel')
        return certify(incumbent, challenger, rows, qualify, accepts=accepts, seed=seed)

    def retry(incumbent, challenger, cohort, evaluate):
        rows = tuple(Row(str(case), 'task') for case in cohort)
        result = certify(incumbent, challenger, rows, lambda prompt, row, _: evaluate(prompt, int(row.id)),
                         accepts=accepts)
        evidence = [(reply.prompt, int(reply.row_id), reply.passed) for reply in result.observations]
        return result.status == 'promoted', sum(prompt == challenger for prompt, _, _ in evidence), evidence

    with (patch.object(fixed_pool_cycle, 'certify_paired_qualification', fresh),
          patch.object(archive.archive, 'qualify_archived', retry)):
        return archive.episode(matrix, held, seed, original, settings, 'recency')


def prepare(phase):
    if phase == 'replication':
        parent, original, data, measured = replication.prepare(phase)
        # Both models use the same case IDs. Derive the subject mapping from
        # the validated panel keys, preserving the archived row order.
        held = {name.split('/')[0]: row['holdoutCaseIDs'] for name, row in measured.items()}
        original = {**original, 'holdoutCaseIDs': held}
        known = {name: row['methods']['cpo-52'] for name, row in measured.items()}
        controls = {name: {key: row['methods'][key] for key in ('gepa-sequential-31', 'gepa-batched-44')}
                    for name, row in measured.items()}
    else:
        parent, original, data, controls, known = margin.prepare(phase)
    plan = {
        'protocol': 'cpo-paired-promotion-evidence-v1', 'phase': phase, 'parentPlanSha256': digest(parent),
        'referenceReportSha256': parent['referenceReportSha256'], 'gepaVersion': parent['gepaVersion'],
        'validationRows': parent['validationRows'], 'searchCap': 52, 'policies': list(POLICIES),
        'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in (
            'benchmarks/paired_promotion_evidence.py', 'benchmarks/starting_prompt_margin.py',
            'benchmarks/paid_incumbent_credit.py', 'benchmarks/archive_complementarity_transfer.py',
            'cpo/fixed_pool_cycle.py', 'cpo/paired_qualification.py')},
        'pairedGates': {
            'critical': 'Preserve every matched incumbent critical pass.',
            'paired-evidence': 'Require an exact one-sided sign-test tail at most 1/4 as a selection heuristic.',
            'paired-win-ratio': 'Require at least one paired win and at least twice as many wins as losses.',
        },
        'scope': ('Retrospective comparison of archived decisions at the original search cap. '
                  'Both archive and fresh qualification use the same gate. Final holdout never guides selection.'),
    }
    return plan, original, data, controls, known


def collect(matrix, held, original, plan, policy):
    totals, journals, passes = Counter(), [], []
    paired_gates = {'paired-evidence': evidence_passes, 'paired-win-ratio': win_ratio_passes}
    for seed in original['seeds']:
        if policy in paired_gates:
            count, trace = paired_episode(matrix, held, seed, original, plan, accepts=paired_gates[policy])
        else:
            count, trace, _ = margin.run_cpo(matrix, held, seed, original, plan, policy)
        totals.update(count)
        for row in trace:
            decision = row['decision']
            totals.update(freshNominations=int(not decision['archivePromoted'] and
                                               decision['challenger'] != decision['incumbent']),
                          promotions=int(decision['selected'] != decision['incumbent']))
        journals.append(trace)
        passes.append(count['holdoutPasses'])
    return dict(totals, paidLookups=totals['searchPaid'] + totals['qualificationPaid'],
                traceSha256=digest(journals)), passes


def replay(plan, original, data, controls, known):
    panels, totals = {}, {policy: Counter() for policy in POLICIES}
    for item in data:
        subject, model, matrix = (item[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        methods, changes, baseline = {}, {}, []
        for policy in POLICIES:
            point, passes = collect(matrix, held, original, plan, policy)
            methods[policy] = point
            if policy == 'seeded':
                frontier.expect_reference(point, known[name])
                baseline = passes
            else:
                delta = [new - old for old, new in zip(baseline, passes, strict=True)]
                changes[policy] = {'episodesGaining': sum(d > 0 for d in delta), 'episodesLosing': sum(d < 0 for d in delta),
                                   'grossGain': sum(max(d, 0) for d in delta), 'grossLoss': -sum(min(d, 0) for d in delta)}
        refs = {key: {field: row[field] for field in ('holdoutPasses', 'paidLookups')}
                for key, row in controls[name].items()}
        panels[name] = {'methods': methods, 'controls': refs, 'changesFromSeeded': changes}
        for key, row in {**methods, **refs}.items():
            totals.setdefault(key, Counter()).update({field: value for field, value in row.items() if type(value) is int})
    return {'plan': plan, 'planSha256': digest(plan), 'totals': totals, 'panels': panels}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--phase', choices=PHASES, required=True)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Execution requires the current seal and a fresh report path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
