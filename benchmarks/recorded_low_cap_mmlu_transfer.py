"""Transfer the frozen cap-13 validation race to disjoint archived MMLU panels."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import recorded_two_witness_mmlu_transfer as archive
from benchmarks import recorded_validation_tail_matched_caps as fitted
from cpo._contract import digest


cost, frontier = archive.cost, archive.cost.frontier
DISCOVERY_SHA256 = 'b2a7ad3681ebbc05fe199d70f1c008e1072188aa5831146254ba7670cf0ccb78'
TARGET_SHA256 = '5c043b5fc8458cf924bf868e03fc410f2c82e437294d6e0024279c0ddc0487ff'
POLICY = fitted.prior.baseline
PRIMARY = f'{POLICY}/13'
FULL = f'{POLICY}/54'


def check_enrollment(discovery, panels):
    tasks = {subject for cohort, subject, _ in discovery if cohort == 'MMLU'}
    models = {model for _, _, model in discovery}
    identities = [panel[:3] for panel in panels]
    if len(set(identities)) != len(identities):
        raise ValueError('An archived target panel was enrolled twice')
    for cohort, subject, model in identities:
        if cohort != 'MMLU' or subject in tasks or model in models:
            raise ValueError('Transfer requires subjects and checkpoints outside the cap sweep')


def prepare():
    donor, _, _, _ = fitted.prepare()
    source, panels = archive.prepare()
    read = cost.prior.baseline.read_reference
    discovery = read('docs/recorded-validation-tail-matched-caps-results-v1.json', DISCOVERY_SHA256, donor)
    reference = read('docs/recorded-two-witness-mmlu-transfer-results-v1.json', TARGET_SHA256, source)
    check_enrollment(donor['panels'], panels)
    if (discovery['language']['MMLU']['atMatchedBudgets']['5714']['settings']['cpo']['setting'] != PRIMARY
            or any(donor[key] != source[key] for key in ('caseCounts', 'seeds', 'challengers', 'searchCap',
                                                      'minimumSearchCap', 'gepaVersion'))):
        raise ValueError('The frozen candidate and episode schedule must match the published design')
    sources = (Path(__file__), Path(fitted.__file__), Path(archive.__file__), Path(cost.__file__))
    plan = {**{key: source[key] for key in ('caseCounts', 'seeds', 'challengers', 'searchCap',
                                          'minimumSearchCap', 'gepaVersion', 'bootstrapSeed', 'bootstrapDraws',
                                          'enrolledPanels', 'excludedPreviouslyExaminedTasks', 'archivesSha256')},
            'protocol': 'recorded-low-cap-mmlu-transfer-v1',
            'transferPlanSha256': digest(source), 'transferReceiptSha256': TARGET_SHA256,
            'discoveryPlanSha256': digest(donor), 'discoveryReceiptSha256': DISCOVERY_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in sources},
            'candidate': PRIMARY, 'fullValidationDiagnostic': FULL, 'nativeModes': cost.MODES,
            'gate': 'positive observed margin and nonnegative paired lower endpoint against the strongest '
                    'affordable common native GEPA setting or retained starts',
            'scope': 'Freeze cap 13 using the published discovery result. Replay all enrolled disjoint target '
                     'subjects and model checkpoints with their original case schedules. Give both native GEPA '
                     'modes every original cap. Match by realized search plus qualification and reselect the '
                     'affordable native setting on each paired case draw. Report full-pool CPO only for '
                     'attribution and a separately labeled subject-specific GEPA hindsight bound.'}
    return plan, panels, reference['results']


def measure_cpo(subject, matrix, plan):
    cells = {str(index): tuple((int(passed), None, False) for passed in row) for index, row in enumerate(matrix)}
    totals, vectors, changes = {}, {}, {}
    diagnostics = Counter()
    traces = []
    for seed in plan['seeds']:
        start, roster, cohorts = archive.transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
        arguments = cells, start, roster, cohorts, seed
        heldout = [cells[start][case][0] for case in cohorts[-1]]
        retained = {'holdoutPasses': sum(heldout), 'paidLookups': 0}
        totals.setdefault(frontier.RETAIN, Counter()).update(retained)
        fitted.prior.add_vector(vectors.setdefault(frontier.RETAIN, [0] * len(heldout)), heldout)
        outcomes = []
        for label in (plan['candidate'], plan['fullValidationDiagnostic']):
            policy, raw_cap = label.split('/')
            cap = int(raw_cap)
            point, trace, grades = fitted.cpo_trial(arguments, policy, cap)
            if (point['searchLookups'] > cap or point['qualificationLookups'] > 2 * len(cohorts[2])
                    or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']):
                raise ValueError('CPO exceeded its independent search or proof allowance')
            validation, qualification = cohorts[1:3]
            if trace[2] != start and sum(cells[trace[2]][case][0] - cells[start][case][0] for case in validation) <= 0:
                raise ValueError('A nominated challenger must strictly improve validation')
            if trace[3] != start and (trace[3] != trace[2] or
                    sum(cells[trace[3]][case][0] - cells[start][case][0] for case in qualification) <= 0):
                raise ValueError('A promotion must independently qualify the same nominee')
            totals.setdefault(label, Counter()).update(point)
            fitted.prior.add_vector(vectors.setdefault(label, [0] * len(heldout)), grades)
            outcomes.append((trace, point))
        (low_trace, low), (full_trace, full) = outcomes
        traces.append((low_trace, full_trace))
        short_prompt, full_prompt = low_trace[3], full_trace[3]
        diagnostics.update(trials=1, cap13Promotions=int(short_prompt != start),
                           fullPoolPromotions=int(full_prompt != start))
        if short_prompt == full_prompt:
            group = 'same-prompt'
        elif short_prompt == start:
            group = 'full-pool-only-promotion'
        elif full_prompt == start:
            group = 'cap-13-only-promotion'
        else:
            group = 'different-promotions'
        changes.setdefault(group, Counter()).update(trials=1,
                                                    fullPoolPassDelta=full['holdoutPasses'] - low['holdoutPasses'],
                                                    extraFullPoolLookups=full['paidLookups'] - low['paidLookups'])
    return totals, vectors, {'decisionsSha256': digest(traces), 'deploymentChanges': changes, **diagnostics}


def replay(plan, panels, reference):
    totals, cases, subjects, details, changes = {}, {}, {}, {}, {}
    for _, subject, model, matrix in panels:
        name = f'{subject}/{model}'
        cpo, grades, diagnostics = measure_cpo(subject, matrix, plan)
        anchor = reference['panelsAtOriginalCap'][name]
        if any(cpo[frontier.RETAIN][key] != anchor[frontier.RETAIN][key] for key in cost.METRICS):
            raise ValueError('The retained starts must reproduce the original transfer receipt')
        gepa, native_grades = cost.measure_panel(subject, matrix, plan,
                                                {'totals': anchor, 'holdoutCases': len(grades[frontier.RETAIN])})
        controls = tuple(gepa)
        subject_points = subjects.setdefault(subject, {})
        subject_vectors = cases.setdefault(subject, {})
        by_setting = {**grades, **native_grades}
        for label, point in {**cpo, **gepa}.items():
            metrics = {key: point[key] for key in cost.METRICS}
            totals.setdefault(label, Counter()).update(metrics)
            subject_points.setdefault(label, Counter()).update(metrics)
            outcome = by_setting[label]
            fitted.prior.add_vector(subject_vectors.setdefault(label, [0] * len(outcome)), outcome)
        details[name] = {'cpo': cpo, 'heldoutCases': len(grades[frontier.RETAIN]), **diagnostics}
        for group, point in diagnostics['deploymentChanges'].items():
            changes.setdefault(group, Counter()).update(point)
    if any(totals[label] != reference['totals'][label] for label in (*controls, frontier.RETAIN)):
        raise ValueError('The original transfer cost frontier and retained score must reproduce')
    candidate = plan['candidate']
    comparison = frontier.compare(totals, cases, policies=(candidate,), draws=plan['bootstrapDraws'],
                                  seed=plan['bootstrapSeed'], groups={'fixed-gepa-or-retain': controls})[candidate]
    primary = comparison['fixed-gepa-or-retain']
    passed = primary['holdoutPassDifference'] > 0 and primary['pairedRange95'][0] >= 0
    hindsight = fitted.prior.by_subject_ceiling(subjects, controls, {candidate: totals[candidate]['paidLookups']})
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'passedTransferGate': passed,
            'totals': totals, 'panels': details, 'comparison': primary, 'deploymentChanges': changes,
            'subjectTunedGepaHindsight': hindsight[candidate],
            'caseVectorsSha256': digest(cases)}


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
    result = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
