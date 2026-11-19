"""Compare one-finalist screens on the frozen 12-case transfer schedule."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_archive_cycles as archive, prompteval_continuous as continuous
from benchmarks import prompteval_round_reserve as attribution, prompteval_validation_size as selection
from benchmarks import prompteval_validation_transfer as transfer
from cpo import Result, cycle
from cpo._contract import digest, unique_object
from cpo.single_finalist import select_single_finalist


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '64041b252305c0666b9e7afd70c7965ab74e2df1d3f8fd3670beb3915929097b'
POLICIES = ('ordered', 'gain-first', 'first-gain')
METHODS = tuple(f'{method}.runner-up' for method in archive.METHODS)


def screened_episode(matrix, held, seed, original, policy):
    upstream, sealed_schedule = continuous.step, continuous.schedule
    rows, cap = transfer.DESIGNS['candidate']

    def schedule(*args):
        return selection.narrow_schedule(*sealed_schedule(*args), rows)

    def step(method, contents, incumbent, layout, plan):
        if method != archive.METHODS[0]:
            return attribution.attributed_step(upstream, method, contents, incumbent, layout, plan, fixed_round=False)

        def search(initial, _train, validation, evaluate, _propose, *, metric_limit, **_):
            selected = select_single_finalist(initial, layout['alternatives'], validation, evaluate,
                                              metric_limit=metric_limit, screen=policy)
            return Result(selected.prompt, selected.evaluations, 0, [])

        with patch.object(cycle, 'search', search):
            return attribution.attributed_step(upstream, method, contents, incumbent, layout, plan, fixed_round=False)

    with patch.object(continuous, 'schedule', schedule), patch.object(continuous, 'step', step), patch.object(
            archive, 'POLICIES', ('runner-up',)):
        return archive.episode(matrix, held, seed, {**original, 'evaluationLookupLimit': cap})


def prepare():
    parent, original, source = transfer.prepare()
    raw = (ROOT / 'docs/prompteval-validation-transfer-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Published transfer report differs from the verified source')
    prior = json.loads(raw, object_pairs_hook=unique_object)
    if digest(parent) != prior['planSha256']:
        raise ValueError('Frozen transfer schedule differs from the published plan')
    plan = {'protocol': 'cpo-prompteval-single-finalist-v1', 'parentPlanSha256': prior['planSha256'],
            'parentReportSha256': SOURCE_SHA256, 'gepaVersion': original['gepaVersion'],
            'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'selectorSha256': sha256((ROOT / 'cpo/single_finalist.py').read_bytes()).hexdigest(),
            'policies': list(POLICIES), 'rowsAndCap': transfer.DESIGNS['candidate'],
            'gate': 'At least the matched GEPA pass count at no extra cost, with more passes or 10% fewer lookups',
            'scope': 'Fixed candidate streams with original archive, qualification and GEPA controls'}
    return plan, original, source, prior['panels']


def replay(plan, original, source, prior):
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[field] for field in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        baseline = [selection.episode(matrix, held, seed, original, *plan['rowsAndCap']) for seed in original['seeds']]
        by_method = {arm: [episode[arm] for episode in baseline] for arm in METHODS}
        for method, trace in by_method.items():
            if totals(trace) != prior[name]['totals']['candidate'][method]:
                raise ValueError('Recorded baseline differs from the published transfer')
        candidates = {}
        for policy in POLICIES:
            measured = [screened_episode(matrix, held, seed, original, policy) for seed in original['seeds']]
            if any([episode[method] for episode in measured] != by_method[method] for method in METHODS[1:]):
                raise ValueError('The finalist screen changed a matched GEPA trace')
            trace = [episode[transfer.CPO] for episode in measured]
            search = sum(step['searchLookups'] for episode in trace for step in episode['steps'])
            candidates[policy] = {'totals': totals(trace), 'searchLookups': search, 'traceSha256': digest(trace),
                                  'comparisons': {method: transfer.paired(trace, reference)
                                                  for method, reference in by_method.items()}}
        panels[name] = {'baseline': {method: totals(trace) for method, trace in by_method.items()},
                        'candidates': candidates}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels,
            'panelsClearingBothGates': {policy: [name for name, row in panels.items() if all(
                row['candidates'][policy]['comparisons'][method]['qualified'] for method in METHODS[1:])]
                                        for policy in POLICIES}}


def totals(trace):
    return {'holdoutPasses': sum(row['holdoutPasses'] for row in trace),
            'paidLookups': sum(row['evaluations'] for row in trace)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, original, source, prior = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, original, source, prior)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
