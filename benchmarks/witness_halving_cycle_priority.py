"""Prioritize fallback Halving cycles using their already-paid selection evidence."""

import argparse
from fractions import Fraction
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_anchor_fallback as replay
from cpo._contract import digest
from cpo.halving import cached_lookahead, lookahead


ROOT, RANKING, FULL = replay.ROOT, replay.RANKING, replay.FULL
REFERENCE = 'docs/witness-anchor-fallback-results-v1.json'
REFERENCE_SHA256 = 'c8cdfa6b542f539fc8ab828867fac6adb9b47a14f6ecfb62b390a142735a1eb6'
DEFER, PRIORITY = 'finish-from-cache-after-cap', 'paid-halving-cycle-priority'
METHODS = (DEFER, PRIORITY)


def prepare():
    upstream, controls, native, data = replay.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(upstream):
        raise ValueError('Use the published fallback and original Halving controls')
    paths = (Path(__file__), Path(cached_lookahead.__file__), Path(lookahead.__file__))
    plan = {key: upstream[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed')}
    plan.update(protocol='witness-halving-cycle-priority-v1', methods=METHODS, primary=PRIORITY,
                parentPlanSha256=digest(upstream), parentReceiptSha256=REFERENCE_SHA256,
                sourceSha256={p.resolve().relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in paths},
                rule='At fallback entry, rank cycles by chance of a challenger under equally weighted unknown '
                'Halving boards divided by one plus the number of missing grades. Already-settled challenger '
                'cycles come first; ties retain cycle order. Use no held-out rows or new grades to calculate priority.',
                ablation='Compare the original cycle order with the same permission to finish later cycles '
                'from paid evidence after the shared lookup cap. Both use exact Halving and one independent proof.',
                gate='Require a positive paired lower endpoint against original Halving and the cache-only '
                'ablation, with no more than the seeded total lookup cost in every cohort.')
    return plan, reference, controls, native, data


def priority(start, layout, paid):
    candidates = (start, *layout['alternatives'])
    cases = tuple(layout['validation'][:lookahead._DEPTH])
    rounds = (len(candidates) - 1).bit_length()
    while rounds * len(candidates) > 8:
        candidates = candidates[:(len(candidates) + 1) // 2]
        rounds -= 1
    if len(candidates) not in (3, 4) or len(cases) != lookahead._DEPTH:
        raise ValueError('The priority measure requires the archived cap-eight Halving board')

    possible, masks, winners, _ = lookahead._tables(len(candidates))
    missing = 0
    for key, mask in zip(((prompt, case) for prompt in candidates for case in cases), masks, strict=True):
        if key in paid:
            possible &= mask if paid[key] else ~mask
        else:
            missing += 1
    decisive = lookahead._certain(possible, winners)
    challenger_boards = (possible & ~winners[0]).bit_count()
    return decisive not in (None, 0), Fraction(challenger_boards, possible.bit_count() * (1 + missing))


def fallback(start, layouts, paid, evaluate, limit, activity, *, rank_cycles):
    if rank_cycles:
        layouts = sorted(layouts, key=lambda layout: priority(start, layout, paid), reverse=True)
    selector = cached_lookahead.CachedLookaheadHalving(metric_limit=limit, paid=paid)
    for layout in layouts:
        if selector.exhausted:
            selector = cached_lookahead.CachedLookaheadHalving(metric_limit=0, paid=selector.observations)
        activity['cycles'] += 1
        nominee = selector.select((start, *layout['alternatives']), layout['validation'], evaluate)
        if nominee not in (None, start):
            activity['nominations'] += 1
            observations = selector.observations
            if len(observations) > len(paid) + limit:
                raise ValueError('Halving exceeded the original paid validation cap')
            return RANKING.Nomination(nominee, len(observations), observations)
        if nominee is None:
            activity['unfinishedCycles'] += 1
    observations = selector.observations
    return RANKING.Nomination(None, len(observations), observations)


def compare(plan, data, controls, native, reference):
    observed, reports = {}, {}
    paired_bands = RANKING.paired_bands
    paired = paired_bands.paired_ranges

    def capture(groups, method, active):
        observed[method] = groups
        return paired(groups, method, active)

    for arm in METHODS:
        candidate = partial(fallback, rank_cycles=arm == PRIORITY)
        with (patch.multiple(replay, PRIMARY=arm, CAPS={arm: plan['fallbackValidationCap']},
                             METHODS=(replay.retry.BASE, FULL, arm), cached_race=candidate),
              patch.object(paired_bands, 'paired_ranges', capture)):
            reports[arm] = replay.measure(plan, data, controls, native)
        if reports[arm]['panelTraceSha256'] != reference['panelTraceSha256'] or any(
                reports[arm]['totals'][control] != reference['totals'][control] for control in (replay.retry.BASE, FULL)):
            raise ValueError('The seeded and original Halving outcomes changed')
        if reports[arm]['fallbackActivity'][arm]['eligibleEpisodes'] != reference['fallbackActivity'][replay.PRIMARY]['eligibleEpisodes']:
            raise ValueError('Cycle priority changed the established fallback trigger')

    groups = observed[PRIORITY]
    if groups.keys() != observed[DEFER].keys():
        raise ValueError('The ablation must use the same archived subjects')
    for subject, group in groups.items():
        other = observed[DEFER][subject]
        if any(group[key] != other[key] for key in ('identity', 'decisionsPerCase')):
            raise ValueError('The ablation must use the same case identities and episodes')
        group['cases'][DEFER] = other['cases'][DEFER]
    with patch.object(paired_bands, 'BASELINE', DEFER):
        versus_defer = paired(groups, PRIORITY, plan)['subjectsAndCases']
    summary = {key: {arm: reports[arm][key][arm] for arm in METHODS}
               for key in ('totals', 'pairedVsOriginal', 'fallbackActivity', 'bestAffordableNativeGEPA')}
    return {**summary, 'controls': {key: reference['totals'][key] for key in (FULL, replay.retry.BASE)},
            'pairedPriorityVsDeferred': versus_defer, 'panelTraceSha256': reference['panelTraceSha256'],
            'qualifies': reports[PRIORITY]['qualifies'] and versus_defer['interval95PercentagePoints'][0] > 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, reference, controls, native, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    cohorts = {phase: compare(plan, data[phase], controls['cohorts'][phase], native['cohorts'][phase],
                              reference['cohorts'][phase]) for phase in RANKING.PHASES}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'cohorts': cohorts, 'newProviderRequests': 0,
                   'qualifies': all(row['qualifies'] for row in cohorts.values())}, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
