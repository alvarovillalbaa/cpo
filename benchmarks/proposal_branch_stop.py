"""Spend a second proposal-search window only on unresolved validation."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import expected_cost_proposal_replay as source
from benchmarks.case_difficulty_allocation import checked_file
from cpo import Observation, ProposalBatch, ProposalPair, Row, search
from cpo._contract import digest
from cpo.expected_qualification import certify_expected_qualification


ROOT = Path(__file__).resolve().parents[1]
PARENT = 'a340fc3fc1ea6757a691ad594a54a13f500adf2d22328db65707e48b9c1289e5'
FIRST = 72
LIMIT = 104
THRESHOLDS = (1, 2)
CONTROLS = (*source.continuous.GEPA, f'cpo-{FIRST}', f'cpo-{LIMIT}')
METHODS = (*CONTROLS, *(f'cpo-adaptive-{gain}' for gain in THRESHOLDS))


class _BudgetReached(Exception):
    pass


def staged_search(incumbent, train, validation, evaluate, offers, *, first_cap, total_cap, probe_size, seed,
                  minimum_gain):
    """Return a complete nominee and the union of both windows' paid replies."""
    ledger, reflections = {}, {}
    counters = Counter()
    opening = ProposalPair(*offers[:2])

    def observe(prompt, row):
        key = prompt, row.id
        if key in ledger:
            counters['cachedEvaluations'] += 1
        else:
            if len(ledger) >= total_cap:
                raise _BudgetReached
            ledger[key] = evaluate(prompt, row)
        return ledger[key]

    def run(cap):
        index = 2

        def propose(parent, feedback, history, width):
            nonlocal index
            request = (parent, index, width, tuple((row.id, item.passed) for row, item in feedback),
                       tuple((prompt, tuple(sorted(counts.items()))) for prompt, counts in history))
            if request not in reflections:
                batch = offers[index:index + width]
                reflections[request] = ProposalBatch(tuple(batch), exhausted=index + len(batch) == len(offers))
            index += len(reflections[request].prompts)
            return reflections[request]

        return search(incumbent, train, validation, observe, propose, metric_limit=cap, rounds=len(offers) // 2,
                      train_per_round=probe_size, seed=seed, adaptive=True, opening_pair=opening)

    first = run(first_cap)
    first_cost = len(ledger)
    gains = Counter()
    for row in validation:
        gains[row.family] += ledger[first.prompt, row.id].passed - ledger[incumbent, row.id].passed
    perfect = all(ledger[first.prompt, row.id].passed for row in validation)
    enough = sum(gains.values()) >= minimum_gain and min(gains.values()) >= 0
    chosen = first
    if perfect or enough:
        counters['earlyStops'] += 1
    else:
        counters['extensions'] += 1
        try:
            chosen = run(total_cap)
        except _BudgetReached:
            counters['firstNomineeRetainedAtCap'] += 1
        counters['extensionLookups'] += len(ledger) - first_cost
        counters['extensionNomineeChanges'] += chosen.prompt != first.prompt
    counters.update(searchLookups=len(ledger), reflections=len(reflections))
    return chosen.prompt, ledger, counters


def step(matrix, incumbent, layout, plan, margin):
    train, validation, qualification = ([Row(str(case), 'task') for case in layout[key]]
                                        for key in ('train', 'validation', 'qualify'))

    def evaluate(prompt, row):
        passed = matrix[int(prompt)][int(row.id)] == '1'
        return Observation(passed, {'correct': passed})

    nominee, ledger, counts = staged_search(
        incumbent, train, validation, evaluate, layout['alternatives'], first_cap=FIRST, total_cap=LIMIT,
        probe_size=plan['probeSize'], seed=layout['seed'], minimum_gain=margin,
    )
    selected, replies = incumbent, ()
    if nominee != incumbent:
        prior = tuple((sum(ledger[prompt, row.id].passed for row in validation), len(validation))
                      for prompt in (incumbent, nominee))
        result = certify_expected_qualification(
            incumbent, nominee, qualification, lambda prompt, row, _: evaluate(prompt, row).passed,
            validation_counts=prior, minimum_gain=plan['minimumQualificationGain'], seed=layout['seed'],
        )
        selected, replies = result.prompt, result.observations
    counts.update(expected=len(replies), promotions=int(selected != incumbent))
    record = (incumbent, nominee, selected,
              digest([(p, row, value.passed) for (p, row), value in ledger.items()]),
              [(reply.prompt, reply.row_id, reply.repeat, reply.passed) for reply in replies])
    return selected, counts, record


