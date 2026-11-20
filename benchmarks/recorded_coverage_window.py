"""Test whether one shared probe improves critical-coverage search at tight budgets."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import combinations
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_coverage_confirmation as source, recorded_coverage_frontier as parent
from cpo._contract import digest
from cpo.coverage_confirmation import confirm_covered_gain


ROOT = Path(__file__).resolve().parents[1]
PARENT_REPORT = '1ebab4d108e1d5fc7eef4d6fe42a5e7b0a4c5e2dfd4dd541a8fbf16c53d3b00b'
CAPS = (24, 36, 48)
METHODS = ('binary-window', 'field-window')
WIDTH = 4


def screen(initial, roster, validation, strata, evaluate, spent, *, cap, width, fields):
    baseline = {case: evaluate(initial, case)[0] for case in validation}
    protected = {case for case in strata if baseline[case]}
    missed = [case for case in validation if not baseline[case]]
    if not missed:
        return initial, 0
    sizes = Counter(strata.values())
    witness = min(missed, key=lambda case: (case not in strata, sizes[strata[case]] if case in strata else 0))
    winner, score = initial, sum(baseline.values())
    cursor = 0
    while cursor < len(roster) and score < len(validation):
        available = min(width, cap - spent() - (len(validation) - 1))
        if available <= 0:
            break
        window = roster[cursor:cursor + available]
        cursor += len(window)
        measured = {prompt: evaluate(prompt, witness) for prompt in window}
        ranked = sorted(window, key=lambda prompt: (measured[prompt][0], measured[prompt][1] if fields else 0),
                        reverse=True)
        for prompt in ranked:
            if spent() + len(validation) - 1 > cap or score == len(validation):
                break
            exact = confirm_covered_gain(baseline, score, protected, strata, {witness: measured[prompt][0]},
                                         lambda case: evaluate(prompt, case)[0])
            if exact is not None:
                winner, score = prompt, exact
    return winner, cursor


def prepare():
    previous, data, earlier = parent.prepare()
    raw = (ROOT / 'docs/recorded-coverage-frontier-results-v1.json').read_bytes()
    archive = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_REPORT or archive['planSha256'] != digest(previous):
        raise ValueError('The archived frontier differs from its seal')
    own = Path(__file__).resolve()
    plan = {**previous, 'protocol': 'cpo-recorded-coverage-window-v1', 'trialCaps': CAPS,
            'primary': 'field-window', 'windowMethods': METHODS, 'windowWidth': WIDTH,
            'parentPlanSha256': digest(previous), 'parentReportSha256': PARENT_REPORT,
            'sourceSha256': {**previous['sourceSha256'], str(own.relative_to(ROOT)): sha256(own.read_bytes()).hexdigest()},
            'fixedComparison': 'Also retain the previous strongest affordable GEPA setting at each unscreened CPO cost.',
            'windowPolicy': ('Read one shared incumbent miss per candidate in a bounded block. Prefer a critical miss in '
                             'the smallest represented stratum. Reuse that observation and confirm candidates in exact '
                             'pass order, with optional matched-field ties. Leave the exact nomination and qualification gates intact.')}
    return plan, data, earlier, archive


def measure(data, plan, cap, method, held):
    _, matrix, _, incumbent, _, _, _ = data
    winner_hits, totals = [], Counter(passes=0, search=0, qualification=0, total=0, offered=0, skippedSearches=0)

    def nominate(initial, roster, validation, strata, evaluate, spent, *, cap, method):
        if method != source.PRIMARY:
            raise ValueError('The experimental screen only replaces the CPO arm')
        return screen(initial, roster, validation, strata, evaluate, spent, cap=cap,
                      width=plan['windowWidth'], fields=use_fields)

    use_fields = method == 'field-window'
    with patch.object(source, 'race', nominate), patch.object(source, 'METHODS', (source.PRIMARY,)):
        for index, cases in enumerate(held):
            records, _, qualification = source.compare(data, cases, plan['seedStart'] + index * plan['seedStride'], cap)
            record = records[source.PRIMARY]
            known = tuple(matrix[incumbent][case][0] for case in qualification)
            search, charge, offered, skipped = parent.prechecked_cost(record, incumbent, known)
            hits = parent.mask(cases, record['outcomes'])
            winner_hits.append(hits)
            totals.update(passes=hits.bit_count(), search=search, qualification=charge, total=search + charge,
                          offered=offered, skippedSearches=skipped)
    return {**totals, 'outcomes': tuple(winner_hits)}


def compare(data, name, plan, prior, archive):
    original, prechecked, critical = parent.measure(data, plan, prior)
    for policy, series in (('original', original), ('precheck', prechecked)):
        if parent.summarize(series, critical, plan['caps']) != archive[policy]['tasks'][name]:
            raise ValueError('Parent frontier totals and matched comparisons did not reproduce')
    held = tuple(combinations(sorted(data[0]), 3))
    controls = (parent.CONTROL, *(label for label in prechecked if label.startswith('gepa-')))
    results = {}
    for cap in plan['trialCaps']:
        base = f'{source.PRIMARY}/{cap}'
        points = {**prechecked, **{method: measure(data, plan, cap, method, held)
                                   for method in plan['windowMethods']}}
        reference_gepa = archive['precheck']['tasks'][name]['comparisons'][base]['strongest-fixed']['control']
        effects = {}
        for method in plan['windowMethods']:
            best = parent.affordable(points[method]['total'], points, controls)
            affordable_original = parent.affordable(points[method]['total'], points,
                                                     (parent.CONTROL, *(f'{source.PRIMARY}/{n}' for n in plan['caps'])))
            effects[method] = {'matchedCapCpo': parent.compare(points, critical, method, base),
                               'affordableCpo': parent.compare(points, critical, method, affordable_original),
                               'affordableGepa': parent.compare(points, critical, method, best),
                               'previousGepaControl': parent.compare(points, critical, method, reference_gepa),
                               'gepaControl': {key: points[best][key] for key in ('passes', 'total')}}
        results[str(cap)] = {'points': {label: {key: value for key, value in points[label].items() if key != 'outcomes'}
                                        for label in (base, *plan['windowMethods'])},
                             'effects': effects}
    return results


def replay(plan, data, prior, archive):
    return {'plan': plan, 'planSha256': digest(plan),
            'results': {task: compare(values, task, plan, prior[task], archive) for task, values in sorted(data.items())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, prior, archive = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, data, prior, archive)
    with args.out.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
