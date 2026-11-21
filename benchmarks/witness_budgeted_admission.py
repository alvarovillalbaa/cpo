"""Compare exact, budget-aware proof ordering on the same CPO nominations."""

import argparse
from collections import Counter
from fractions import Fraction
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_nominee_probe as previous
from cpo import Row
from cpo._contract import digest
from cpo.halving import qualification_budget


ROOT, REPLAY = previous.ROOT, previous.REPLAY
REFERENCE = 'docs/witness-nominee-probe-results-v1.json'
REFERENCE_SHA = '9058777d550acfbb2228a982f6e3ecc62d11bb6198b34294906cc46239dcc42b'
SELECTORS = {'expected-reads': partial(qualification_budget.qualify_with_budget_lookahead, prioritize_promotion=False),
             'budget-lookahead': qualification_budget.qualify_with_budget_lookahead}
METHODS = {f'{method}/{cap}': (cap, False) for method in ('proof-only', *SELECTORS) for cap in previous.CAPS}
BASE = previous.BASE


def prepare():
    parent, _, native, data = previous.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA or reference['planSha256'] != digest(parent):
        raise ValueError('Use the published same-cap proof controls')
    files = (Path(__file__).resolve(), Path(qualification_budget.__file__).resolve())
    plan = {'protocol': 'witness-budgeted-admission-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': REFERENCE_SHA, 'sourceSha256': {
                path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest() for path in files},
            'fallbackValidationCap': parent['fallbackValidationCap'], 'pairedCaseDraws': parent['pairedCaseDraws'],
            'resamplingSeed': parent['resamplingSeed'], 'methods': tuple(METHODS), 'allowances': previous.CAPS,
            'rule': 'Keep the nominee and allotted proof cases fixed. Compare seeded order, expected-read order, '
                    'and a planner that prioritizes certifiable promotion, then settlement, under the remaining cap.',
            'gate': 'Transfer a rule selected using other-family proof outcomes. Require no higher paid cost '
                    'and a positive paired lower endpoint against full seeded proof on each cohort.'}
    return plan, reference, native, data


def outcomes(matrix, held, start, layouts, plan, policy, nomination):
    nominee = nomination.original
    if nominee is None:
        return dict.fromkeys(METHODS, (start, 0, 0, False, False, False))
    cycle = next(index for index, layout in enumerate(layouts) if nominee in layout['alternatives'])
    layout = layouts[cycle]
    current = list(layout['qualify'])
    bank = [case for earlier in layouts[:cycle] for case in earlier['qualify']]
    reserve = bank[:plan['maximumExtensionRows']]
    allowed = set(current + reserve)
    if allowed & set(held) or allowed & {case for _, case in nomination.grades}:
        raise ValueError('The independent proof overlaps search or holdout')
    if plan['qualificationPolicy'] != 'extend-ties':
        raise ValueError('Use the original tie-extension gate')

    def grade(prompt, case):
        if case not in allowed:
            raise ValueError('An admission callback left its independent panel')
        return matrix[int(prompt)][case] == '1'

    prior = []
    for prompt in (start, nominee):
        votes = [passed for (name, _), passed in nomination.grades.items() if name == prompt]
        prior.append((sum(votes), len(votes)))
    baseline = previous.admit(start, nominee, current, bank.copy(), grade, plan=plan, seed=layout['seed'],
                              recycle=policy == 'recycle-unread', remaining=24)
    full = baseline[0]
    decisions = {}
    for method, (cap, _) in METHODS.items():
        scheduler = method.rsplit('/', 1)[0]
        if method == BASE:
            selected, cost, stopped = baseline
        elif scheduler == 'proof-only':
            selected, cost, stopped = previous.admit(start, nominee, current, bank.copy(), grade, plan=plan,
                                                     seed=layout['seed'], recycle=policy == 'recycle-unread',
                                                     remaining=cap)
        else:
            proof = SELECTORS[scheduler](
                start, nominee, [Row(str(case), 'task') for case in current], lambda p, row, _: grade(p, int(row.id)),
                reserve=[Row(str(case), 'task') for case in reserve], minimum_gain=plan['minimumQualificationGain'],
                validation_counts=prior, evaluation_limit=cap)
            selected, cost, stopped = proof.prompt, len(proof.observations), proof.status == 'undecided'
        if (cap == 24 and (stopped or selected != full)) or (selected != start and selected != full):
            raise ValueError('An ordered proof changed the complete admission gate')
        decisions[method] = selected, cost, 0, stopped, False, False
    return decisions


def summarize(groups, plan, reference, native, chosen):
    totals = {}
    bands = {}
    votes = {name: {'decisionsPerCase': unit['decisionsPerCase'], 'cases': unit['cases']} for name, unit in groups.items()}
    for method, (cap, _) in METHODS.items():
        counts = sum((unit['counts'][method] for unit in groups.values()), Counter())
        accuracy = sum(Fraction(sum(unit['cases'][method]), len(unit['held']) * unit['decisionsPerCase'])
                       for unit in groups.values()) / len(groups)
        eligible = {arm: row for arm, row in native['totals'].items() if row['paidLookups'] <= counts['paidLookups']
                    and (arm.startswith('gepa-') or arm == previous.earlier.gap.paired.replay.START)}
        control = min(eligible, key=lambda arm: (-Fraction(eligible[arm]['macroAccuracy']), eligible[arm]['paidLookups'], arm))
        totals[method] = {key: counts[key] for key in ('holdoutPasses', 'paidLookups', 'proofLookups', 'proofCapped', 'promotions')}
        totals[method].update(macroAccuracy=str(accuracy), bestAffordableNative={'arm': control, **eligible[control]})
        matching = f'proof-only/{cap}'
        if method == matching:
            if any(totals[method][key] != reference['totals'][method].get(key, 0) for key in
                   ('holdoutPasses', 'paidLookups', 'proofLookups', 'proofCapped', 'promotions')):
                raise ValueError('A seeded same-cap proof control differs from its frozen cost or score')
        else:
            with patch.object(previous.earlier.paired_bands, 'BASELINE', matching):
                bands[method] = previous.earlier.paired_bands.paired_ranges(votes, method, plan)['subjectsAndCases']
    with patch.object(previous.earlier.paired_bands, 'BASELINE', BASE):
        transfer = previous.earlier.paired_bands.paired_ranges(votes, chosen, plan)['subjectsAndCases']
    return {'totals': totals, 'pairedVsSameCap': bands, 'selectedOutsideFamily': chosen, 'selectedVsOriginal': transfer,
            'qualifies': totals[chosen]['paidLookups'] <= totals[BASE]['paidLookups']
            and transfer['interval95PercentagePoints'][0] > 0}


def execute(plan, reference, native, data):
    earlier = previous.earlier
    with patch.multiple(previous, METHODS=METHODS, outcomes=outcomes):
        replayed = {name: previous.measure(*data[name], plan['fallbackValidationCap']) for name in earlier.PHASES}
        bbh = earlier.gap.paired.BBH
        train = {bbh: previous.summarize_training(list(replayed[bbh][0].values())),
                 'mmlu': previous.summarize_training(
                     [unit for name in earlier.gap.paired.replay.PHASES for unit in replayed[name][0].values()])}
    cohorts = {name: {**summarize(groups, plan, reference['cohorts'][name], native['cohorts'][name],
                                  train['mmlu' if name == bbh else bbh]['selected']), 'panelTraceSha256': traces}
               for name, (groups, traces) in replayed.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'training': train,
            'cohorts': cohorts, 'qualifies': all(entry['qualifies'] for entry in cohorts.values())}


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
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    report = execute(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
