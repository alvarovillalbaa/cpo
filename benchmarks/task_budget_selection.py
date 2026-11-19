"""Test whether archived settings transfer to a task excluded from selection."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path

from benchmarks import paid_budget_frontier as frontier
from cpo._contract import digest, unique_object


ROOT = Path(__file__).resolve().parents[1]
FRONTIER_SHA256 = '1ba8cc12dd25bd11b050ad28b006621af1cc871825d2ea7536a6b9a250935f5b'
ARCHIVE_SHA256 = frontier.CPO_REPORT_SHA
MATCHED_SHA256 = frontier.gepa.SOURCE_SHA256
CPO = frontier.gepa.CPO
REFERENCE = (CPO, 52)
ARCHIVE = ('paired-wins', 'require-win', 'archive-disabled')
TWO_READS = frontier.gepa.reference.CPO_METHODS[1]
GEPA = frontier.gepa.METHODS
FAMILIES = {
    'cpo': (CPO, TWO_READS, *ARCHIVE),
    'gepa': GEPA,
    'mixed': (CPO, TWO_READS, *ARCHIVE, *GEPA),
}
SPLITS = ('other-tasks', 'same-benchmark', 'other-cohorts')


def load_report(filename, expected):
    raw = (ROOT / 'docs' / filename).read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError('A published input report differs')
    return json.loads(raw, object_pairs_hook=unique_object)


def prepare():
    measured = load_report('paid-budget-frontier-results-v1.json', FRONTIER_SHA256)
    archives = load_report('archive-complementarity-transfer-results-v1.json', ARCHIVE_SHA256)
    matched = load_report('bounded-transfer-matched-cost-results-v1.json', MATCHED_SHA256)
    parent, inputs = frontier.prepare()
    if digest(parent) != measured['planSha256']:
        raise ValueError('The realized-cost frontier plan differs')
    tasks = {}
    seen = set()
    for cohort, (original, panels, _, _) in inputs.items():
        for panel in panels:
            subject, model = panel['subject'], panel['model']
            name = f'{subject}/{model}'
            benchmark = subject.partition('-')[0] if cohort != 'mmlu' else 'mmlu'
            if name in seen or benchmark not in ('mmlu', 'bbh', 'lmentry'):
                raise ValueError('Transfer panels must be distinct and assigned to a known benchmark')
            seen.add(name)
            task = tasks.setdefault(subject, {'cohort': cohort, 'benchmark': benchmark, 'maxPasses': 0,
                                              'options': {}, 'models': []})
            task['models'].append(model)
            task['maxPasses'] += len(original['holdoutCaseIDs'][subject]) * len(original['seeds'])
            options = {(method, int(cap)): row for method, caps in measured['panels'][name].items()
                       for cap, row in caps.items()}
            policy = archives['runs'][cohort]['report']['panels'][name]['policies']
            options.update({(variant, 52): policy[variant] for variant in ARCHIVE})
            baseline = matched['runs'][cohort]['report']['panels'][name]['totals']
            options[TWO_READS, 52] = baseline[TWO_READS]
            if any(options[REFERENCE][k] != policy['recency'][k] or options[REFERENCE][k] != baseline[CPO][k]
                   for k in ('holdoutPasses', 'paidLookups')):
                raise ValueError('The source reports disagree about the reference CPO setting')
            for option, row in options.items():
                task['options'].setdefault(option, Counter()).update(
                    holdoutPasses=row['holdoutPasses'], paidLookups=row['paidLookups'])
    if seen != measured['panels'].keys() or any(len(task['models']) != 2 for task in tasks.values()):
        raise ValueError('Expected the complete, paired subject set')
    plan = {
        'protocol': 'cpo-task-budget-selection-v1', 'parentPlanSha256': measured['planSha256'],
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'frontierSha256': FRONTIER_SHA256, 'archiveSha256': ARCHIVE_SHA256, 'matchedCostsSha256': MATCHED_SHA256,
        'reference': {'method': CPO, 'cap': 52}, 'splits': list(SPLITS),
        'primarySplit': 'same-benchmark', 'menus': FAMILIES, 'subjects': sorted(tasks),
        'ranking': 'Mean task accuracy at mean relative training cost at most one, then lower cost.',
        'scope': 'Held-out task selection with both model panels excluded from fitting. Replay sealed points.',
    }
    return plan, tasks, measured['combined']['subjectGepaOracleAtCpoCost']['52']


def training_subjects(tasks, target, split):
    current = tasks[target]
    return tuple(name for name, task in sorted(tasks.items()) if name != target and (
        split == 'other-tasks'
        or (split == 'same-benchmark' and task['benchmark'] == current['benchmark'])
        or (split == 'other-cohorts' and task['cohort'] != current['cohort'])
    ))


def choose_setting(training, methods):
    """Rank settings only from the provided tasks, weighting tasks equally."""
    tasks = tuple(training)
    if not tasks:
        raise ValueError('Each fold requires training tasks')
    candidates = []
    for option in tasks[0]['options']:
        if option[0] not in methods:
            continue
        cost = sum(Fraction(task['options'][option]['paidLookups'], task['options'][REFERENCE]['paidLookups'])
                   for task in tasks) / len(tasks)
        if cost <= 1:
            accuracy = sum(Fraction(task['options'][option]['holdoutPasses'], task['maxPasses'])
                           for task in tasks) / len(tasks)
            candidates.append((accuracy, cost, option))
    if not candidates:
        raise ValueError('No setting met the relative cost bound on the training tasks')
    accuracy, cost, option = min(candidates, key=lambda row: (-row[0], row[1], row[2]))
    return option, {'accuracy': str(accuracy), 'relativeCost': str(cost)}


def evaluate_folds(tasks, split, methods):
    folds = {}
    total = Counter()
    for subject in sorted(tasks):
        training = training_subjects(tasks, subject, split)
        option, fit = choose_setting((tasks[name] for name in training), methods)
        score = tasks[subject]['options'][option]
        total.update(score)
        folds[subject] = {'trainingSubjects': list(training), 'method': option[0], 'cap': option[1],
                          'trainingMetrics': fit, 'realized': score}
    return {'totals': total, 'folds': folds}


def replay(plan, tasks, previous_gepa):
    reference = Counter()
    for task in tasks.values():
        reference.update(task['options'][REFERENCE])
    oracle = {}
    for family, methods in FAMILIES.items():
        choices = {
            name: [{'method': method, 'cap': cap, **row} for (method, cap), row in task['options'].items()
                   if method in methods]
            for name, task in tasks.items()
        }
        oracle[family] = frontier.best_subject_allocation(choices, reference['paidLookups'])
    if any(oracle['gepa'][key] != previous_gepa[key] for key in ('holdoutPasses', 'paidLookups')):
        raise ValueError('The earlier GEPA hindsight bound did not reproduce')
    return {'plan': plan, 'planSha256': digest(plan), 'reference': reference, 'subjectHindsight': oracle,
            'splits': {split: {family: evaluate_folds(tasks, split, methods) for family, methods in FAMILIES.items()}
                       for split in SPLITS}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    report = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
