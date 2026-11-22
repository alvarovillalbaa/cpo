"""Compare immediate validation certificates with the reserved probe batch."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from random import Random

from benchmarks import threshold_precheck_gepa_frontier as prior
from cpo import Observation, Row
from cpo._contract import digest
from cpo import sequential_certificate_cycle as sequential
from cpo import threshold_prechecked_cycle as two_gain


METRICS = prior.cost.METRICS
RETAIN = prior.frontier.RETAIN
POLICIES = {gain: f'immediate-certificate/gain-{gain}' for gain in prior.POLICIES}
REFERENCE = 'docs/threshold-precheck-gepa-frontier-results-v1.json'
REFERENCE_SHA256 = '2f5c498945d4ef5dbe8b4841047449d426769a59b1ede6d07826cd9ca1f58921'


def prepare():
    parent, groups, _, original = prior.prepare()
    reference = prior.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, parent)
    path = Path(__file__)
    sources = (path, Path(sequential.__file__), Path(two_gain.__file__), Path(prior.frontier.__file__))
    plan = {**parent, 'protocol': 'recorded-sequential-certificate-screen-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': REFERENCE_SHA256,
            'sourceSha256': {source.name: sha256(source.read_bytes()).hexdigest() for source in sources},
            'scope': 'Buy an exact certificate immediately on a successful shared probe. '
                     'Continue to the next challenger after an unsuccessful certificate. '
                     'Consider probe failures once remaining candidates cannot be probed and certified. '
                     'Keep the fixed search cap, candidate order, incumbent precheck, separate qualification, '
                     'and original archives. Compare both margins with the corresponding published CPO cycle. '
                     'Bound the hindsight GEPA score at each candidate budget using the previous exact ceilings.'}
    return plan, groups, reference['results'], original


def episode(args, cap, gain, cycle):
    cells, start, roster, cohorts, seed = args
    validation = tuple(Row(str(case), 'validation') for case in cohorts[1])
    qualification = tuple(Row(str(case), 'qualification') for case in cohorts[2])
    called = {}

    def observe(role, prompt, row):
        key = role, prompt, row.id
        if key in called:
            raise ValueError('Each reply must be charged once')
        called[key] = bool(cells[prompt][int(row.id)][0])
        return called[key]

    def qualify(prompt, row, repeat):
        if repeat:
            raise ValueError('The archive pays for a grade once per prompt and qualification case')
        return observe('qualification', prompt, row)

    result = cycle(
        start, roster, validation, qualification,
        lambda prompt, row: Observation(observe('validation', prompt, row), {}),
        metric_limit=cap, qualify=qualify,
        minimum_gain=gain, seed=seed,
    )
    grades = tuple(cells[result.prompt][case][0] for case in cohorts[-1])
    probe_count = sum(role == 'validation' for role, _, _ in called)
    proof_count = len(called) - probe_count
    if (probe_count != result.search.evaluations or probe_count > cap
            or proof_count != result.qualification_evaluations or proof_count > 2 * len(qualification)):
        raise ValueError('Search and qualification must observe their separate allowances')
    if result.search.prompt != start:
        known = {case: grade for (role, prompt, case), grade in called.items()
                 if role == 'validation' and prompt == result.search.prompt}
        incumbent = {case: grade for (role, prompt, case), grade in called.items()
                     if role == 'validation' and prompt == start}
        if sum(known.values()) <= sum(incumbent.values()):
            raise ValueError('A nominee needs a paid validation gain')
    if result.prompt != start:
        exact_gain = sum(cells[result.prompt][case][0] - cells[start][case][0] for case in cohorts[2])
        if exact_gain < gain:
            raise ValueError('A deployment needs the same independent gain')
    metrics = {'holdoutPasses': sum(grades), 'paidLookups': len(called)}
    trace = [(role, prompt, row, passed) for (role, prompt, row), passed in called.items()]
    return metrics, grades, digest(trace), result


def paired_panel(subject, matrix, plan, receipt):
    cells = {str(i): tuple((int(grade), None, False) for grade in row) for i, row in enumerate(matrix)}
    totals, vectors = {}, {}
    stats = {label: Counter() for label in POLICIES.values()}
    paths = {label: [] for label in (*prior.POLICIES.values(), *POLICIES.values())}

    def tally(label, point, grades):
        totals.setdefault(label, Counter()).update(point)
        prior.transfer.fitted.prior.add_vector(vectors.setdefault(label, [0] * len(grades)), grades)

    for seed in plan['seeds']:
        start, roster, cohorts = prior.transfer.archive.transfer.schedule(
            subject, len(matrix[0]), len(matrix), seed, plan,
        )
        args = cells, start, roster, cohorts, seed
        keep = tuple(cells[start][case][0] for case in cohorts[-1])
        tally(RETAIN, {'holdoutPasses': sum(keep), 'paidLookups': 0}, keep)
        for gain, label in POLICIES.items():
            baseline = prior.POLICIES[gain]
            old, original_grades, old_path, original = episode(
                args, plan['screenCap'], gain, two_gain.run_threshold_prechecked_cycle,
            )
            new, grades, new_path, candidate = episode(
                args, plan['screenCap'], gain, sequential.run_sequential_certificate_cycle,
            )
            tally(baseline, old, original_grades)
            tally(label, new, grades)
            paths[baseline].append(old_path)
            paths[label].append(new_path)
            change = new['holdoutPasses'] - old['holdoutPasses']
            stats[label].update(
                revisedNominees=int(original.search.prompt != candidate.search.prompt),
                revisedDeployments=int(original.prompt != candidate.prompt),
                additionalPasses=max(0, change), lostPasses=max(0, -change),
                validationLookupsSaved=original.search.evaluations - candidate.search.evaluations,
                proofLookupsSaved=original.qualification_evaluations - candidate.qualification_evaluations,
            )
    fingerprints = {label: digest(path) for label, path in paths.items()}
    if any(fingerprints[label] != path for label, path in receipt.items()):
        raise ValueError('The two public CPO controls must reproduce their original paid callbacks')
    return totals, vectors, stats, {label: fingerprints[label] for label in POLICIES.values()}


def paired_effect(subjects, candidate, control, plan):
    by_subject = [tuple(left - right for left, right in zip(rows[candidate], rows[control], strict=True))
                  for _, rows in sorted(subjects.items())]
    rng = Random(plan['bootstrapSeed'])
    draws = [sum(sum(rng.choices(cases, k=len(cases))) for cases in by_subject)
             for _ in range(plan['bootstrapDraws'])]
    return {'holdoutPassDifference': sum(map(sum, by_subject)),
            'pairedRange95': prior.frontier.interval(draws)}


def hindsight_bounds(reference, budget):
    ceilings = reference['subjectTunedGepaHindsight']
    published = reference['totals']
    feasible = [point['holdoutPasses'] for point in ceilings.values() if point['paidLookups'] <= budget]
    upper = [point['holdoutPasses'] for label, point in ceilings.items() if published[label]['paidLookups'] >= budget]
    lower = max([published[RETAIN]['holdoutPasses'], *feasible])
    bound = min(upper, default=None)
    if bound is not None and lower > bound:
        raise ValueError('The attained GEPA lower bound cannot exceed its budget ceiling')
    return {'lowerPasses': lower, 'upperPasses': bound}


def measure_cohort(panels, plan, reference, receipt):
    totals, subjects, fingerprints = {}, {}, {}
    stats = {label: Counter() for label in POLICIES.values()}
    for subject, model, matrix in panels:
        panel = f'{subject}/{model}'
        points, vectors, changes, fingerprints[panel] = paired_panel(
            subject, matrix, plan, receipt['panelPathHashes'][panel],
        )
        scores = subjects.setdefault(subject, {})
        for label, point in points.items():
            totals.setdefault(label, Counter()).update(point)
            prior.transfer.fitted.prior.add_vector(scores.setdefault(label, [0] * len(vectors[label])), vectors[label])
        for label, counts in changes.items():
            stats[label].update(counts)
    if any(totals[label] != reference['totals'][label] for label in (RETAIN, *prior.POLICIES.values())):
        raise ValueError('Both fixed-margin budgets and retained starts must match the published report')
    native = {label: point for label, point in reference['totals'].items() if label not in totals}
    comparisons = {}
    for gain, label in POLICIES.items():
        baseline = prior.POLICIES[gain]
        point = totals[label]
        change = stats[label]
        if (change['additionalPasses'] - change['lostPasses'] != point['holdoutPasses'] - totals[baseline]['holdoutPasses']
                or change['validationLookupsSaved'] + change['proofLookupsSaved']
                != totals[baseline]['paidLookups'] - point['paidLookups']):
            raise ValueError('Every cost and held-out score change must reconcile')
        affordable = {name: old for name, old in native.items() if old['paidLookups'] <= point['paidLookups']}
        affordable[RETAIN] = totals[RETAIN]
        best = prior.frontier.highest_scoring(
            {name: old['paidLookups'] for name, old in affordable.items()},
            {name: old['holdoutPasses'] for name, old in affordable.items()}, affordable,
        )
        comparisons[label] = {
            'pairedAgainstPublished': paired_effect(subjects, label, baseline, plan),
            'pairedAgainstStarts': paired_effect(subjects, label, RETAIN, plan),
            'bestNativePointAtObservedBudget': {'setting': best, **affordable[best]},
            'nativeSubjectHindsightBounds': hindsight_bounds(reference, point['paidLookups']),
        }
    return {'totals': totals, 'changes': stats, 'comparisons': comparisons, 'panelPathHashes': fingerprints}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, reference, receipt = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh output path')
    outcomes = {cohort: measure_cohort(panels, plan, reference[cohort], receipt[cohort])
                for cohort, panels in groups.items()}
    with args.out.open('x') as destination:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': outcomes},
                  destination, indent=2, sort_keys=True)
        destination.write('\n')


if __name__ == '__main__':
    main()
