"""Compare coverage-aware CPO with GEPA at matched realized lookup costs."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import combinations
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_coverage_confirmation as source
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
PARENT_REPORT = '85bdcb19940e4800aa627696c2ad2410e407cec61b51a16c7a20deeae1eadf5a'
CAPS = tuple(range(8, 49, 4))
PRIMARY = source.PRIMARY
CONTROL = 'retain-start'


def prepare():
    previous, data = source.prepare()
    raw = (ROOT / 'docs/recorded-coverage-confirmation-results-v1.json').read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_REPORT or reference['planSha256'] != digest(previous):
        raise ValueError('Source results differ from the sealed provider replay')
    runner = Path(__file__).resolve()
    plan = {**previous, 'protocol': 'cpo-recorded-coverage-frontier-v1', 'caps': CAPS,
            'parentPlanSha256': digest(previous), 'parentReportSha256': PARENT_REPORT,
            'sourceSha256': {**previous['sourceSha256'], str(runner.relative_to(ROOT)): sha256(runner.read_bytes()).hexdigest()},
            'frontierControl': CONTROL,
            'comparison': 'Among affordable fixed settings maximize holdout passes, breaking ties by fewer paid lookups.',
            'scope': 'Holdout selects the retrospective control after replay. Ordinary search and qualification are unchanged.',
            'precheck': ('Read incumbent qualification until the first miss or a complete pass panel. Cancel search only '
                         'after a complete pass and reuse any read incumbent replies in ordinary qualification. Apply to all methods.')}
    return plan, data, reference['results']


def mask(cases, matches):
    return sum(1 << index for index, case in enumerate(cases) if matches[case])


def prechecked_cost(record, incumbent, qualification_passes):
    """Count a paid incumbent precheck with exact reuse of subsequent baseline replies."""
    first_miss = next((count for count, passed in enumerate(qualification_passes, 1) if not passed), None)
    if first_miss is None:
        if record['prompt'] != incumbent:
            raise ValueError('A complete passing incumbent panel cannot be strictly improved')
        return 0, len(qualification_passes), 0, 1
    if record['nominee'] == incumbent:
        return record['search'], first_miss, record['offered'], 0
    # The archived qualification already paid for the complete incumbent panel.
    if record['qualification'] < len(qualification_passes):
        raise ValueError('The recorded qualification lacks the paid incumbent panel')
    return record['search'], record['qualification'], record['offered'], 0


def measure(data, plan, reference):
    metadata, matrix, _, incumbent, _, risk, _ = data
    held = tuple(combinations(sorted(metadata), 3))
    critical = tuple(mask(panel, {case: case in risk for case in panel}) for panel in held)
    start = tuple(mask(panel, {case: matrix[incumbent][case][0] for case in panel}) for panel in held)
    points = {CONTROL: {'passes': sum(x.bit_count() for x in start), 'total': 0, 'outcomes': start}}
    prechecked = dict(points)
    for cap in plan['caps']:
        records = [source.compare(data, panel, plan['seedStart'] + index * plan['seedStride'], cap)
                   for index, panel in enumerate(held)]
        with patch.object(source, 'compare', side_effect=records):
            summary = source.summarize(data, cap, held, plan)
        if str(cap) in reference and summary != reference[str(cap)]:
            raise ValueError('An existing cap did not reproduce its published replay')
        for method in (PRIMARY, *source.GEPA):
            hits = tuple(mask(panel, entry[0][method]['outcomes']) for panel, entry in zip(held, records, strict=True))
            label = f'{method}/{cap}'
            points[label] = {**summary['totals'][method], 'outcomes': hits}
            totals = Counter()
            for record, _, qualification in records:
                known = tuple(matrix[incumbent][case][0] for case in qualification)
                search, qualification_cost, offered, skipped = prechecked_cost(record[method], incumbent, known)
                totals.update(search=search, qualification=qualification_cost, total=search + qualification_cost,
                              offered=offered, skippedSearches=skipped)
            prechecked[label] = {**points[label], **totals}
    return points, prechecked, critical


def affordable(budget, points, control_names):
    """Return the strongest measured affordable control, preferring cheaper ties."""
    candidates = [(name, points[name]) for name in control_names if points[name]['total'] <= budget]
    return max(candidates, key=lambda item: (item[1]['passes'], -item[1]['total']))[0]


def compare(points, critical, challenger, control):
    left, right = points[challenger], points[control]
    gain, savings = left['passes'] - right['passes'], right['total'] - left['total']
    losses = sum((want & ~got & keep).bit_count()
                 for got, want, keep in zip(left['outcomes'], right['outcomes'], critical, strict=True))
    return {'control': control, 'passDelta': gain, 'lookupSavings': savings, 'matchedCriticalLosses': losses}


def summarize(points, critical, caps):
    retained = {method: tuple(f'{method}/{cap}' for cap in caps) for method in source.GEPA}
    baseline = (CONTROL,)
    all_controls = (*baseline, *(name for group in retained.values() for name in group))
    comparisons = {}
    for cap in caps:
        name = f'{PRIMARY}/{cap}'
        budget = points[name]['total']
        controls = {method: affordable(budget, points, (*baseline, *labels))
                    for method, labels in retained.items()}
        controls['strongest-fixed'] = affordable(budget, points, all_controls)
        points_matching_score = [control for control in all_controls if points[control]['passes'] >= points[name]['passes']]
        comparisons[name] = {label: compare(points, critical, name, control) for label, control in controls.items()}
        if points_matching_score:
            cheapest = min(points_matching_score, key=lambda control: points[control]['total'])
            comparisons[name]['cheapest-score-match'] = compare(points, critical, name, cheapest)
    return {'points': {name: {key: value for key, value in point.items() if key != 'outcomes'}
                       for name, point in points.items()}, 'comparisons': comparisons}


def replay(plan, tasks, reference):
    panels = {name: measure(data, plan, reference[name]) for name, data in sorted(tasks.items())}
    result = {'plan': plan, 'planSha256': digest(plan)}
    for policy, index in (('original', 0), ('precheck', 1)):
        pooled = {}
        for label in next(iter(panels.values()))[index]:
            points = [item[index][label] for item in panels.values()]
            counts = Counter()
            for point in points:
                counts.update({key: value for key, value in point.items() if key != 'outcomes'})
            pooled[label] = {**counts, 'outcomes': tuple(entry for point in points for entry in point['outcomes'])}
        critical = tuple(entry for _, _, masks in panels.values() for entry in masks)
        result[policy] = {'tasks': {name: summarize(value[index], value[2], plan['caps'])
                                    for name, value in panels.items()},
                          'pooled': summarize(pooled, critical, plan['caps'])}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, tasks, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, tasks, reference)
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
