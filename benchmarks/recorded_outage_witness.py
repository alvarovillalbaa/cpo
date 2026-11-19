"""Test a reserved critical outage case without imputing missing replies."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_promotion_coverage as prior, recorded_promotion_strata as strata
from benchmarks.recorded_field_preservation import SOURCE_PLAN_SHA256, parse, verified
from cpo._contract import digest


TASK = 'outage'
TARGET = (2, 'MISSING')
METHODS = prior.METHODS
BASELINE = 'risk-diverse'
ROOT = Path(__file__).resolve().parents[1]
RESULT_SHA256 = 'c95283b9edb80e3c640c4d95a0bb256278827c70c9a028dca5ce33258f9eb7be'


def reserve_witness(rows, incumbent):
    """Prescreen the incumbent only and reserve the entire target stratum."""
    reserved = sorted(row['id'] for row in rows if row['critical'] and strata.risk_stratum(TASK, row) == TARGET)
    for index, case in enumerate(reserved, start=1):
        if incumbent[case][0]:
            return reserved, case, index
    raise ValueError('The incumbent has no recorded pass in the reserved stratum')


def prepare(replay, source_plan, archive):
    _, base, _, data, run_gepa, cohorts, risk = strata.prepare(replay)
    old = parse(verified(ROOT / 'docs/recorded-promotion-strata-results-v1.json', RESULT_SHA256))
    (_, _, _, holdouts, _), _, incumbent, _ = data[TASK]
    source = parse(verified(source_plan, SOURCE_PLAN_SHA256))
    file = 'outage-strict-plan.json'
    cases = parse(verified(archive / file, source['taskSources'][TASK][file]))['datasets']['holdout']
    reserved, witness, prescreen = reserve_witness(cases, holdouts[incumbent])
    external = {row['id']: row['critical'] for row in cases if row['id'] not in reserved}
    plan = {'protocol': 'cpo-recorded-outage-witness-v1', 'task': TASK, 'gepaVersion': base['gepaVersion'],
            'baselineReportSha256': RESULT_SHA256, 'sourcePlanSha256': SOURCE_PLAN_SHA256,
            'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'targetStratum': list(TARGET),
            'disjointReserve': reserved, 'selectedWitness': witness, 'incumbentPrescreenLookups': prescreen,
            'remainingExternalCases': len(external), 'retainedReplaySplits': len(cohorts[TASK]),
            'rule': 'After promotion, require a pass on the witness if the target stratum was absent from all nine development cases',
            'paidAccounting': 'Charge shared incumbent prescreen separately and one challenger evaluation per eligible split'}
    return plan, base, old['results'][TASK], data[TASK], run_gepa, cohorts[TASK], risk[TASK], external


def same_panel(data, held, seed, base, run_gepa, risk):
    rows = data[0][1]
    critical = {case for case, row in rows.items() if row['critical']}
    old_assign = prior.assign_panels
    layouts = []

    def allocate(validation, promotion, metadata, _):
        baseline = old_assign(validation, promotion, metadata, 2)
        matched = strata.assign_risk_panels(*baseline, critical, risk, seed)[BASELINE]
        layouts.extend(matched)
        return matched

    with patch.object(prior, 'POLICIES', {BASELINE: 2}), patch.object(prior, 'assign_panels', allocate):
        item = prior.compare(data, held, seed, base, run_gepa)
    return item, layouts[0], layouts[1]


def selected_prompt(chosen, incumbent, applies, witnessed):
    """Resolve one candidate using only the selected witness bit, if required."""
    return incumbent if applies and not witnessed[chosen] else chosen


def score_possible_world(trials, incumbent, witnessed, matrix, critical):
    scores = {arm: Counter(passes=0, calls=0, promotions=0) for arm in METHODS}
    losses = Counter({arm: 0 for arm in METHODS[1:]})
    for trial in trials:
        held = trial['holdout']
        matches = {}
        for arm in METHODS:
            entry = trial['arms'][arm]
            selected = selected_prompt(entry['chosen'], incumbent, entry['witnessRequired'], witnessed)
            matches[arm] = {case: matrix[selected][case][0] for case in held}
            scores[arm]['passes'] += sum(matches[arm].values())
            scores[arm]['calls'] += entry['calls'] + int(entry['witnessRequired'])
            scores[arm]['promotions'] += selected != incumbent
        for arm in METHODS[1:]:
            losses[arm] += sum(case in critical and matches[arm][case] and not matches['cpo'][case] for case in held)
    return scores, losses


def witness_bounds(trials, incumbent, witnessed, matrix, critical, missing):
    """A missing prompt has one shared witness outcome across splits and arms."""
    if len(missing) > 10:
        raise ValueError('The small fixed archive exceeds the exact missing-outcome enumeration limit')
    worlds = [score_possible_world(trials, incumbent, {**witnessed, **dict(zip(missing, bits, strict=True))}, matrix, critical)
              for bits in product((False, True), repeat=len(missing))]
    metrics = ('passes', 'calls', 'promotions')
    return {
        'candidateMetrics': {arm: {metric: bounds(scores[arm][metric] for scores, _ in worlds) for metric in metrics}
                             for arm in METHODS},
        'matchedCriticalLosses': {arm: bounds(losses[arm] for _, losses in worlds) for arm in METHODS[1:]},
        'pairedPassDelta': {arm: bounds(scores['cpo']['passes'] - scores[arm]['passes'] for scores, _ in worlds)
                            for arm in METHODS[1:]},
    }


def bounds(values):
    values = list(values)
    return [min(values), max(values)]


def run(plan, base, old, data, run_gepa, held, risk, external):
    (_, rows, matrix, holdouts, _), _, incumbent, _ = data
    critical = {case for case, row in rows.items() if row['critical']}
    if set(external) & set(rows):
        raise ValueError('The retained provider holdout must be disjoint from the replay bank')
    witness = plan['selectedWitness']
    witnessed = {prompt: panel[witness][0] for prompt, panel in holdouts.items()}
    trials, baseline_losses = [], []
    baseline = {arm: Counter(passes=0, calls=0, promotions=0) for arm in METHODS}
    for index, cases in enumerate(held):
        seed = base['seedStart'] + index * base['seedStride']
        item, validation, promotion = same_panel(data, cases, seed, base, run_gepa, risk)
        development = set(rows) - set(cases)
        train = development - set(validation) - set(promotion)
        novel = not any(risk[case] == TARGET for case in development)
        arms = {}
        for arm in METHODS:
            entry = item['arms'][f'{arm}.{BASELINE}']
            required = novel and entry['promotion'] == 'promote'
            if entry['searchEvaluations'] + entry['qualificationEvaluations'] + 2 * required > base['metricLimit'] + 6:
                raise ValueError('The augmented decision would exceed the original evaluation envelope')
            baseline[arm].update(passes=sum(entry['outcomes'].values()), calls=entry['calls'],
                                 promotions=int(entry['promotion'] == 'promote'))
            arms[arm] = {**entry, 'witnessRequired': required}
        for arm in METHODS[1:]:
            for case in item['critical']:
                if arms[arm]['outcomes'][case] and not arms['cpo']['outcomes'][case]:
                    baseline_losses.append({'seed': seed, 'case': case, 'control': arm,
                                            'inTrain': any(risk[row] == risk[case] for row in train),
                                            'inValidation': any(risk[row] == risk[case] for row in validation),
                                            'inPromotion': any(risk[row] == risk[case] for row in promotion),
                                            'witnessRequired': arms['cpo']['witnessRequired'],
                                            'controlWitnessRequired': arms[arm]['witnessRequired'],
                                            'incumbentPassed': matrix[incumbent][case][0]})
        trials.append({'holdout': cases, 'arms': arms})
    for arm, totals in baseline.items():
        if any(value != old['totals'][f'{arm}.{BASELINE}'][metric] for metric, value in totals.items()):
            raise ValueError('The source diverse-panel replay did not reproduce')
    for arm in METHODS[1:]:
        if sum(item['control'] == arm for item in baseline_losses) != old['comparisons'][f'{arm}.{BASELINE}']['criticalLosses']:
            raise ValueError('The source diverse-panel critical losses did not reproduce')

    needed = Counter(trial['arms'][arm]['chosen'] for trial in trials for arm in METHODS
                     if trial['arms'][arm]['witnessRequired'])
    missing = sorted(needed.keys() - witnessed.keys())
    coverage = {arm: Counter(required=0, recordedPass=0, recordedFailure=0, missing=0) for arm in METHODS}
    for trial in trials:
        for arm, entry in trial['arms'].items():
            if entry['witnessRequired']:
                result = witnessed.get(entry['chosen'])
                coverage[arm]['required'] += 1
                coverage[arm][{True: 'recordedPass', False: 'recordedFailure', None: 'missing'}[result]] += 1
    return {'plan': plan, 'planSha256': digest(plan), 'baseline': baseline, 'baselineCriticalLossObservations': baseline_losses,
            'witnessEvidence': coverage, 'missingWitnessPromptCount': len(missing), 'possibleWorlds': 2 ** len(missing),
            'replayBounds': witness_bounds(trials, incumbent, witnessed, matrix, critical, missing)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('replay', 'source-plan', 'archive'):
        parser.add_argument('--' + argument, type=Path, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    setup = prepare(args.replay, args.source_plan, args.archive)
    plan = setup[0]
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = run(*setup)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
