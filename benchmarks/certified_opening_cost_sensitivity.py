"""Reproduce cost sensitivity for certified opening validation from archived charges."""

import argparse
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path


DATA = Path(__file__).with_name('data') / 'certified-opening-cost-terms-v1.json'


def extreme_ratio(terms, fixed, *, maximize):
    """Extremize CPO cost divided by GEPA cost using one price per reply."""
    ratio = Fraction(1)
    direction = 1 if maximize else -1
    while True:
        cpo, gepa = fixed
        for cpo_uses, gepa_uses, low, _, high in terms:
            # At the current ratio, the signed contribution of each price
            # is independent. The selected endpoints give the next ratio.
            weight = ratio.denominator * cpo_uses - ratio.numerator * gepa_uses
            charge = high if direction * weight > 0 else low
            cpo += charge * cpo_uses
            gepa += charge * gepa_uses
        revised = Fraction(cpo, gepa)
        if revised == ratio:
            return ratio
        ratio = revised


def describe(terms, fixed):
    def cost(arm, column):
        return fixed[arm] + sum(row[arm] * row[column] for row in terms)

    shared = [1 - extreme_ratio(terms, fixed, maximize=maximize) for maximize in (True, False)]
    separate = [1 - Fraction(cost(0, 4), cost(1, 2)), 1 - Fraction(cost(0, 2), cost(1, 4))]
    return {'originalCostMicrousd': {'cpo': cost(0, 3), 'gepa': cost(1, 3)},
            'sharedChargeSavingsFraction': list(map(str, shared)),
            'separateChargeSavingsFraction': list(map(str, separate)),
            'sharedChargesAlwaysSaveAtLeastTenPercent': shared[0] >= Fraction(1, 10),
            'separateChargesAlwaysSaveAtLeastTenPercent': separate[0] >= Fraction(1, 10)}


def measure(data):
    def scope(tasks, phase_indices, *, phase=None):
        terms = []
        fixed = [0, 0]
        scores = Counter()
        for info in tasks:
            record = info['pairedScores']
            scores.update(record['pooled'] if phase is None else record['byPhase'][phase])
            for arm in range(2):
                fixed[arm] += sum(info['fixedChargesMicrousd'][phase][arm] for phase in phase_indices)
            for count, *group in info['cellGroups']:
                uses = [count * sum(group[2 * phase + arm] for phase in phase_indices) for arm in range(2)]
                terms.append((*uses, *group[-3:]))
        return {**describe(terms, fixed), 'pairedScores': dict(scores)}

    tasks = data['tasks']
    phases = range(len(data['phases']))
    return {'parentReportSha256': data['parentReportSha256'], 'pooled': scope(tasks.values(), phases),
            'byPhase': {name: scope(tasks.values(), (phase,), phase=name) for phase, name in enumerate(data['phases'])},
            'byTask': {task: scope((info,), phases) for task, info in tasks.items()}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path, nargs='?', default=DATA)
    args = parser.parse_args()
    print(json.dumps(measure(json.loads(args.data.read_bytes())), indent=2, sort_keys=True))
