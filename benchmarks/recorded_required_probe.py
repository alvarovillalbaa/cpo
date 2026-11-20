"""Test screening only when a missed case is required by the validation gate."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import combinations
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_coverage_window as window
from cpo import Observation, Row
from cpo._contract import digest
from cpo.required_probe import required_miss, select_required_covered_pool


ROOT = Path(__file__).resolve().parents[1]
PARENT_SHA256 = '25ff154a5166e1c7a44c1c5deb845e306b8e6dce8ea51d94e541baffe4c7182d'
METHODS = ('required-window', 'required-first')
source, frontier = window.source, window.parent


def select(initial, roster, rows, strata, evaluate, spent, *, cap, width, policy):
    if policy == 'required-first':
        attempted = set()

        def observe(prompt, row):
            attempted.add(prompt)
            passed, fields = evaluate(prompt, row.id)
            return Observation(passed, {}, fields)

        validation = [Row(case, 'task', case in strata) for case in rows]
        result = select_required_covered_pool((initial, *roster), validation, observe,
                                              metric_limit=cap, critical_strata=strata)
        if result.evaluations != spent():
            raise ValueError('Packaged selector diverged from paid lookup accounting')
        return result.prompt, len(attempted - {initial})

    baseline = {case: evaluate(initial, case)[0] for case in rows}
    witness = required_miss(baseline, strata)

    def cached(prompt, case):
        if prompt == initial:
            return baseline[case], 0
        return evaluate(prompt, case)

    if witness is None:
        return _race(initial, roster, rows, strata, cached, spent, cap=cap, method=source.PRIMARY)
    return _screen(initial, roster, rows, strata, cached, spent, cap=cap, width=width, fields=False)


# Preserve the two original algorithms while the sealed harness routes its candidate arm to the adapter.
_screen = window.screen
_race = source.race


def prepare():
    previous, data, prior, frontier_archive = window.prepare()
    raw = (ROOT / 'docs/recorded-coverage-window-results-v1.json').read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_SHA256 or digest(previous) != reference['planSha256']:
        raise ValueError('Previous shared-probe replay differs from its seal')
    paths = ('benchmarks/recorded_required_probe.py', 'cpo/required_probe.py', 'cpo/covered_pool.py')
    plan = {**previous, 'protocol': 'cpo-recorded-required-probe-v1', 'primary': 'required-first',
            'requiredProbePolicies': METHODS, 'parentPlanSha256': digest(previous), 'parentReportSha256': PARENT_SHA256,
            'sourceSha256': {**previous['sourceSha256'], **{path: sha256((ROOT / path).read_bytes()).hexdigest()
                                                           for path in paths}},
            'policy': ('Use the existing exact roster race unless an incumbent miss is the sole case in a critical '
                       'stratum. Compare probing that case in the existing window with probing one challenger at a '
                       'time. Keep exact confirmation, qualification, and the same incumbent precheck.')}
    return plan, data, prior, frontier_archive, reference['results']


def opportunity(data, plan, held):
    rows, matrix, _, initial, _, strata, _ = data
    counts = Counter(precheckAdmitted=0, requiredWitness=0)
    for index, cases in enumerate(held):
        available = sorted(rows.keys() - set(cases))
        Random(plan['seedStart'] + index * plan['seedStride']).shuffle(available)
        validation, qualification = available[3:7], available[7:]
        if all(matrix[initial][case][0] for case in qualification):
            continue
        counts['precheckAdmitted'] += 1
        baseline = {case: matrix[initial][case][0] for case in validation}
        witness = required_miss(baseline, {case: strata[case] for case in validation if case in strata})
        counts['requiredWitness'] += witness is not None
    return counts


def compare(data, task, plan, prior, frontier_archive, reference):
    original, paid, critical = frontier.measure(data, plan, prior)
    for policy, values in (('original', original), ('precheck', paid)):
        if frontier.summarize(values, critical, plan['caps']) != frontier_archive[policy]['tasks'][task]:
            raise ValueError('The original frontier did not reproduce')
    held = tuple(combinations(sorted(data[0]), 3))
    controls = (frontier.CONTROL, *(label for label in paid if label.startswith('gepa-')))
    records = {}
    for cap in plan['trialCaps']:
        base = f'{source.PRIMARY}/{cap}'
        old = window.measure(data, plan, cap, 'binary-window', held)
        if {key: value for key, value in old.items() if key != 'outcomes'} != reference[str(cap)]['points']['binary-window']:
            raise ValueError('The earlier binary window did not reproduce')
        points = {**paid, 'binary-window': old}
        for policy in METHODS:
            def chosen(initial, roster, validation, strata, evaluate, spent, *, cap, width, fields):
                return select(initial, roster, validation, strata, evaluate, spent, cap=cap,
                              width=width, policy=policy)

            with patch.object(window, 'screen', chosen):
                points[policy] = window.measure(data, plan, cap, 'binary-window', held)
        comparisons = {}
        for policy in METHODS:
            rival = frontier.affordable(points[policy]['total'], points, controls)
            fixed = reference[str(cap)]['effects']['binary-window']['previousGepaControl']['control']
            comparisons[policy] = {label: frontier.compare(points, critical, policy, control)
                                   for label, control in (('ordered', base), ('binaryWindow', 'binary-window'),
                                                          ('affordableGepa', rival), ('fixedGepa', fixed))}
        records[str(cap)] = {'points': {arm: {key: value for key, value in points[arm].items() if key != 'outcomes'}
                                        for arm in (base, 'binary-window', *METHODS)}, 'comparisons': comparisons}
    return {'caps': records, 'admittedTrialCoverage': opportunity(data, plan, held)}


def replay(plan, data, prior, frontier_archive, reference):
    return {'plan': plan, 'planSha256': digest(plan),
            'results': {task: compare(values, task, plan, prior[task], frontier_archive, reference[task])
                        for task, values in sorted(data.items())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, *inputs)
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
