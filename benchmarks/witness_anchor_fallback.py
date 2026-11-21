"""Settle a bounded four-anchor race only after the rotating witness finds no nominee."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import witness_anchor_routing_budget as parent
from benchmarks.witness_anchor_bounds import race, reference_runner
from benchmarks.witness_fallback_caps import LookupLimit
from cpo._contract import digest


ROOT, RANKING, retry, FULL = parent.ROOT, parent.RANKING, parent.retry, parent.FULL
REPLAY = parent.parent.REPLAY
REFERENCE = 'docs/witness-anchor-routing-budget-results-v1.json'
REFERENCE_SHA256 = 'fec4d74b76f106e1531c50bfa26a8a210a8f8e9d2902e3b0bc647031fcc3d708'
ANCHORS = 4
CAPS = {f'cached-anchor-fallback/{limit}': limit for limit in (8, 16)}
PRIMARY = 'cached-anchor-fallback/16'
METHODS = (retry.BASE, FULL, *CAPS)


def prepare():
    upstream, _, _, native, data = parent.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(upstream):
        raise ValueError('Use the published budget-transfer replay')
    plan = {key: upstream[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed')}
    plan.update(protocol='witness-anchor-fallback-v1', parentPlanSha256=digest(upstream),
                parentReceiptSha256=REFERENCE_SHA256, sourceSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                methods=METHODS, primary=PRIMARY, anchors=ANCHORS, newLookupCaps=CAPS,
                trigger='Preserve every witness nomination. If the rotating witness returns none, replace '
                'Halving with the exact four-anchor race over the same cycles and proposal order.',
                budget='Use the existing witness cache and charge only new grades, pooled across cycles. '
                'If the next new read would exceed the cap before settlement, retain the incumbent.',
                gate='Require a positive paired lower endpoint against the expected-read first proof '
                'and realized lookup cost within the seeded ceiling on every cohort.')
    return plan, reference, native, data


def cached_race(start, layouts, paid, evaluate, limit, activity):
    observations = dict(paid)
    lookups = 0

    def read(prompt, case):
        nonlocal lookups
        key = prompt, case
        if key not in observations:
            if lookups == limit:
                raise LookupLimit
            observations[key] = evaluate(prompt, case)
            lookups += 1
        else:
            activity['cacheHits'] += 1
        return observations[key]

    for layout in layouts:
        anchors = list(layout['validation'])
        Random(layout['seed']).shuffle(anchors)
        if len(anchors) < ANCHORS:
            raise ValueError('The anchor fallback needs four distinct validation cases')
        candidates = (start, *layout['alternatives'])
        activity['races'] += 1
        try:
            settled = race(candidates, anchors[:ANCHORS], read, ANCHORS * len(candidates))
        except LookupLimit:
            activity['cappedEpisodes'] += 1
            break
        if not settled.settled:
            raise ValueError('A full anchor race must settle the winning identity')
        if settled.prompt != start:
            activity['nominations'] += 1
            return RANKING.Nomination(settled.prompt, len(observations), observations)
    return RANKING.Nomination(None, len(observations), observations)


def original_search(matrix, held, start, layouts, active, policy, cap):
    halving = RANKING.gap.paired.CachedLookaheadHalving
    prefix = None

    def capture(*, metric_limit, paid):
        nonlocal prefix
        if prefix is not None or metric_limit != cap:
            raise ValueError('Expected one fallback with the sealed Halving cap')
        prefix = dict(paid)
        return halving(metric_limit=metric_limit, paid=paid)

    with patch.object(RANKING.gap.paired, 'CachedLookaheadHalving', capture):
        nomination = RANKING.search_to_nomination(matrix, held, start, layouts, active, policy, cap)
    return nomination, prefix


def measure(plan, data, reference, native):
    inputs, panels, _, _, cap = data
    schedule, policy = inputs['schedule'], inputs['qualificationBank']
    active = {**schedule, 'evaluationLookupLimit': cap}
    groups, traces = {}, {}
    activity = {arm: Counter() for arm in CAPS}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        identity = tuple(panel['caseIDs'][case] for case in held) if 'caseIDs' in panel else panel['caseOrderSha256']
        group = groups.setdefault(subject, {'identity': identity, 'decisionsPerCase': 0, 'costs': Counter(),
                                            'cases': {arm: [0] * len(held) for arm in METHODS},
                                            'wideEpisodes': Counter()})
        if group['identity'] != identity:
            raise ValueError('Both models must share holdout cases')
        group['decisionsPerCase'] += len(schedule['seeds'])
        trace = []
        for seed in schedule['seeds']:
            start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
            nomination, paid = original_search(matrix, held, start, layouts, active, policy,
                                               plan['fallbackValidationCap'])
            old = retry.outcomes(matrix, held, start, layouts, active, policy, nomination)
            trace.append((seed, tuple((item.prompt, item.lookups, item.status, item.retry)
                                      for item in (old[retry.BASE], old[FULL]))))
            payouts = {arm: (nomination, old[arm]) for arm in (retry.BASE, FULL)}
            evaluate = lambda prompt, case: matrix[int(prompt)][case] == '1'
            for arm, limit in CAPS.items():
                if paid is None:
                    payouts[arm] = payouts[FULL]
                    continue
                activity[arm]['eligibleEpisodes'] += 1
                recovered = cached_race(start, layouts, paid, evaluate, limit, activity[arm])
                purchased = recovered.paid_search - len(paid)
                if not 0 <= purchased <= limit or any(recovered.grades[key] != value for key, value in paid.items()):
                    raise ValueError('Anchor fallback exceeded its cap or lost a paid grade')
                proof = reference_runner.qualify(matrix, held, start, layouts, active, recovered)
                activity[arm].update(validationLookups=purchased, proofLookups=proof.lookups,
                                     promotions=int(proof.prompt != start))
                payouts[arm] = recovered, proof
            for arm, (searched, proved) in payouts.items():
                votes = (int(matrix[int(proved.prompt)][case] == '1') for case in held)
                group['cases'][arm] = [value + vote for value, vote in zip(group['cases'][arm], votes, strict=True)]
                group['costs'][arm] += searched.paid_search + proved.lookups
        traces[f'{subject}/{model}'] = digest(trace)
    totals = {arm: parent.parent.totals(list(groups.values()), arm) for arm in METHODS}
    if traces != reference['panelTraceSha256'] or any(totals[arm] != reference['controls'][arm]
                                                    for arm in (retry.BASE, FULL)):
        raise ValueError('The seeded or expected-read first-proof control changed')
    for row in totals.values():
        del row['wideEpisodes']
    paired, affordable = {}, {}
    for arm in CAPS:
        with patch.object(RANKING.paired_bands, 'BASELINE', FULL):
            paired[arm] = RANKING.paired_bands.paired_ranges(groups, arm, plan)['subjectsAndCases']
        available = [(key, row) for key, row in native['totals'].items()
                     if key.startswith('gepa-') and row['paidLookups'] <= totals[arm]['paidLookups']]
        setting, best = min(available, key=lambda item: (-Fraction(item[1]['macroAccuracy']), item[1]['paidLookups'], item[0]))
        affordable[arm] = {'setting': setting, **best}
    return {'totals': totals, 'pairedVsOriginal': paired, 'fallbackActivity': activity,
            'bestAffordableNativeGEPA': affordable, 'panelTraceSha256': traces,
            'qualifies': totals[PRIMARY]['paidLookups'] <= totals[retry.BASE]['paidLookups']
            and paired[PRIMARY]['interval95PercentagePoints'][0] > 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, reference, native, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    cohorts = {phase: measure(plan, data[phase], reference['cohorts'][phase], native['cohorts'][phase])
               for phase in RANKING.PHASES}
    report = {'plan': plan, 'planSha256': seal, 'cohorts': cohorts, 'newProviderRequests': 0,
              'qualifies': all(row['qualifies'] for row in cohorts.values())}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
