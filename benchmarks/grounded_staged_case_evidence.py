"""Verify staged archives and measure paired sensitivity to the holdout cases."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks import grounded, grounded_staged as staged


def convolve(left, right):
    counts = Counter()
    for a, a_count in left.items():
        for b, b_count in right.items():
            counts[a + b] += a_count * b_count
    return counts


def case_resampling_range(deltas_by_task):
    """Count every within-task resample, keeping each case's repeats together."""
    pooled = Counter({0: 1})
    for deltas in deltas_by_task:
        counts = Counter(deltas)
        if not counts:
            raise ValueError('Case sensitivity requires a nonempty panel for each task')
        panel = Counter({0: 1})
        for _ in deltas:
            panel = convolve(panel, counts)
        pooled = convolve(pooled, panel)

    total = pooled.total()
    cumulative = 0
    endpoints = []
    for delta, count in sorted(pooled.items()):
        cumulative += count
        while len(endpoints) < 2 and 40 * cumulative >= (1, 39)[len(endpoints)] * total:
            endpoints.append(delta)
    return endpoints


def assess(result, gate):
    holdout = result['holdout']
    costs = result['searchCallsByArm']
    panels = {task: {} for task in holdout}
    for task, rows in holdout.items():
        for row in rows:
            panels[task].setdefault(row['id'], []).append(row)
    comparisons = {}
    for arm, verdict in result['outcome']['comparisons'].items():
        by_task = {}
        for task, cases in panels.items():
            by_task[task] = [sum(row['passes']['cpo'] - row['passes'][arm] for row in repeats)
                             for repeats in cases.values()]
        deltas = [delta for panel in by_task.values() for delta in panel]
        comparisons[arm] = {**verdict, 'casesAhead': sum(delta > 0 for delta in deltas),
                            'casesTied': deltas.count(0), 'casesBehind': sum(delta < 0 for delta in deltas),
                            'addedPassesByTask': {task: sum(panel) for task, panel in by_task.items()},
                            'caseResampling95PassDifference': case_resampling_range(by_task.values())}

    deletion_rejections = []
    for task, cases in panels.items():
        for case in cases:
            remaining = {**holdout, task: [row for row in holdout[task] if row['id'] != case]}
            if not staged.grade(remaining, costs, gate)['qualified']:
                deletion_rejections.append(case)
    return {'sealedGateQualified': result['outcome']['qualified'], 'searchCallsByArm': costs,
            'uniqueCasesByTask': {task: len(cases) for task, cases in panels.items()},
            'pairedRepliesPerArm': sum(len(rows) for rows in holdout.values()), 'comparisons': comparisons,
            'singleCaseRemovalsFailingOriginalGate': sorted(deletion_rejections)}


def verify(directory, *, development=None):
    with TemporaryDirectory(prefix='cpo-staged-case-evidence-') as scratch:
        fresh = Path(scratch) / 'verified'
        result = staged.replay(directory, fresh, development=development)
        plan = grounded.load_json((fresh / 'plan.json').read_bytes())
        return {'planSha256': result['planSha256'], 'delivery': result['delivery'],
                'archiveSha256': {name: sha256((fresh / name).read_bytes()).hexdigest()
                                  for name in staged.ARCHIVE_FILES},
                **assess(result, plan['gate'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development', required=True, type=Path)
    parser.add_argument('--confirmation', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    directories = (args.development,) if args.confirmation is None else (args.development, args.confirmation)
    if args.out is not None and (args.out.exists() or any(
            args.out.resolve().is_relative_to(directory.resolve()) for directory in directories)):
        parser.error('Evidence requires a fresh output path outside both archives')
    try:
        report = {'analysis': 'portable-grounded-staged-case-evidence-v1',
                  'analysisSourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
                  'development': verify(args.development)}
        if args.confirmation is not None:
            report['confirmation'] = verify(args.confirmation, development=args.development)
        if args.out is not None:
            staged.save(args.out, report)
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    if args.out is None:
        print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
