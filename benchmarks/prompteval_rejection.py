"""Measure validation-order changes without adding screening lookups."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import pool, prompteval_proxy as proxy, prompteval_transfer as transfer, prompteval_witnesses as witnesses
from cpo import Observation, Row, select_pool
from cpo._contract import digest


ARMS = {'ordered-four': (4, 0), 'screened-four': (4, 4), 'entire-pool': (None, 0)}
CONTROLS = ('gepa-sequential', 'gepa-batched', 'cpo-minibatch')
TIGHT_CAP = 72


def prepare(phase):
    if phase == 'development':
        data, sizes, fingerprint = transfer.read_source()
    elif phase == 'prior-confirmation':
        data, sizes, fingerprint = witnesses.read_source('confirmation')
    else:
        data, sizes, fingerprint = proxy.read_source()
    base = transfer.plan(data, sizes, fingerprint)
    readers = (Path(__file__), Path(proxy.__file__), Path(witnesses.__file__))
    sources = {reader.relative_to(Path(__file__).resolve().parents[1]).as_posix(): sha256(reader.read_bytes()).hexdigest()
               for reader in readers}
    plan = {**base, 'protocol': 'prompteval-adaptive-rejection-v2', 'phase': phase, 'subjects': list(sizes),
            'arms': {name: {'maxChallengers': width, 'screenRows': rows} for name, (width, rows) in ARMS.items()},
            'controls': list(CONTROLS), 'primaryChallengers': 'ordered-four',
            'tightCap': TIGHT_CAP, 'sourceSha256': {**base['sourceSha256'], **sources}}
    return plan, data


def run_arm(matrix, candidates, validation, holdout, cap, *, width, screen, adaptive):
    allowed = set(validation)
    if allowed.intersection(holdout):
        raise ValueError('Validation must be disjoint from holdout')
    observed = {}

    def evaluate(prompt, row):
        case = int(row.id)
        key = prompt, case
        if prompt not in candidates or case not in allowed or key in observed or len(observed) >= cap:
            raise ValueError('A validation lookup exceeded the sealed pool or cap')
        outcome = observed[key] = matrix[int(prompt)][case] == '1'
        return Observation(outcome, {})

    result = select_pool(candidates, [Row(str(case), 'task') for case in validation], evaluate,
                         metric_limit=cap, screen_rows=screen, max_challenges=width, adaptive_rejection=adaptive)
    if result.evaluations != len(observed):
        raise ValueError('Lookup counts do not match the selector')
    if (any((result.prompt, case) not in observed for case in validation)
            or result.validation_passes != sum(observed[result.prompt, case] for case in validation)):
        raise ValueError('The selected prompt must be exactly validated')
    return {'candidate': result.prompt, 'evaluations': result.evaluations,
            'holdoutPasses': sum(matrix[int(result.prompt)][case] == '1' for case in holdout),
            'searchSha256': digest([(prompt, case, value) for (prompt, case), value in observed.items()])}


def compare(matrix, holdout, seed, plan):
    trial = transfer.compare(matrix, holdout, seed)
    baseline = trial['arms']
    trial['arms'] = {control: baseline[control] for control in CONTROLS}
    candidates, validation = trial['candidates'], trial['validation']
    for name, (width, screen) in ARMS.items():
        for adaptive in (False, True):
            tag = 'adaptive-' + name if adaptive else name
            trial['arms'][tag] = run_arm(matrix, candidates, validation, holdout, plan['evaluationLookupLimit'],
                                         width=width, screen=screen, adaptive=adaptive)
    for adaptive in (False, True):
        name = 'tight-adaptive' if adaptive else 'tight-order'
        trial['arms'][name] = run_arm(matrix, candidates, validation, holdout, plan['tightCap'],
                                       width=ARMS[plan['primaryChallengers']][0], screen=0, adaptive=adaptive)
    if trial['arms']['entire-pool'] != baseline['cpo-exact-pool']:
        raise ValueError('Original exact pool replay changed')
    for name, (width, screen) in ARMS.items():
        challengers = len(candidates) - 1
        challenged = challengers if width is None else min(width, challengers)
        max_cost = len(validation) * (1 + challenged) + screen * (challengers - challenged)
        if (max_cost <= plan['evaluationLookupLimit']
                and trial['arms'][name]['candidate'] != trial['arms']['adaptive-' + name]['candidate']):
            raise ValueError('A fully funded race changed its exact winner')
    return trial


def execute(plan, data):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    panels = {}
    for panel in data['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        holdout = plan['holdoutCaseIDs'][subject]
        trials = [compare(matrix, holdout, seed, plan) for seed in plan['seeds']]
        totals, _ = pool.summarize(trials, 'adaptive-ordered-four', CONTROLS)
        variants = [(f'adaptive-{arm}', arm) for arm in ARMS] + [('tight-adaptive', 'tight-order')]
        comparisons = {}
        for arm, control in variants:
            refs = [control] if arm == 'tight-adaptive' else [control, *CONTROLS]
            paired = pool.summarize(trials, arm, refs)[1]
            changed = sum(trial['arms'][arm]['candidate'] != trial['arms'][control]['candidate'] for trial in trials)
            comparisons[arm] = {'comparators': paired, 'changedSelections': changed}
        panels[f'{subject}/{model}'] = {'totals': totals, 'comparisons': comparisons, 'trials': trials}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('development', 'prior-confirmation', 'different-subjects'), required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    report = execute(plan, data)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
