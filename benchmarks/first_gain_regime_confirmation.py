"""Seal exact confirmation cases covering all independent-proposal task regimes."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from math import ceil
from pathlib import Path

from benchmarks import first_gain_independent_proposals as development
from benchmarks import witness_regime_coverage as coverage
from cpo._contract import digest


ROOT = development.parent.ROOT
BASE_SHA = '80b96150569d3be6927f3f6d171d56b0b3b986e1bb210ccfa5b185d2dcfd376f'
BASE_FILE = 'docs/first-gain-independent-proposals-plan-v1.json'
ARMS = ('initial', *development.ARMS)
REPEATS = development.grounded.REPEATS
TALLIES = ('logicalSearchUses', 'attributedSearchRequests')


def case_panels(tasks):
    policy, staged, witness = coverage.policy, coverage.staged, coverage.episode
    historical = policy.cohorts(coverage.grounded.SEED), staged.cohorts()
    older = witness.cohorts()
    earlier_stress = coverage.stress_cases(older, historical)
    earlier_archive = {task: {'earlierStress': rows} for task, rows in earlier_stress.items()}
    isolated = {task: {'confirmation': []} for task in tasks}
    added = coverage.stress_cases(isolated, (tasks, older, earlier_archive, *historical))
    return {task: [{**row, 'id': f'first-gain-confirmation-{task}-{index:02}'}
                   for index, row in enumerate(rows, 1)] for task, rows in added.items()}


def prepare():
    tasks, base = development.prepare()
    raw = (ROOT / BASE_FILE).read_bytes()
    prior = json.loads(raw)
    prior_seal = prior.pop('planSha256')
    if sha256(raw).hexdigest() != BASE_SHA or digest(prior) != prior_seal or digest(base) != prior_seal:
        raise ValueError('Use the sealed independent-proposal development layout')
    panel = case_panels(tasks)
    for task, rows in panel.items():
        available = [row for group in tasks[task].values() for row in group]
        if (tuple(coverage.regime(task, row) for row in rows) != coverage.REGIMES[task]
                or len({row['id'] for row in (*rows, *available)}) != len(rows) + len(available)
                or len({row['input'] for row in (*rows, *available)}) != len(rows) + len(available)):
            raise ValueError('Confirmation needs one input-disjoint case per defined regime')
    paths = ('benchmarks/first_gain_regime_confirmation.py', 'benchmarks/witness_regime_coverage.py')
    request_ceiling = sum(map(len, panel.values())) * REPEATS * len(ARMS)
    plan = {
        'protocol': 'cpo-first-gain-regime-confirmation-v1', 'delivery': 'offline-design-and-gate-rehearsal',
        'developmentPlanSha256': prior_seal, 'developmentManifestSha256': BASE_SHA,
        'sourceSha256': {**base['sourceSha256'],
                         **{name: sha256((ROOT / name).read_bytes()).hexdigest() for name in paths}},
        'candidate': development.FIRST, 'controls': development.CONTROLS, 'repeats': REPEATS,
        'panelSha256': digest(panel), 'casesByTask': {task: len(rows) for task, rows in panel.items()},
        'minimumTaskPasses': {task: ceil(0.75 * REPEATS * len(rows)) for task, rows in panel.items()},
        'minimumAddedPasses': 4, 'efficiencyPercent': 90, 'minimumPassesPerRegime': 1,
        'generationRequestCeiling': request_ceiling,
        'confirmationRule': ('Bind the final prompts and costs only after verified qualifying model development. '
                             'Score all assigned cases and repeats for the initial prompt and every finalist. '
                             'Require all paired quality and cost gates, per-task floors, and an exact pass on '
                             'each regime case. Share only identical prompt, case and repeat requests.'),
    }
    return plan, panel, tasks


def evaluate(plan, panel, outcomes, costs_by_tally):
    """Check a complete finalized ledger of Boolean grades by case and repeat."""
    candidate, controls = plan['candidate'], plan['controls']
    arms = {'initial', candidate, *controls}
    if set(outcomes) != set(panel) or set(costs_by_tally) != set(TALLIES) or any(
            set(costs) != arms - {'initial'} or any(type(cost) is not int or cost < 0 for cost in costs.values())
            for costs in costs_by_tally.values()):
        raise ValueError('Confirmation needs all tasks and both complete development cost tallies')
    staged, failures = {}, {}
    for task, rows in panel.items():
        available = outcomes[task]
        keys = {(row['id'], repeat) for row in rows for repeat in range(plan['repeats'])}
        if set(available) != keys or any(set(grades) != arms or any(type(value) is not bool for value in grades.values())
                                         for grades in available.values()):
            raise ValueError('Confirmation needs all paired cases, repeats and Boolean scores')
        staged[task], failures[task] = [], []
        for row in rows:
            votes = [available[row['id'], repeat] for repeat in range(plan['repeats'])]
            if sum(grades[candidate] for grades in votes) < plan['minimumPassesPerRegime']:
                failures[task].append(row['id'])
            staged[task].extend({'id': row['id'], 'critical': row['critical'],
                                 'passes': {**grades, 'cpo': grades[candidate]}} for grades in votes)
    paired = {tally: development.staged.grade(staged, {**costs, 'cpo': costs[candidate]},
                                              {**plan, 'minimumTaskPasses': 0}, controls=controls)
              for tally, costs in costs_by_tally.items()}
    floor = all(paired[TALLIES[0]]['passesByTask']['cpo'][task] >= minimum
                for task, minimum in plan['minimumTaskPasses'].items())
    qualifies = all(verdict['qualified'] for verdict in paired.values())
    return {'pairedByTally': paired, 'pairedGateMet': qualifies, 'perTaskFloorMet': floor,
            'failedRegimeCases': failures, 'qualified': qualifies and floor and not any(failures.values())}


def scripted(plan, panel, *, target=None, branch=None, failed_repeats=0, shared=True):
    """Score an exact fixture or one shared, schema-valid policy fault."""
    result = {}
    for task, rows in panel.items():
        grades = {}
        for row in rows:
            expected = row['expected']
            matches = task == target and coverage.regime(task, row) == branch
            changed = coverage.mutation(task, expected) if matches else expected
            valid, _ = development.grounded.score(json.dumps(expected), expected)
            disputed, _ = development.grounded.score(json.dumps(changed), expected)
            for repeat in range(plan['repeats']):
                failed = repeat < failed_repeats and matches
                grades[row['id'], repeat] = {
                    arm: disputed if failed and (shared or arm == plan['candidate']) else valid
                    for arm in ARMS
                }
        result[task] = grades
    return result


def rehearse(plan, panel, tasks):
    costs = {tally: {plan['candidate']: 90, **dict.fromkeys(plan['controls'], 100)} for tally in TALLIES}
    baseline = evaluate(plan, panel, scripted(plan, panel), costs)
    if not baseline['qualified']:
        raise ValueError('The exact fixture must meet the confirmation gate')
    measured = {}
    for task, branches in coverage.REGIMES.items():
        counts = Counter()
        for branch in branches:
            for label, failures, shared in (('oneSharedFailedRepeat', 1, True),
                                            ('persistentSharedFault', REPEATS, True),
                                            ('persistentCandidateFault', REPEATS, False)):
                verdict = evaluate(plan, panel, scripted(plan, panel, target=task, branch=branch,
                                                         failed_repeats=failures, shared=shared), costs)
                counts[f'{label}PairedGatePasses'] += verdict['pairedGateMet']
                counts[f'{label}FinalPasses'] += verdict['qualified']
        development_holdout = {coverage.regime(task, row) for row in tasks[task]['holdout']}
        original_reserve = {coverage.regime(task, row) for row in tasks[task]['confirmation']}
        measured[task] = {'caseCount': len(panel[task]), 'originalReserveCoverage': len(original_reserve),
                          'developmentHoldoutCoverage': len(development_holdout),
                          'criticalCaseCount': sum(row['critical'] for row in panel[task]), **counts}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'fixtureQualified': True,
            'tasks': measured, 'rows': panel}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--fixture', metavar='PLAN_SHA256')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, panel, tasks = prepare()
    seal = digest(plan)
    if not args.fixture and not args.out:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.fixture != seal or args.out is None or args.out.exists():
        cli.error('Use the current fixture seal and a fresh output path')
    report = rehearse(plan, panel, tasks)
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