def prepare():
    old, phases = source.prepare()
    reference = checked_file('docs/expected-cost-proposal-replay-results-v1.json', PARENT)
    if reference['designSha256'] != digest(old):
        raise ValueError('The original proposal-cycle result differs from its design')
    paths = ('benchmarks/proposal_branch_stop.py', 'benchmarks/expected_cost_proposal_replay.py',
             'cpo/optimizer.py', 'cpo/expected_qualification.py')
    design = {'protocol': 'cpo-proposal-branch-stop-v1', 'sourceDesignSha256': digest(old), 'sourceReportSha256': PARENT,
              'firstCap': FIRST, 'combinedCap': LIMIT, 'stopMargins': THRESHOLDS, 'methods': METHODS,
              'scope': ('Stop after a complete validation gain with no family loss or replay with a larger allowance. '
                        'Charge every distinct lookup in either window, keep the first nominee if interrupted, '
                        'and qualify just one final nominee on the original independent rows.'),
              'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in paths}}
    return design, {phase: (plan, panels, reference['results'][phase]['panels'])
                    for phase, (plan, panels, _) in phases.items()}


def measure(plan, panels, references):
    total, subjects, results = {label: Counter() for label in METHODS}, {}, {}
    for panel in panels:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        name, held = f'{subject}/{model}', plan['holdoutCaseIDs'][subject]
        counters = {label: Counter() for label in METHODS}
        finals, journals = ({label: [] for label in METHODS} for _ in range(2))
        for seed in plan['seeds']:
            initial, layouts = source.continuous.schedule(len(matrix[0]), len(matrix), held, seed, plan)
            for label in source.continuous.GEPA:
                current, trace = initial, []
                for layout in layouts:
                    record = source.continuous.step(label, matrix, current, layout, plan)
                    counters[label].update({key: record[key] for key in ('searchLookups', 'qualificationLookups')})
                    counters[label]['promotions'] += current != record['selected']
                    current = record['selected']
                    trace.append(record)
                finals[label].append(int(current))
                journals[label].append(trace)
            for cap in (FIRST, LIMIT):
                label = f'cpo-{cap}'
                final, used, trace = source.proposal_episode(matrix, initial, layouts, {**plan, 'evaluationLookupLimit': cap})
                counters[label].update(used)
                finals[label].append(final)
                journals[label].append(trace)
            for margin in THRESHOLDS:
                label = f'cpo-adaptive-{margin}'
                current, trace = initial, []
                for layout in layouts:
                    current, used, record = step(matrix, current, layout, plan, margin)
                    counters[label].update(used)
                    trace.append(record)
                finals[label].append(int(current))
                journals[label].append(trace)

        by_subject = subjects.setdefault(subject, {label: [0] * len(held) for label in METHODS})
        panel_results = {}
        for label in METHODS:
            scores = [sum(matrix[prompt][case] == '1' for prompt in finals[label]) for case in held]
            counters[label]['holdoutPasses'] = sum(scores)
            qualifier = 'qualificationLookups' if label in source.continuous.GEPA else 'expected'
            counters[label]['paidLookups'] = counters[label]['searchLookups'] + counters[label][qualifier]
            point = {**counters[label], 'traceSha256': digest(journals[label])}
            if label in CONTROLS and point != references[name][label]:
                raise ValueError(f'Original budget control differs for {name}/{label}')
            for index, value in enumerate(scores):
                by_subject[label][index] += value
            total[label].update(counters[label])
            panel_results[label] = point
        results[name] = panel_results
    with patch.object(source, 'CAPS', ('adaptive-1', 'adaptive-2')):
        paired = source.paired_ranges(total, subjects)
    return {'panels': results, 'totals': total, 'pairedComparisons': paired}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, phases = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for plan, *_ in phases.values()):
        cli.error('Use pinned GEPA 0.1.4')
    result = {'design': design, 'designSha256': seal,
              'results': {phase: measure(*inputs) for phase, inputs in phases.items()}}
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
