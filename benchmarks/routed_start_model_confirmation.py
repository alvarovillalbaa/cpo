"""Freeze and confirm the start-protection route on unseen archived model splits."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
from unittest.mock import patch

from benchmarks import independent_mmlu_cost_frontier as frontier
from benchmarks import independent_mmlu_cost_uncertainty as uncertainty
from benchmarks import independent_mmlu_transfer as dataset
from benchmarks import routed_finalist_parquet_capture as parquet
from benchmarks import routed_model_cost_frontier as prior_cost
from benchmarks import routed_start_protection as prior
from benchmarks.four_case_qualification_transfer import interval
from benchmarks.prompteval_transfer import holdout
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'docs/routed-start-model-confirmation-design-v1.json'
PARENT_SHA256 = '68ef0088bd57522ec031daa45d24b8023afc571fb28bf8f6ce28db2ec81d3b20'
SUBJECTS = ('college_physics', 'computer_security', 'electrical_engineering', 'formal_logic',
            'high_school_european_history', 'high_school_psychology', 'international_law', 'public_relations')
MODELS = ('meta_llama_llama_3_8b_instruct', 'mistralai_mistral_7b_v0_1')
EXPECTED = [(subject, model) for subject in SUBJECTS for model in MODELS]
ROUTE = 'wide-on-third-miss'
CANDIDATE = 'split-and-reserve'
BASELINE = 'ordinary'
METHODS = (CANDIDATE, BASELINE, 'seeded')
PRIMARY = tuple(f'{mode}/52' for mode in uncertainty.MODES)
FIELDS = frontier.FIELDS


def object_name(subject, model):
    return f'{subject}/{model}-00000-of-00001.parquet'


def design(objects):
    parent, _, _, old_panels, _ = prior.prepare('model-transfer')
    pilots = prior.checked_report('routed-start-protection', PARENT_SHA256)
    if digest(parent) != pilots['model-transfer']['planSha256']:
        raise ValueError('The retrospective design differs from its result')
    older_subjects = {key.split('/')[0] for key in (*old_panels, *pilots['mmlu']['panels'])}
    if older_subjects.intersection(SUBJECTS) or set(objects) != {object_name(*pair) for pair in EXPECTED}:
        raise ValueError('The confirmation needs the sealed new subject and model objects')
    if min(frontier.CAPS) < parent['validationRows'] + parent['schedule']['qualificationRowsPerCycle']:
        raise ValueError('Every GEPA cap must fund the incumbent after archive qualification')
    if any(type(item['size']) is not int or not 0 < item['size'] <= 2_000_000
           or len(item['oid']) != 40 or item['lfs'] and len(item['lfs']['oid']) != 64 for item in objects.values()):
        raise ValueError('Every pinned source object needs a bounded size and a Git or LFS receipt')
    paths = ('benchmarks/routed_start_model_confirmation.py', 'benchmarks/routed_finalist_parquet_capture.py',
             'benchmarks/routed_start_protection.py', 'benchmarks/independent_mmlu_cost_frontier.py',
             'benchmarks/independent_mmlu_cost_uncertainty.py', 'benchmarks/gepa_paid_cap_transfer.py',
             'benchmarks/paid_budget_frontier.py')
    return {
        **{k: parent[k] for k in ('schedule', 'validationRows', 'searchCap', 'gepaVersion')},
        'protocol': 'cpo-routed-start-model-confirmation-v1', 'parentPlanSha256': digest(parent),
        'parentReportSha256': PARENT_SHA256, 'sourceDataset': dataset.DATASET, 'sourceRevision': dataset.REVISION,
        'license': 'MIT', 'subjects': SUBJECTS, 'models': MODELS, 'templateCount': 100,
        'objects': objects, 'decoderVersion': parquet.DECODER_VERSION,
        'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
        'route': ROUTE, 'candidate': CANDIDATE, 'methods': METHODS,
        'gepaMethods': uncertainty.MODES, 'gepaCaps': frontier.CAPS,
        'primaryControls': PRIMARY, 'minimumLookupSavingPercent': 10, 'minimumLowerGain': 0,
        'bootstrapDraws': 4096, 'bootstrapSeed': 20261125,
        'scope': ('Freeze object identities, optimizer settings and controls before obtaining correctness outcomes. '
                  'Pair both models and all seeded trajectories within each resampled holdout case. '
                  'The primary gate uses both GEPA modes at cap 52. The secondary comparison reselects '
                  'the best affordable fixed point from the complete predeclared GEPA cost sweep.'),
    }


def freeze():
    dataset.check_revision()
    objects = {}
    for subject in SUBJECTS:
        tree = parquet.tree(subject)
        for model in MODELS:
            name = object_name(subject, model)
            item = tree[name]
            objects[name] = {'size': item['size'], 'oid': item['oid'], 'lfs': item.get('lfs')}
    return design(objects)


def check_snapshot(snapshot, plan):
    with patch.object(dataset, 'EXPECTED', EXPECTED):
        dataset.check_corpus(snapshot, plan)
    for panel in snapshot['panels']:
        name = object_name(panel['subject'], panel['model'])
        source = panel['sourceParquet']
        target = plan['objects'][name]
        expected_url = f'{parquet.HUB}/datasets/{dataset.DATASET}/resolve/{dataset.REVISION}/{name}'
        if (source['url'] != expected_url or source['gitOid'] != target['oid'] or source['bytes'] != target['size']
                or len(source['sha256']) != 64 or target['lfs'] and source['sha256'] != target['lfs']['oid']):
            raise ValueError('Capture provenance differs from the sealed source objects')


def capture(plan):
    if version('duckdb') != plan['decoderVersion']:
        raise ValueError('Use the pinned DuckDB decoder in a temporary environment')
    import duckdb

    with TemporaryDirectory(prefix='cpo-start-confirmation-parquet-') as scratch, duckdb.connect(':memory:') as conn:
        conn.execute('SET threads=1')
        conn.execute('SET preserve_insertion_order=true')
        panels = [parquet.published_panel(subject, model, plan['objects'], Path(scratch), conn)
                  for subject, model in EXPECTED]
    snapshot = {'designSha256BeforeCapture': digest(plan), 'sourceDataset': dataset.DATASET,
                'observedRepoRevision': dataset.REVISION, 'license': plan['license'], 'panels': panels}
    check_snapshot(snapshot, plan)
    return snapshot


def measure_panel(panel, plan):
    matrix, subject = panel['correctness'], panel['subject']
    held = holdout(subject, len(matrix[0]))
    schedule = plan['schedule']
    starts = prior_cost.retained_prompts(matrix, held, schedule)
    gepa, cpo, outcomes = {}, {}, {}
    for mode in plan['gepaMethods']:
        points = gepa[mode] = {}
        for cap in plan['gepaCaps']:
            finals, points[str(cap)] = uncertainty.final_prompts(matrix, held, schedule, plan, mode, cap)
            outcomes[f'{mode}/{cap}'] = uncertainty.case_totals(matrix, held, finals)
    for policy in (CANDIDATE, BASELINE):
        totals, finals, traces = Counter(), [], []
        for seed, start in zip(schedule['seeds'], starts, strict=True):
            count, trace = prior.run(matrix, held, seed, plan, ROUTE, policy, str(start))
            totals.update(count)
            traces.append(trace)
            finals.append(int(trace[-1]['decision']['selected']))
        cpo[policy] = {**totals, 'paidLookups': totals['searchPaid'] + totals['qualificationPaid'],
                       'traceSha256': digest(traces)}
        outcomes[policy] = uncertainty.case_totals(matrix, held, finals)
    finals, cpo['seeded'], _ = prior_cost.cpo_paths('seeded', matrix, held, plan)
    outcomes['seeded'] = uncertainty.case_totals(matrix, held, finals)
    outcomes['retain-start'] = uncertainty.case_totals(matrix, held, starts)
    flat = {**cpo, **{f'{mode}/{cap}': point for mode, caps in gepa.items() for cap, point in caps.items()}}
    if any(sum(outcomes[label].values()) != point['holdoutPasses'] for label, point in flat.items()):
        raise ValueError('Paired holdout counts differ from the measured trajectories')
    return {'holdoutCaseIDs': held, 'cpo': cpo, 'gepa': gepa,
            'retainStart': sum(outcomes['retain-start'].values())}, outcomes


def paired_ranges(subject_cases, plan, affordable):
    labels = tuple(dict.fromkeys((*PRIMARY, *affordable, BASELINE, 'seeded', 'retain-start')))
    rng = Random(plan['bootstrapSeed'])
    samples = {label: [] for label in (*PRIMARY, BASELINE, 'seeded', 'retain-start', 'primaryJoint')}
    if affordable:
        samples['affordable'] = []
    for _ in range(plan['bootstrapDraws']):
        margins = Counter()
        for subject in sorted(subject_cases):
            cases = subject_cases[subject]
            chosen = Counter(rng.choices(tuple(cases), k=len(cases)))
            margins.update({label: sum((cases[i][CANDIDATE] - cases[i][label]) * n for i, n in chosen.items())
                            for label in labels})
        margins['primaryJoint'] = min(margins[label] for label in PRIMARY)
        if affordable:
            margins['affordable'] = min(margins[label] for label in affordable)
        for label, values in samples.items():
            values.append(margins[label])
    return {label: interval(values) for label, values in samples.items()}


def replay(snapshot, plan, raw):
    check_snapshot(snapshot, plan)
    panels, subject_cases = {}, {}
    for panel in snapshot['panels']:
        subject, model = panel['subject'], panel['model']
        point, outcomes = measure_panel(panel, plan)
        panels[f'{subject}/{model}'] = point
        dest = subject_cases.setdefault(subject, {case: Counter() for case in point['holdoutCaseIDs']})
        if tuple(dest) != tuple(point['holdoutCaseIDs']):
            raise ValueError('Both models must share the same holdout case order')
        for label, values in outcomes.items():
            for case, count in values.items():
                dest[case][label] += count
    summary = frontier.summarize(panels)
    budget = summary['cpoTotals'][CANDIDATE]['paidLookups']
    gepa_costs = {f'{mode}/{cap}': p['paidLookups']
                  for mode, caps in summary['gepaTotals'].items() for cap, p in caps.items()}
    affordable = [label for label, cost in gepa_costs.items() if cost <= budget]
    ranges = paired_ranges(subject_cases, plan, affordable)
    savings = {label: (gepa_costs[label] - budget) / gepa_costs[label] for label in PRIMARY}
    limit = 100 - plan['minimumLookupSavingPercent']
    low, high = ranges['primaryJoint']
    if any(100 * budget > limit * gepa_costs[label] for label in PRIMARY) or high < plan['minimumLowerGain']:
        status = 'failed'
    else:
        status = 'passed' if low >= plan['minimumLowerGain'] else 'inconclusive'
    return {'plan': plan, 'planSha256': digest(plan), 'corpusSha256': sha256(raw).hexdigest(),
            'panels': panels, **summary, 'primaryGate': status, 'lookupSavingFractions': savings,
            'caseSensitivityRanges': ranges, 'distinctHoldoutCases': sum(map(len, subject_cases.values()))}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', action='store_true')
    mode.add_argument('--design', action='store_true')
    mode.add_argument('--capture', action='store_true')
    mode.add_argument('--replay', type=Path)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    if args.freeze:
        if args.execute is not None or args.out is None or args.out.exists():
            cli.error('Freezing source metadata requires a fresh manifest path')
        plan = freeze()
        result = {'design': plan, 'designSha256': digest(plan)}
    else:
        frozen = dataset.read_json(DESIGN.read_bytes())
        plan = design(frozen['design']['objects'])
        seal = digest(plan)
        if frozen != json.loads(json.dumps({'design': plan, 'designSha256': seal})):
            raise ValueError('The design differs from the published manifest')
        if args.design and args.execute is None and args.out is None:
            print(json.dumps(frozen, sort_keys=True, indent=2))
            return
        if args.design or args.execute != seal or args.out is None or args.out.exists():
            cli.error('Execution requires the frozen design seal and a fresh output path')
        if args.capture:
            result = capture(plan)
        else:
            if version('gepa') != plan['gepaVersion']:
                raise ValueError('Use the pinned GEPA version')
            raw = args.replay.read_bytes()
            result = replay(dataset.read_json(raw), plan, raw)
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
