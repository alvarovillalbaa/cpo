"""Retry one finalist with the unspent portion of the original narrow search cap."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import family_qualification_order as parent
from benchmarks import routed_score_allocation as route
from cpo._contract import digest
from cpo.lazy_incumbent import select_with_lazy_incumbent
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPORT = 'b8edacf20885c09bc79b4aa40841ad0cfa4dd0e527e7df1bca3677f4bce798d8'
POLICIES = ('same-witness', 'shared-miss')
METHODS = (*parent.METHODS, *POLICIES)


def retry_finalist(incumbent, candidates, rows, evaluate, *, metric_limit, alternate, audit):
    """Resume the untouched suffix after an exact first-finalist rejection."""
    rows, candidates = tuple(rows), tuple(candidates)
    ledger = {}
    first_witness = None

    def observe(prompt, row):
        nonlocal first_witness
        key = prompt, row.id
        if key not in ledger:
            if len(ledger) >= metric_limit:
                raise ValueError('The finalist retry cannot exceed the original cap')
            ledger[key] = evaluate(prompt, row)
            if prompt != incumbent and first_witness is None:
                first_witness = row.id
        return ledger[key]

    first = select_with_lazy_incumbent(incumbent, candidates, rows, observe, metric_limit=metric_limit)
    if first.prompt != incumbent or first.finalist is None:
        return first

    audit['firstFinalistRejections'] += 1
    suffix = candidates[candidates.index(first.finalist) + 1:]
    # The selector still reserves two full panels. Credit only the already
    # observed incumbent replies that a second proof can reuse.
    credit = sum((incumbent, row.id) in ledger for row in rows)
    before = len(ledger)
    allowance = metric_limit - before + credit
    if not suffix or allowance < 2 * len(rows):
        return first
    if alternate:
        witness = next((row for row in rows if row.id != first_witness
                        and (incumbent, row.id) in ledger and not ledger[incumbent, row.id].passed
                        and (first.finalist, row.id) in ledger and not ledger[first.finalist, row.id].passed), None)
        if witness is not None:
            rows = (witness, *(row for row in rows if row.id != witness.id))
            audit['sharedMissScreens'] += 1
    second = select_with_lazy_incumbent(incumbent, suffix, rows, observe, metric_limit=allowance)
    audit.update(retryScreens=1, retryLookups=len(ledger) - before,
                 secondFinalists=int(second.finalist is not None), validationRescues=int(second.prompt != incumbent))
    finalist = second.finalist if second.finalist is not None else first.finalist
    return FinalistResult(second.prompt, finalist, len(ledger))


def episode(matrix, held, seed, plan, start, label):
    if label not in POLICIES:
        return parent.run(matrix, held, seed, plan, start, label, ordered=False)
    audit = Counter()

    def search(incumbent, candidates, rows, evaluate, *, metric_limit):
        return retry_finalist(incumbent, candidates, rows, evaluate, metric_limit=metric_limit,
                              alternate=label == 'shared-miss', audit=audit)

    with patch.object(route.ties.split, 'select_with_lazy_incumbent', search):
        counts, trace = route.run(matrix, held, seed, plan, start, 'strict')
    counts.update(audit)
    return counts, trace


def prepare():
    frozen, panels = parent.prepare()
    report = parent.parent.checked_file('docs/family-qualification-order-results-v1.json', SOURCE_REPORT)
    if report['designSha256'] != digest(frozen):
        raise ValueError('The published qualification replay has a different seal')
    inputs = {name: (items, plan, report['results'][name]['panels'])
              for name, (items, _, plan) in panels.items()}
    sources = ('benchmarks/funded_finalist_retry.py', 'benchmarks/family_qualification_order.py',
               'benchmarks/routed_witness_split.py', 'cpo/lazy_incumbent.py', 'cpo/challenger.py')
    design = {'protocol': 'cpo-funded-finalist-retry-v1', 'sourceDesignSha256': digest(frozen),
              'sourceReportSha256': SOURCE_REPORT, 'methods': METHODS, 'primary': POLICIES[1],
              'limit': 'The existing per-cycle search cap, with a full reserve for the second proof',
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in sources}}
    return design, inputs


def measure(panels, plan, references):
    totals = {label: Counter() for label in METHODS}
    details, holdouts = {}, {}
    margins = {policy: {} for policy in POLICIES}
    uncertainty = route.CONFIRMATION.uncertainty
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = route.CONFIRMATION.holdout(subject, len(matrix[0]))
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('Both models must share the same ordered holdout cases')
        starts = route.ties.costs.retained_prompts(matrix, held, plan['schedule'])
        counts = {label: Counter() for label in METHODS}
        traces, finals = ({label: [] for label in METHODS} for _ in range(2))
        for seed, start in zip(plan['schedule']['seeds'], starts, strict=True):
            for label in METHODS:
                used, trace = episode(matrix, held, seed, plan, str(start), label)
                counts[label].update(used)
                traces[label].append(trace)
                finals[label].append(int(trace[-1]['decision']['selected'] if label in ('strict', *POLICIES)
                                         else trace[-1]['selected']))
                if label in POLICIES:
                    delta = used['holdoutPasses'] - baseline
                    counts[label].update(changedFinal=int(finals[label][-1] != finals['strict'][-1]),
                                         improved=int(delta > 0), regressed=int(delta < 0))
                if label == 'strict':
                    baseline = used['holdoutPasses']
        points = {label: {**used, 'paidLookups': used['searchPaid'] + used['qualificationPaid'],
                          'traceSha256': digest(traces[label])} for label, used in counts.items()}
        outcomes = {label: uncertainty.case_totals(matrix, held, prompts) for label, prompts in finals.items()}
        for label, point in points.items():
            if label in parent.METHODS:
                route.ties.frontier.expect_reference(point, references[name][label]['original'])
            if sum(outcomes[label].values()) != point['holdoutPasses']:
                raise ValueError('The paired holdout measurements disagree with the replay')
            totals[label].update({key: value for key, value in point.items() if type(value) is int})
        for policy, groups in margins.items():
            paired = groups.setdefault(subject, {label: [0] * len(held) for label in parent.METHODS})
            for label, gaps in paired.items():
                for index, case in enumerate(held):
                    gaps[index] += outcomes[policy][case] - outcomes[label][case]
        details[name] = points

    comparisons = {}
    for policy, groups in margins.items():
        interval = route.transfer.ranges(groups, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
        cost = totals[policy]['paidLookups']
        savings = {label: 1 - cost / totals[label]['paidLookups'] for label in route.PRIMARY}
        funded = all(cost * 100 <= totals[label]['paidLookups'] * (100 - plan['minimumLookupSavingPercent'])
                     for label in route.PRIMARY)
        low, high = interval['joint']
        gate = 'failed' if not funded or high < 0 else 'passed' if low >= 0 else 'inconclusive'
        comparisons[policy] = {'gate': gate, 'lookupSavings': savings, 'caseRanges': interval}
    return {'totals': totals, 'comparisons': comparisons, 'panels': details}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, inputs = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for _, plan, _ in inputs.values()):
        cli.error('Use pinned GEPA 0.1.4')
    results = {name: measure(*item) for name, item in inputs.items()}
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
