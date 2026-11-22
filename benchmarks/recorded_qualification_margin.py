"""Test a qualification gain that stays positive after omitting one case."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_one_failure_screen_transfer as transfer
from cpo._contract import digest
from cpo.paired_qualification import QualificationDecision, QualificationObservation


early, cost, frontier = transfer.prior, transfer.cost, transfer.frontier
adapter = early.calibrated.adapter
BASELINE = 'complete-panel/13'
CANDIDATE = 'two-net-qualification-gains'
EARLIER = 'earlier-screen-cohort'
TRANSFER = 'disjoint-transfer-cohort'
TRANSFER_REPORT = 'docs/recorded-one-failure-screen-transfer-results-v1.json'
TRANSFER_SHA256 = 'e4f2ac401077b83705fa79befa036af71d00fb65e66b1ae625af9900f42b288d'


def minimum_two(incumbent, challenger, rows, observe, prefix, validation_counts, seed, mode):
    if (mode != adapter.EXPECTED or not rows or len({row.family for row in rows}) != 1
            or any(row.critical for row in rows) or len({row.id for row in rows}) != len(rows)
            or tuple(prefix) != tuple(row.id for row in rows[:len(prefix)])
            or any(type(value) is not bool for value in prefix.values())):
        raise ValueError('Use expected-cost qualification on one noncritical panel with a paid incumbent prefix')
    proof = adapter.proof
    rates = (4 - proof._pass_rate(*validation_counts[0]), proof._pass_rate(*validation_counts[1]))
    observations = [QualificationObservation(incumbent, case, 0, passed) for case, passed in prefix.items()]
    sizes = (len(rows),)
    state = ((len(prefix), 0, sum(not value for value in prefix.values())),)
    candidates = incumbent, challenger
    while True:
        low, high = proof._bounds(sizes, state)
        status = proof._settled(low, high, 2)
        if status is not None:
            winner = challenger if status == 'promoted' else incumbent
            return QualificationDecision(status, winner, tuple(observations), low[0], high[0])
        _, (_, side) = proof._minimum_expected_reads(sizes, rates, 2, state)
        row = rows[state[0][side]]
        passed = observe(candidates[side], row, 0)
        if type(passed) is not bool:
            raise ValueError('Qualification requires exact boolean replies')
        observations.append(QualificationObservation(candidates[side], row.id, 0, passed))
        state = proof._advance(state, 0, side, passed == bool(side))


def prepare():
    older, original_panels, native, *_ = early.prepare()
    target, transfer_panels = transfer.prepare()
    read = cost.prior.baseline.read_reference
    original = read(transfer.PARENT, transfer.PARENT_SHA256, older)
    target_reference = read(TRANSFER_REPORT, TRANSFER_SHA256, target)
    settings = ('caseCounts', 'seeds', 'challengers', 'searchCap', 'minimumSearchCap', 'gepaVersion',
                'bootstrapSeed', 'bootstrapDraws', 'fixedCpoCaps')
    if any(older[key] != target[key] for key in settings if key != 'fixedCpoCaps'):
        raise ValueError('The validation, qualification and evaluation schedules must agree')
    paths = (Path(__file__), Path(early.__file__), Path(adapter.__file__), Path(adapter.proof.__file__))
    plan = {**{key: target[key] for key in settings}, 'protocol': 'recorded-qualification-margin-v1',
            'originalPlanSha256': digest(older), 'originalReceiptSha256': transfer.PARENT_SHA256,
            'transferPlanSha256': digest(target), 'transferReceiptSha256': TRANSFER_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'baseline': BASELINE, 'candidate': CANDIDATE, 'minimumQualificationGain': 2, 'primaryCohort': TRANSFER,
            'gate': 'positive observed margin and nonnegative paired lower endpoint against the strongest '
                    'affordable native GEPA, fixed CPO, published screen, or retained starts',
            'scope': 'Keep the cap-13 full-panel-reserve screen, its nominee, incumbent precheck and proof '
                     'panel fixed. Require a two-pass independent qualification gain under the original '
                     'maximum proof budget with expected-cost scheduling and paid prefix credit. Evaluate '
                     'both already-scored, mutually disjoint archived MMLU cohorts. Compare realized search '
                     'plus proof lookups against the previous screen, both native GEPA modes and fixed CPO.'}
    return plan, {EARLIER: [panel[1:] for panel in original_panels], TRANSFER: transfer_panels}, native, {
        EARLIER: original, TRANSFER: target_reference}


def verify_panel(cohort, subject, model, matrix, plan, native, reference):
    panel = f'{subject}/{model}'
    if cohort == TRANSFER:
        points, vectors, gepa, detail = transfer.measure_panel(subject, matrix, plan)
        if detail != reference['panels'][panel]:
            raise ValueError('The transfer qualification and native traces must reproduce')
        if any(sum(vectors[label]) != point['holdoutPasses'] for label, point in points.items()):
            raise ValueError('The transfer scores must reconcile to their panel vectors')
        return points, vectors, gepa
    cpo, scores, events, traces, _, _ = early.measure_cpo(subject, matrix, plan)
    anchor = reference['panels'][panel]
    if events != anchor['events'] or traces != anchor['decisionTracesSha256']:
        raise ValueError('The original screen and qualification decisions must reproduce')
    gepa, native_scores = cost.measure_panel(
        subject, matrix, plan, {'totals': native['panelsAtOriginalCap'][panel],
                                'holdoutCases': len(scores[frontier.RETAIN])})
    return {**cpo, **gepa}, {**scores, **native_scores}, tuple(gepa)


def measure_margin(subject, matrix, plan):
    cells = {str(index): tuple((int(passed), None, False) for passed in row) for index, row in enumerate(matrix)}
    counts = Counter()
    totals, vector, traces = Counter(), [], []
    for seed in plan['seeds']:
        start, roster, cohorts = transfer.fixed.archive.transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
        args = cells, start, roster, cohorts, seed
        original, prior_trace, _, _ = early.trial(args, 'complete-panel', transfer.CAP)
        with patch.object(adapter, 'qualify_with_prefix', minimum_two):
            point, trace, grades, _ = early.trial(args, 'complete-panel', transfer.CAP)
        if trace[:3] != prior_trace[:3] or point['searchLookups'] != original['searchLookups']:
            raise ValueError('The stronger qualification must keep every paid search and nominee')
        nominee, deployed = trace[2:4]
        proof = [cells[nominee][case][0] - cells[start][case][0] for case in cohorts[2]]
        expected = nominee if sum(proof) >= 2 else start
        if deployed != expected or (deployed != start and any(sum(proof) - grade <= 0 for grade in proof)):
            raise ValueError('A promotion must retain a strict gain after any single proof case is omitted')
        if deployed != start and prior_trace[3] != deployed:
            raise ValueError('The margin cannot add a promotion')
        difference = point['holdoutPasses'] - original['holdoutPasses']
        counts.update(trials=1, priorPromotions=int(prior_trace[3] != start), promotions=int(deployed != start),
                      vetoedPromotions=int(deployed != prior_trace[3]), extraPasses=difference,
                      gainsFromVeto=max(0, difference), lossesFromVeto=max(0, -difference),
                      proofLookupsSaved=original['qualificationLookups'] - point['qualificationLookups'])
        totals.update({metric: point[metric] for metric in cost.METRICS})
        if not vector:
            vector = [0] * len(grades)
        transfer.fixed.fitted.prior.add_vector(vector, grades)
        traces.append(trace)
    return totals, vector, counts, digest(traces)


def replay_cohort(cohort, panels, plan, native, reference):
    totals, subjects, details = {}, {}, {}
    events = Counter()
    for subject, model, matrix in panels:
        points, vectors, native_labels = verify_panel(cohort, subject, model, matrix, plan, native, reference)
        point, scores, counts, trace = measure_margin(subject, matrix, plan)
        rows = subjects.setdefault(subject, {})
        for label, measured in {**points, CANDIDATE: point}.items():
            totals.setdefault(label, Counter()).update(measured)
            grades = scores if label == CANDIDATE else vectors[label]
            transfer.fixed.fitted.prior.add_vector(rows.setdefault(label, [0] * len(grades)), grades)
        events.update(counts)
        details[f'{subject}/{model}'] = {'events': counts, 'traceSha256': trace}
    if any(totals[label] != point for label, point in reference['totals'].items()):
        raise ValueError('The previously published scores and lookup costs must reproduce')
    if any(sum(sum(rows[label]) for rows in subjects.values()) != point['holdoutPasses'] for label, point in totals.items()):
        raise ValueError('The paired case vectors must reconcile to all point results')
    strict = tuple(label for label in totals if label.startswith(f'{transfer.fixed.POLICY}/'))
    screens = tuple(reference['totals']) if cohort == EARLIER else transfer.METHODS
    compare = frontier.compare(totals, subjects, policies=(CANDIDATE,), draws=plan['bootstrapDraws'],
                               seed=plan['bootstrapSeed'], groups={'native-gepa': native_labels,
                                                                  'prior-screen': (BASELINE,),
                                                                  'joint': (*native_labels, *strict, *screens)})[CANDIDATE]
    joint = compare['joint']
    return {'totals': {label: totals[label] for label in (CANDIDATE, BASELINE, frontier.RETAIN)},
            'events': events, 'comparison': compare, 'panels': details, 'caseVectorsSha256': digest(subjects),
            'passedArchiveGate': joint['holdoutPassDifference'] > 0 and joint['pairedRange95'][0] >= 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, native, references = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    results = {cohort: replay_cohort(cohort, panels, plan, native, references[cohort])
               for cohort, panels in groups.items()}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
