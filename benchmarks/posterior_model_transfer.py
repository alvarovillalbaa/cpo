"""Confirm the frozen posterior allocation route on new archived model panels."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from benchmarks import independent_mmlu_transfer as dataset, routed_finalist_parquet_capture as parquet
from benchmarks import routed_score_allocation as prior
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'docs/posterior-model-transfer-design-v1.json'
PARENT_REPORT = '096f581ea76be3be25bd109167d7a944c2825debd16f760796d23b1b1f38dd49'
SUBJECTS = ('high_school_geography', 'high_school_government_and_politics', 'high_school_microeconomics',
            'high_school_statistics', 'moral_disputes', 'world_religions')
MODELS = ('google_gemma_7b', 'google_flan_t5_xxl')
EXPECTED = [(subject, model) for subject in SUBJECTS for model in MODELS]
CANDIDATE = 'posterior-wide'
CPO = ('strict', 'exact-wide', CANDIDATE)
CONTROLS = (*prior.GEPA, 'retain-start')


def object_name(subject, model):
    return f'{subject}/{model}-00000-of-00001.parquet'


def design(objects):
    previous, *_ = prior.prepare()
    raw = (ROOT / 'docs/routed-score-allocation-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != PARENT_REPORT or dataset.read_json(raw)['planSha256'] != digest(previous):
        raise ValueError('The posterior routing experiment differs from its published seal')
    if objects.keys() != {object_name(*panel) for panel in EXPECTED} or any(
            not 0 < item['size'] <= 2_000_000 or len(item['oid']) != 40
            or item['lfs'] and len(item['lfs']['oid']) != 64 for item in objects.values()):
        raise ValueError('Every enrolled panel needs a bounded and pinned source object')
    paths = ('benchmarks/posterior_model_transfer.py', 'benchmarks/routed_finalist_parquet_capture.py',
             'benchmarks/independent_mmlu_transfer.py', 'benchmarks/independent_mmlu_cost_uncertainty.py')
    return {
        **{key: previous[key] for key in ('schedule', 'validationRows', 'searchCap', 'gepaVersion',
                                           'bootstrap', 'minimumLookupSavingPercent')},
        'protocol': 'cpo-posterior-model-transfer-v1', 'parentPlanSha256': digest(previous),
        'parentReportSha256': PARENT_REPORT, 'sourceDataset': dataset.DATASET, 'sourceRevision': dataset.REVISION,
        'license': 'MIT', 'objects': objects, 'subjects': SUBJECTS, 'models': MODELS, 'templateCount': 100,
        'decoderVersion': parquet.DECODER_VERSION, 'methods': (*CPO, *CONTROLS),
        'primary': CANDIDATE, 'primaryControls': prior.PRIMARY, 'cheaperControl': prior.LOWER_COST,
        'sourceSha256': {**previous['sourceSha256'], **{path: sha256((ROOT / path).read_bytes()).hexdigest()
                                                       for path in paths}},
        'scope': ('Freeze panel identities and posterior-wide before capture. Preserve the original exact-wide '
                  'and routed CPO controls, the 52-lookup GEPA controls, and the earlier cap-47 batched point. '
                  'Resample physical holdout cases, keeping models and all episodes together.'),
    }


def freeze():
    dataset.check_revision()
    objects = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for subject, metadata in zip(SUBJECTS, pool.map(parquet.tree, SUBJECTS), strict=True):
            for model in MODELS:
                name = object_name(subject, model)
                item = metadata[name]
                objects[name] = {'size': item['size'], 'oid': item['oid'], 'lfs': item.get('lfs')}
    return design(objects)


def check_snapshot(snapshot, plan):
    with patch.object(dataset, 'EXPECTED', EXPECTED):
        dataset.check_corpus(snapshot, plan)
    for panel in snapshot['panels']:
        name = object_name(panel['subject'], panel['model'])
        expected, source = plan['objects'][name], panel['sourceParquet']
        url = f'{parquet.HUB}/datasets/{dataset.DATASET}/resolve/{dataset.REVISION}/{name}'
        if (source['url'] != url or source['bytes'] != expected['size'] or source['gitOid'] != expected['oid']
                or len(source['sha256']) != 64 or expected['lfs'] and source['sha256'] != expected['lfs']['oid']):
            raise ValueError('Snapshot provenance differs from an enrolled source object')


def capture(plan):
    if version('duckdb') != plan['decoderVersion']:
        raise ValueError('Use the pinned DuckDB decoder in a temporary environment')
    import duckdb

    dataset.check_revision()
    with TemporaryDirectory(prefix='cpo-posterior-parquet-') as scratch, duckdb.connect(':memory:') as connection:
        connection.execute('SET threads=1')
        connection.execute('SET preserve_insertion_order=true')
        panels = [parquet.published_panel(subject, model, plan['objects'], Path(scratch), connection)
                  for subject, model in EXPECTED]
    dataset.check_revision()
    result = {'designSha256BeforeCapture': digest(plan), 'sourceDataset': dataset.DATASET,
              'observedRepoRevision': dataset.REVISION, 'license': plan['license'], 'panels': panels}
    check_snapshot(result, plan)
    return result


def measure(panel, plan):
    subject, matrix = panel['subject'], panel['correctness']
    held = prior.CONFIRMATION.holdout(subject, len(matrix[0]))
    schedule = plan['schedule']
    uncertainty = prior.CONFIRMATION.uncertainty
    starts = prior.ties.costs.retained_prompts(matrix, held, schedule)
    finals, points = {'retain-start': starts}, {}
    for method in CPO:
        totals, log, final = Counter(), [], []
        for seed, start in zip(schedule['seeds'], starts, strict=True):
            usage, trace = prior.run(matrix, held, seed, plan, str(start), method)
            totals.update(usage)
            log.append(trace)
            final.append(int(trace[-1]['decision']['selected']))
        points[method] = {**totals, 'paidLookups': totals['searchPaid'] + totals['qualificationPaid'],
                          'traceSha256': digest(log)}
        finals[method] = final
    for label in prior.GEPA:
        mode, cap = label.split('/')
        finals[label], points[label] = uncertainty.final_prompts(matrix, held, schedule, plan, mode, int(cap))
    outcomes = {method: uncertainty.case_totals(matrix, held, choices) for method, choices in finals.items()}
    points['retain-start'] = {'holdoutPasses': sum(outcomes['retain-start'].values()), 'paidLookups': 0}
    if any(sum(outcomes[key].values()) != point['holdoutPasses'] for key, point in points.items()):
        raise ValueError('Final-prompt vectors disagree with the paid replay')
    return held, points, outcomes


def replay(plan, snapshot, corpus_hash):
    check_snapshot(snapshot, plan)
    reports, holdouts, vectors = {}, {}, {}
    totals = {name: Counter() for name in plan['methods']}
    comparisons = (*CONTROLS, 'strict', 'exact-wide')
    for panel in snapshot['panels']:
        subject, model = panel['subject'], panel['model']
        held, points, outcomes = measure(panel, plan)
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('The two linked models must share every holdout case')
        by_subject = vectors.setdefault(subject, {method: [0] * len(held) for method in comparisons})
        for method, values in by_subject.items():
            for index, case in enumerate(held):
                values[index] += outcomes[CANDIDATE][case] - outcomes[method][case]
        reports[f'{subject}/{model}'] = points
        for name, point in points.items():
            totals[name].update({key: value for key, value in point.items() if type(value) is int})
    ranges = prior.transfer.ranges(vectors, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
    budget = totals[CANDIDATE]['paidLookups']
    saving = {name: 1 - budget / totals[name]['paidLookups'] for name in prior.GEPA}
    meets_cost = all(100 * budget <= (100 - plan['minimumLookupSavingPercent']) * totals[name]['paidLookups']
                     for name in plan['primaryControls'])
    low, high = ranges['joint']
    gate = 'failed' if not meets_cost or high < 0 else 'passed' if low >= 0 else 'inconclusive'
    return {'plan': plan, 'designSha256': digest(plan), 'corpusSha256': corpus_hash,
            'uniqueHoldoutCases': sum(map(len, holdouts.values())), 'panels': reports, 'totals': totals,
            'comparison': {'gate': gate, 'caseSensitivityRanges': ranges, 'lookupSavingFractions': saving}}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', action='store_true')
    mode.add_argument('--capture', action='store_true')
    mode.add_argument('--replay', type=Path)
    cli.add_argument('--execute')
    cli.add_argument('--out', required=True, type=Path)
    args = cli.parse_args()
    if args.out.exists() or args.freeze == bool(args.execute):
        cli.error('Use a fresh output path and supply the frozen seal for capture or replay')
    if args.freeze:
        plan = freeze()
        result = {'design': plan, 'designSha256': digest(plan)}
    else:
        stored = dataset.read_json(DESIGN.read_bytes())
        plan = design(stored['design']['objects'])
        seal = digest(plan)
        if stored != dataset.read_json(json.dumps({'design': plan, 'designSha256': seal}).encode()) or args.execute != seal:
            cli.error('The frozen design, source or execution seal differs')
        if args.capture:
            result = capture(plan)
        else:
            if version('gepa') != plan['gepaVersion']:
                cli.error('Use the pinned GEPA version')
            data = args.replay.read_bytes()
            result = replay(plan, dataset.read_json(data), sha256(data).hexdigest())
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
