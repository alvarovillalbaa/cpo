"""Initialize anchor score bounds with the paid witness evidence before fallback."""

import argparse
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import witness_anchor_fallback as parent
from benchmarks.witness_anchor_bounds import Race
from cpo._contract import digest


ROOT, RANKING, FULL = parent.ROOT, parent.RANKING, parent.FULL
REFERENCE = 'docs/witness-anchor-fallback-results-v1.json'
REFERENCE_SHA256 = 'c8cdfa6b542f539fc8ab828867fac6adb9b47a14f6ecfb62b390a142735a1eb6'
EXACT, PROVED = 'paid-anchor-exact/16', 'paid-anchor-proved-gain/16'
METHODS = (EXACT, PROVED)


def prepare():
    upstream, controls, native, data = parent.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    previous = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or previous['planSha256'] != digest(upstream):
        raise ValueError('Use the published cached anchor fallback replay')
    plan = {key: upstream[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed', 'anchors')}
    plan.update(protocol='witness-paid-anchor-bounds-v1', parentPlanSha256=digest(upstream),
                parentReceiptSha256=REFERENCE_SHA256, sourceSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                methods=METHODS, primary=PROVED,
                prefix='Keep every rotating witness nominee and the same first independent proof. When the '
                'witness finds none, initialize every candidate bound and anchor read rate from already paid grades.',
                finish='The exact arm requires an unbeatable score with proposal-order ties. The proved-gain '
                'arm can also nominate the best lower bound at the cap if it exceeds the incumbent upper bound.',
                budget='Each arm pools the original 16 new lookup budget across the same ordered cycles.',
                gate=upstream['gate'])
    return plan, previous, controls, native, data


def race(candidates, anchors, paid, evaluate, cap, *, allow_proved_gain):
    if not candidates or len(set(candidates)) != len(candidates) or not anchors or len(set(anchors)) != len(anchors):
        raise ValueError('Use distinct candidates and anchor cases')
    if type(cap) is not int or cap < 0:
        raise ValueError('Use a nonnegative lookup cap')

    pending = [[] for _ in candidates]
    lower = [0] * len(candidates)
    successes = dict.fromkeys(anchors, 0)
    reads = dict.fromkeys(anchors, 0)

    def record(index, case, grade):
        if type(grade) is not bool:
            raise ValueError('An anchor grade must be boolean')
        lower[index] += grade
        successes[case] += grade
        reads[case] += 1

    for index, candidate in enumerate(candidates):
        for case in anchors:
            key = candidate, case
            if key in paid:
                record(index, case, paid[key])
            else:
                pending[index].append(case)

    spent = 0
    while True:
        leader = max(range(len(candidates)), key=lambda index: (lower[index], -index))
        rivals = [index for index, unread in enumerate(pending) if index != leader
                  and (lower[index] + len(unread), -index) > (lower[leader], -leader)]
        if not rivals:
            return Race(candidates[leader], spent, True, bool(pending[leader]))
        if spent == cap:
            proved_gain = leader != 0 and lower[leader] > lower[0] + len(pending[0])
            selected = leader if allow_proved_gain and proved_gain else 0
            return Race(candidates[selected], spent, False, bool(pending[selected]))

        if pending[0]:
            selected, case = 0, pending[0][0]
        else:
            active = [*rivals, leader] if pending[leader] else rivals
            rates = {case: (successes[case] + 1) / (reads[case] + 2) for case in anchors}
            selected = max(active, key=lambda index: (lower[index] + sum(rates[case] for case in pending[index]), -index))
            choose_case = max if selected == leader else min
            case = choose_case(pending[selected], key=rates.__getitem__)
        record(selected, case, evaluate(candidates[selected], case))
        pending[selected].remove(case)
        spent += 1


def fallback(start, layouts, paid, evaluate, limit, activity, *, allow_proved_gain):
    observations = dict(paid)
    remaining = limit

    def purchase(prompt, case):
        key = prompt, case
        if key in observations:
            raise ValueError('The initial bounds missed a paid grade')
        observations[key] = evaluate(prompt, case)
        return observations[key]

    for layout in layouts:
        cases = list(layout['validation'])
        Random(layout['seed']).shuffle(cases)
        anchors = cases[:parent.ANCHORS]
        if len(anchors) != parent.ANCHORS:
            raise ValueError('The fallback needs four distinct validation cases')
        candidates = (start, *layout['alternatives'])
        activity['races'] += 1
        activity['preloadedGrades'] += sum((prompt, case) in observations for prompt in candidates for case in anchors)
        result = race(candidates, anchors, observations, purchase, remaining, allow_proved_gain=allow_proved_gain)
        remaining -= result.reads
        if not result.settled:
            activity['cappedEpisodes'] += 1
        if result.prompt != start:
            activity['nominations'] += 1
            activity['provedGainAtCap'] += int(not result.settled)
            return RANKING.Nomination(result.prompt, len(observations), observations)
        if not result.settled:
            break
    return RANKING.Nomination(None, len(observations), observations)


def compare(plan, data, native, controls, previous):
    runs = {}
    for arm in METHODS:
        chosen = partial(fallback, allow_proved_gain=arm == PROVED)
        with patch.multiple(parent, CAPS={arm: plan['fallbackValidationCap']}, PRIMARY=arm,
                            METHODS=(parent.retry.BASE, FULL, arm), cached_race=chosen):
            runs[arm] = parent.measure(plan, data, controls, native)
        if runs[arm]['panelTraceSha256'] != previous['panelTraceSha256']:
            raise ValueError('The original first-proof trace changed')
        if runs[arm]['fallbackActivity'][arm]['eligibleEpisodes'] != previous['fallbackActivity'][parent.PRIMARY]['eligibleEpisodes']:
            raise ValueError('The replacement must trigger on the same no-nominee episodes')

    historical = {parent.PRIMARY: previous['totals'][parent.PRIMARY]}
    for arm in (parent.retry.BASE, FULL):
        if any(runs[policy]['totals'][arm] != previous['totals'][arm] for policy in METHODS):
            raise ValueError('The original first-proof score or cost changed')
        historical[arm] = previous['totals'][arm]
    report = {key: {arm: runs[arm][key][arm] for arm in METHODS}
              for key in ('totals', 'pairedVsOriginal', 'fallbackActivity', 'bestAffordableNativeGEPA')}
    return {**report, 'publishedTotals': historical,
            'publishedFallbackActivity': previous['fallbackActivity'][parent.PRIMARY],
            'panelTraceSha256': previous['panelTraceSha256'], 'qualifies': runs[PROVED]['qualifies']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, previous, controls, native, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    cohorts = {phase: compare(plan, data[phase], native['cohorts'][phase], controls['cohorts'][phase],
                              previous['cohorts'][phase]) for phase in RANKING.PHASES}
    report = {'plan': plan, 'planSha256': seal, 'cohorts': cohorts, 'newProviderRequests': 0,
              'qualifies': all(row['qualifies'] for row in cohorts.values())}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
