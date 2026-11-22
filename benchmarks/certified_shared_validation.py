"""Replay exact shortlist decisions at lower validation cost."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from benchmarks import shared_validation_split_safe_transfer as prior
from cpo import certified_shared_validation_cycle as certified
from cpo._contract import digest


PREDECESSORS = {
    'BBH': ('bbh', '818c79dccdc6c92b9cf8d096a4fece76ed6910765e841d6a6f88db9b0f4b69f3'),
    'BBH/seen-task': ('bbh-seen-task', '0526f1cefde090232fff4538b230dfc7eab146201e9eed427b47ed4a548ba18e'),
    'BBH/new-task': ('bbh-new-task', '7ffd1fb082bde28bf41989de935f2d960429dd43d5062b87c590a7ef09a23462'),
    'LMentry': ('lmentry', 'f849048d65f5d59e625472b7b92954ebd5e1ab1fc5ff35313b95b0a339992bd1'),
    'LMentry/seen-task': ('lmentry-seen-task', '7398fab10d6fd1d47058ff83310ccd48a1d79b6b89099860225a09b21efb48a3'),
    'LMentry/new-task': ('lmentry-new-task', '35809d042423f5907887ca915f2a72f8ad9ae425885933f8c30435346f974954'),
    'earlier-screen-cohort': ('earlier-screen-cohort', 'e36bca05ca53ba6ffae676788f2bc950f09daca370e4ff7df788db49fd12ed10'),
    'disjoint-transfer-cohort': ('disjoint-transfer-cohort', '4d03a0543cafe5a6d7c17563e6088b498f62e0397c3f16cd8ffd7224612af2c0'),
}


def prepare():
    parent, panels, controls, _, _, _ = prior.prepare()
    read = prior.paired.frontier.cost.prior.baseline.read_reference
    references = {cohort: read(f'docs/shared-validation-split-safe-{name}-results-v1.json', sha,
                               {**parent, 'cohort': cohort})['results']
                  for cohort, (name, sha) in PREDECESSORS.items()}
    plan = {**parent, 'protocol': 'certified-shared-validation-v1', 'parentPlanSha256': digest(parent),
            'parentResultSha256': {key: sha for key, (_, sha) in PREDECESSORS.items()},
            'shortlistSourceSha256': {path.name: sha256(path.read_bytes()).hexdigest()
                                      for path in (Path(__file__), Path(certified.__file__))},
            'scope': 'Preserve the wide nonloss shortlist decisions and exact qualification receipt. '
                     'Use optimistic scores to stop buying challenger replies once the funded cut is fixed. '
                     'Keep the old logical funding decisions and leave the actual savings unspent. '
                     'Bound GEPA at the lower cost using the frozen split-safe attainable points.'}
    return plan, panels, controls, references


def compare_trial(cells, start, roster, roles, seed, cap, gain):
    args = cells, start, roster, roles, seed, cap, gain
    primary = prior.frozen.PRIMARY
    eager, before = prior.frozen.execute_trial(primary, args)
    actual, after = prior.frozen.paired.cycle.execute_path(certified.run_certified_shared_validation_cycle, *args)
    if ((actual.search.prompt, actual.search.finalist, actual.qualification)
            != (eager.search.prompt, eager.search.finalist, eager.qualification)):
        raise ValueError('The charged reads must preserve the exact nomination and qualification decision')
    if not after.items() <= before.items():
        raise ValueError('The shortlist cannot introduce a new paid reply')
    for role, prompt, _ in before.keys() - after.keys():
        if role != 'validation' or prompt in (start, eager.search.finalist):
            raise ValueError('Only replies from eliminated challengers can be omitted')
    prior.frozen.audit_trial(cells, start, roles, actual, after, gain, primary)
    old, grades, old_path = prior.paired.reference.point(cells, roles[-1], eager, before)
    new, actual_grades, new_path = prior.paired.reference.point(cells, roles[-1], actual, after)
    if actual_grades != grades:
        raise ValueError('Every individual holdout grade must be preserved')
    return {'holdoutPasses': old['holdoutPasses'], 'eagerLookups': old['paidLookups'],
            'certifiedLookups': new['paidLookups'], 'eagerValidationLookups': eager.search.evaluations,
            'certifiedValidationLookups': actual.search.evaluations, 'paths': 1,
            'pathsWithSavings': int(len(after) < len(before)), 'nominees': int(actual.search.finalist is not None),
            'deployments': int(actual.promoted)}, old_path, new_path


def measure(panels, plan, controls, reference):
    prior_comparisons = reference['comparisons']
    totals = {label: Counter() for label in controls.values()}
    fingerprints = {}
    retained = 0
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        traces = {label: ([], []) for label in controls.values()}
        panel = f'{subject}/{model}'
        for seed in plan['seeds']:
            start, roster, roles = prior.paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            retained += sum(cells[start][case] for case in roles[-1])
            for gain, label in controls.items():
                point, old_path, new_path = compare_trial(cells, start, roster, roles, seed, plan['fullRosterCap'], gain)
                totals[label].update(point)
                traces[label][0].append(old_path)
                traces[label][1].append(new_path)
        fingerprints[panel] = {}
        for label, (before, after) in traces.items():
            if digest(before) != reference['panelPathHashes'][panel][label][prior.frozen.PRIMARY]:
                raise ValueError('The eager archive must reproduce its exact paid path')
            fingerprints[panel][label] = digest(after)

    attainments = [comparison['splitSafeCombined'] for comparison in prior_comparisons.values()]
    for label, point in totals.items():
        original = prior_comparisons[label]['cpo']
        if (point['eagerLookups'], point['holdoutPasses']) != (original['paidLookups'], original['holdoutPasses']):
            raise ValueError('The published costs and scores must reconcile')
        saved = point['eagerLookups'] - point['certifiedLookups']
        if saved != point['eagerValidationLookups'] - point['certifiedValidationLookups']:
            raise ValueError('Every saved lookup must be from validation')
        point['savedLookups'] = saved
        affordable = [p['holdoutPasses'] for p in attainments if p['paidLookups'] <= point['certifiedLookups']]
        # The maximum at a higher budget also bounds every lower budget from above.
        point['splitSafeGepaPassLowerBound'] = max([retained, *affordable])
        point['splitSafeGepaPassUpperBound'] = prior_comparisons[label]['splitSafeCombined']['holdoutPasses']
    return {'comparisons': totals, 'certifiedPanelPathHashes': fingerprints}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels, controls, references = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh output path')
    result = {cohort: measure(panels[cohort], plan, controls, reference) for cohort, reference in references.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': result},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
