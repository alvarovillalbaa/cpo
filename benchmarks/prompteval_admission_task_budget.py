"""Stress the one-admission result with task-specific optimizer budgets."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import paid_budget_frontier as frontier
from benchmarks import prompteval_narrow_native_admission as narrow
from benchmarks import task_budget_selection as selection
from cpo._contract import digest


ROOT = narrow.transfer.ROOT
CPO = narrow.CPO
START = narrow.START
SPLITS = selection.SPLITS
SCORE_FIELDS = ('holdoutPasses', 'paidLookups')
REFERENCE = ROOT / 'docs/prompteval-narrow-native-admission-results-v1.json'
REFERENCE_SHA = '16e1dc37d6a088d2b4d6f1b3cb58e4153460490d10234ddb6c5c53fc49fd7092'


def inputs():
    design, baseline, panels, matched = narrow.prepare()
    raw = REFERENCE.read_bytes()
    observed = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA or observed['planSha256'] != digest(design):
        raise ValueError('Use the original sealed narrower-validation results')
    tasks, panel_keys, caps = {}, set(), {START: 0}
    caps.update({arm: values['searchCap'] for arm, values in design['conditions'].items()})
    matched_plan = json.loads(narrow.REFERENCE.read_bytes())['plan']
    caps.update(matched_plan['searchCaps'])
    caps.update({narrow.matched.first(arm): cap for arm, cap in matched_plan['searchCaps'].items()})
    for panel in panels:
        subject, model = panel['subject'], panel['model']
        benchmark = panel['benchmark'].lower()
        key = f'{subject}/{model}'
        if key in panel_keys or benchmark not in ('bbh', 'lmentry'):
            raise ValueError('Tasks need distinct panel identities and a known benchmark')
        panel_keys.add(key)
        held = narrow.REPLAY.transfer.holdout(subject, len(panel['caseIDs']))
        physical = tuple(panel['caseIDs'][index] for index in held)
        task = tasks.setdefault(subject, {'benchmark': benchmark, 'cohort': benchmark, 'caseIDs': physical,
                                          'options': {}, 'maxPasses': 0, 'models': []})
        if task['caseIDs'] != physical or task['benchmark'] != benchmark or model in task['models']:
            raise ValueError('A task must preserve the same case IDs across its model panels')
        task['models'].append(model)
        task['maxPasses'] += len(held) * len(baseline['schedule']['seeds'])
        options = {arm: {name: row[name] for name in SCORE_FIELDS} for arm, row in observed['panels'][key].items()}
        for arm, row in matched['panels'][key].items():
            amounts = {name: row[name] for name in SCORE_FIELDS}
            if options.setdefault(arm, amounts) != amounts:
                raise ValueError('The receipts disagree about a repeated control')
        for arm, row in options.items():
            task['options'].setdefault((arm, caps[arm]), Counter()).update(row)
    if panel_keys != observed['panels'].keys() or panel_keys != matched['panels'].keys():
        raise ValueError('Both receipts must cover the same archive panels')
    if any(len(task['models']) != 2 for task in tasks.values()) or len({t['maxPasses'] for t in tasks.values()}) != 1:
        raise ValueError('The exact integer frontier requires balanced task denominators')
    menus = {
        'native-one-admission': (START, *sorted(arm for arm in caps if arm.startswith('gepa-')
                                                and arm.endswith('/one-admission'))),
        'native-all-measured': (START, *sorted(arm for arm in caps if arm.startswith('gepa-'))),
        'cpo': (START, CPO, narrow.matched.CPO),
    }
    menus['mixed'] = tuple(dict.fromkeys((*menus['native-all-measured'], *menus['cpo'])))
    reference = (CPO, caps[CPO])
    if any(task['options'].keys() != tasks[min(tasks)]['options'].keys() or task['options'][reference]['paidLookups'] <= 0
           for task in tasks.values()):
        raise ValueError('Every task requires the same measured menu and a nonzero CPO reference cost')
    code = (Path(__file__), Path(frontier.__file__), Path(selection.__file__))
    plan = {'protocol': 'prompteval-admission-task-budget-v1', 'narrowerPlanSha256': digest(design),
            'narrowerReceiptSha256': REFERENCE_SHA, 'matchedReceiptSha256': narrow.REFERENCE_SHA,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in code},
            'reference': reference, 'menus': menus, 'trainingSplits': SPLITS, 'tasks': sorted(tasks),
            'scope': ('Keep both model panels together in every task. Compute hindsight upper bounds at the '
                      'reference cost and choose settings without the target task in each held-out fold.')}
    return plan, tasks, observed['totals'][CPO]


def match_score(tasks, choices, target):
    """Find the lowest native cost reaching the target via the same exact frontier."""
    maxima = {task: max(row['paidLookups'] for row in rows) for task, rows in choices.items()}
    possible = sum(task['maxPasses'] for task in tasks.values())
    flipped = {name: [{**row, 'paidLookups': tasks[name]['maxPasses'] - row['holdoutPasses'],
                       'holdoutPasses': maxima[name] - row['paidLookups']} for row in entries]
               for name, entries in choices.items()}
    result = frontier.best_subject_allocation(flipped, possible - target)
    if result is None:
        return None
    return {**result, 'paidLookups': sum(maxima.values()) - result['holdoutPasses'],
            'holdoutPasses': possible - result['paidLookups']}


def execute(plan, tasks, expected):
    reference = tuple(plan['reference'])
    base = sum((task['options'][reference] for task in tasks.values()), Counter())
    maximum = sum(task['maxPasses'] for task in tasks.values())
    if any(base[field] != expected[field] for field in SCORE_FIELDS) or str(Fraction(base['holdoutPasses'], maximum)) != expected['macroAccuracy']:
        raise ValueError('The task aggregates disagree with the published CPO reference')
    budget, score = base['paidLookups'], base['holdoutPasses']
    menus = {}
    for menu, methods in plan['menus'].items():
        choices = {name: [{'method': arm, 'cap': cap, **row} for (arm, cap), row in task['options'].items()
                          if arm in methods] for name, task in tasks.items()}
        with patch.object(selection, 'REFERENCE', reference):
            held = {split: selection.evaluate_folds(tasks, split, methods) for split in plan['trainingSplits']}
        menus[menu] = {'bestAtReferenceBudget': frontier.best_subject_allocation(choices, budget),
                       'leastCostToMatchReferenceScore': match_score(tasks, choices, score), 'heldOutTasks': held}
    return {'plan': plan, 'planSha256': digest(plan), 'referenceTotals': base, 'possibleHoldoutPasses': maximum,
            'menus': menus, 'newProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs_to_run = inputs()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Use the current plan seal and a fresh output path')
    result = execute(plan, *inputs_to_run)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
