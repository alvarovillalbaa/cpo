"""Use tied co-observed evidence to choose among paid strict certificates."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_calibrated_training_route as prior
from cpo._contract import digest


parent, transfer, math, core = prior.parent, prior.transfer, prior.math, prior.core
REFERENCE = 'docs/recorded-calibrated-training-route-results-v1.json'
REFERENCE_SHA256 = '1bbe3cd66272b46c638b7dfa698361e0257c369b545086394f9a63c1c21d193d'
TIE = 'paid-head-to-head-tie'
PRESERVE = 'paid-head-to-head-preserve-incumbent'
MODES = (TIE, PRESERVE)


def comparisons(incumbent, first, roster, rows, ledger, mode):
    """Rank strict certificates by net gain on cases shared with the first nominee."""
    if first == incumbent:
        return {}
    baseline = {row.id: ledger[incumbent, row.id].passed for row in rows}
    target = sum(baseline.values()) + 1
    protected = {row.id for row in rows if row.critical and baseline[row.id]}
    leader = {row.id: ledger[first, row.id].passed for row in rows if (first, row.id) in ledger}
    ranks = {}
    for candidate in roster:
        if candidate == first:
            continue
        paid = {row.id: ledger[candidate, row.id].passed for row in rows if (candidate, row.id) in ledger}
        passes = sum(paid.values())
        if passes < target or any(not paid.get(case) for case in protected):
            continue
        shared = paid.keys() & leader.keys()
        wins = sum(paid[case] and not leader[case] for case in shared)
        losses = sum(leader[case] and not paid[case] for case in shared)
        if wins and wins >= losses and (mode == TIE or all(grade or not baseline[case] for case, grade in paid.items())):
            ranks[candidate] = wins - losses, -losses, passes, len(shared)
    return ranks


def run_trial(cells, start, roster, cohorts, seed, cap, mode):
    original = math.select
    allowed = {}

    def nominate(incumbent, candidates, rows, observe, ledger, **kwargs):
        first, tied = original(incumbent, candidates, rows, observe, ledger, **kwargs)
        allowed.update(comparisons(incumbent, first, candidates, rows, ledger, mode))
        if not allowed:
            return first, tied
        return max(allowed, key=allowed.__getitem__), False

    with (patch.object(math, 'select', nominate), patch.object(core.prior, 'can_defer', lambda *_: False),
          patch.object(core.backup, 'select_with_training', lambda _, first, *args, **kwargs: first)):
        point, trace, grades = prior.adapter.run_trial(cells, start, roster, cohorts, seed, cap,
                                                        parent.BASELINE, prior.adapter.EXPECTED)
    if (point['searchLookups'] > cap or point['qualificationLookups'] > 2 * len(cohorts[2])
            or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']):
        raise ValueError('Reranking must preserve the search allowance and one independent proof')
    return point, trace, grades, tuple(allowed)


def prepare():
    inherited, data, controls, baseline, _, _ = prior.prepare()
    report = transfer.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, inherited)
    if inherited['route']:
        raise ValueError('The archived no-training route must reproduce')
    plan = {**{key: inherited[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                               'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-paid-head-to-head-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': REFERENCE_SHA256, 'methods': MODES,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Keep the original strict validation race. Consider only a paid strict certificate '
                     'against the incumbent. A candidate needs at least one head-to-head win and '
                     'at least as many wins as losses on cases also paid for the original winner. '
                     'Compare that rule with preserving every observed incumbent pass. Rank by '
                     'net gain, fewer losses, certified passes and shared observations, then '
                     'original roster order. Buy no extra validation and apply one independent proof. '
                     'Audit a hindsight ceiling over only the offers each paid rule allowed.'}
    return plan, data, controls, baseline, report['results']


def measure(plan, cells, settings, group, width, controls, baseline, reference, mode):
    changes, never, original_traces = Counter(), Counter(), []
    original = core.trial

    def trial(*args):
        original_args = args[:-1]
        old, old_trace, before, _ = prior.run_trial(*original_args, ())
        point, trace, grades, offers = run_trial(*original_args, mode)
        never.update(old)
        original_traces.append(old_trace)
        if (point['searchLookups'] != old['searchLookups']
                or (not offers and (trace != old_trace or point != old or grades != before))):
            raise ValueError('The paid-prefix replay may only change the chosen independent proof')
        start, cohorts = original_args[1], original_args[3]
        delta = sum(grades) - sum(before)
        hindsight = sum(before)
        for prompt in offers:
            gain = sum(cells[prompt][case][0] - cells[start][case][0] for case in cohorts[2])
            deployed = prompt if gain > 0 else start
            hindsight = max(hindsight, sum(cells[deployed][case][0] for case in cohorts[-1]))
        if hindsight < sum(grades):
            raise ValueError('The offer ceiling must include the realized deployment, including retention')
        changes.update(trials=1, eligibleAlternatives=len(offers), changedNominations=int(trace[2] != old_trace[2]),
                       changedDeployments=int(trace[3] != old_trace[3]), passDelta=delta, grossGain=max(delta, 0),
                       grossLoss=max(-delta, 0), lookupDelta=point['paidLookups'] - old['paidLookups'],
                       hindsightGainCeiling=hindsight - sum(before))
        if transfer.HISTORICAL in point:
            changes['historicalCostDeltaNanodollars'] += point[transfer.HISTORICAL] - old[transfer.HISTORICAL]
        return point, trace, grades

    def existing(*args):
        return parent.run_trial(*args[:-1]) if args[-1] == parent.ORDERED else original(*args)

    anchors = {**controls, 'totals': {**controls['totals'], parent.ORDERED: baseline['anchors'][parent.ORDERED]}}
    with (patch.object(transfer, 'PRIMARY', mode), patch.object(transfer, 'METHODS', (mode, core.FIRST, parent.ORDERED)),
          patch.object(core, 'trial', existing), patch.object(transfer.parity.shortlist, 'trial', trial)):
        result = transfer.measure(plan, cells, settings, group, width, anchors)
    if (never != reference['totals'][prior.NEVER]
            or digest(original_traces) != reference['totals'][prior.ARM]['traceSha256']
            or any(point != baseline['totals'][label] for label, point in result['totals'].items() if label != mode)
            or any(value[core.FIRST] != baseline['comparisons'][key][core.FIRST]
                   for key, value in result['comparisons'].items())):
        raise ValueError('Original traces and both cost frontiers must reproduce')
    return {'totals': result['anchors'][mode], 'pairedChanges': changes,
            'comparisons': {key: value[mode] for key, value in result['comparisons'].items()}}


def replay(plan, data, controls, baseline, reference):
    results = {}
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        results[dataset] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                name = f'{group}/{width}'
                results[dataset][name] = {mode: measure(plan, cells, settings, group, width, controls[dataset][name],
                                                          baseline[dataset][name], reference[dataset][name], mode)
                                          for mode in MODES}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
