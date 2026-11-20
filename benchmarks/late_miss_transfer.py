"""Confirm the frozen late-miss policy on previously unused archived panels."""

from argparse import ArgumentParser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import independent_mmlu_transfer as source
from benchmarks import late_miss_substitution as prior
from benchmarks import posterior_model_transfer as transfer
from benchmarks import routed_finalist_parquet_capture as parquet
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'docs/late-miss-transfer-design-v1.json'
SNAPSHOT = ROOT / 'benchmarks/data/late-miss-transfer-v1.json'
PARENT_REPORT = 'f1671ec3758638da00451bf4e6e66b7e4bc6cb81c2a40bc87e6ba08969508cc0'
SUBJECTS = ('anatomy', 'college_biology', 'elementary_mathematics', 'high_school_macroeconomics',
            'human_aging', 'professional_psychology', 'sociology', 'us_foreign_policy')
MODELS = ('mistralai_mixtral_8x7b_instruct_v01', 'tiiuae_falcon_180b')
PANELS = tuple((subject, model) for subject in SUBJECTS for model in MODELS)
CANDIDATE = prior.METHODS[0]
CONTROLS = prior.parent.CONTROLS
METHODS = (CANDIDATE, *CONTROLS)


def local_pairs(value):
    if isinstance(value, dict):
        if (all(isinstance(value.get(key), str) for key in ('subject', 'model'))
                and isinstance(value.get('correctness'), list)):
            yield value['subject'], value['model']
        else:
            for entry in value.values():
                yield from local_pairs(entry)
    elif isinstance(value, list):
        for entry in value:
            yield from local_pairs(entry)


def design(objects, inventory):
    base, _ = prior.prepare()
    published = prior.inputs.checked_file('docs/late-miss-substitution-results-v1.json', PARENT_REPORT)
    if published['designSha256'] != digest(base):
        raise ValueError('The nominated late-miss policy differs from its published design')
    expected = {transfer.object_name(*panel) for panel in PANELS}
    if set(objects) != expected or any(not 0 < item['size'] <= 2_000_000 or len(item['oid']) != 40
                                      or item['lfs'] and len(item['lfs']['oid']) != 64
                                      for item in objects.values()):
        raise ValueError('Every enrolled panel needs one bounded pinned source object')
    parent, *_ = prior.route.prepare()
    paths = ('benchmarks/late_miss_transfer.py', 'benchmarks/late_miss_substitution.py',
             'benchmarks/posterior_model_transfer.py', 'benchmarks/routed_finalist_parquet_capture.py',
             'benchmarks/independent_mmlu_transfer.py')
    return {**{key: parent[key] for key in ('schedule', 'validationRows', 'searchCap', 'gepaVersion',
                                            'bootstrap', 'minimumLookupSavingPercent')},
            'protocol': 'cpo-late-miss-transfer-v1', 'parentDesignSha256': digest(base),
            'parentReportSha256': PARENT_REPORT, 'sourceDataset': source.DATASET,
            'sourceRevision': source.REVISION, 'license': 'MIT', 'objects': objects,
            'subjects': SUBJECTS, 'models': MODELS, 'templateCount': 100, 'decoderVersion': parquet.DECODER_VERSION,
            'methods': METHODS, 'primary': CANDIDATE, 'primaryControls': prior.route.PRIMARY,
            'localPreCaptureInventory': inventory,
            'sourceSha256': {**parent['sourceSha256'], **{path: sha256((ROOT / path).read_bytes()).hexdigest()
                                                        for path in paths}},
            'scope': ('Keep late substitution fixed. Enroll 16 unused model-subject pairs and freeze their '
                      'objects before capture. Keep the original schedules and compare against the original '
                      'CPO route, both official cap-52 GEPA modes, batched cap 47, and retaining the start.')}


def freeze(inventory_dir):
    if not inventory_dir.is_dir():
        raise ValueError('The local snapshot inventory directory must exist')
    known_files = sorted(path for path in inventory_dir.glob('*.json') if path.name != SNAPSHOT.name)
    if not known_files:
        raise ValueError('The transfer needs a local corpus inventory before capture')
    seen = {pair for path in known_files for pair in local_pairs(source.read_json(path.read_bytes()))}
    if set(PANELS) & seen:
        raise ValueError('A confirmation pair already appears in a workspace snapshot')
    inventory = {'jsonFiles': len(known_files), 'namedPanelPairs': len(seen), 'overlap': 0}
    source.check_revision()
    objects = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for subject, files in zip(SUBJECTS, pool.map(parquet.tree, SUBJECTS), strict=True):
            for model in MODELS:
                name = transfer.object_name(subject, model)
                item = files[name]
                objects[name] = {'size': item['size'], 'oid': item['oid'], 'lfs': item.get('lfs')}
    return design(objects, inventory)


def measure(panel, plan):
    route = prior.route
    subject, matrix = panel['subject'], panel['correctness']
    held = route.CONFIRMATION.holdout(subject, len(matrix[0]))
    start = route.ties.costs.retained_prompts(matrix, held, plan['schedule'])
    uncertainty = route.CONFIRMATION.uncertainty
    finals, points = {'retain-start': start}, {}
    for label in ('strict', CANDIDATE):
        counts, traces, prompts = Counter(), [], []
        for seed, prompt in zip(plan['schedule']['seeds'], start, strict=True):
            used, trace = prior.episode(matrix, held, seed, plan, str(prompt), alternate=label == CANDIDATE)
            counts.update(used)
            traces.append(trace)
            prompts.append(int(trace[-1]['decision']['selected']))
        points[label] = {**counts, 'paidLookups': counts['searchPaid'] + counts['qualificationPaid'],
                         'traceSha256': digest(traces)}
        finals[label] = prompts
    for label in route.GEPA:
        mode, cap = label.split('/')
        finals[label], points[label] = uncertainty.final_prompts(matrix, held, plan['schedule'], plan, mode, int(cap))
    outcomes = {label: uncertainty.case_totals(matrix, held, values) for label, values in finals.items()}
    points['retain-start'] = {'holdoutPasses': sum(outcomes['retain-start'].values()), 'paidLookups': 0}
    if any(sum(outcomes[label].values()) != point['holdoutPasses'] for label, point in points.items()):
        raise ValueError('The final prompt scores must match the measured trajectories')
    return held, points, outcomes


def replay(plan, snapshot, snapshot_sha256):
    with patch.object(transfer, 'EXPECTED', list(PANELS)):
        transfer.check_snapshot(snapshot, plan)
    points, holdouts, vectors = {}, {}, {}
    totals = {label: Counter() for label in METHODS}
    for panel in snapshot['panels']:
        subject, model = panel['subject'], panel['model']
        held, measured, outcomes = measure(panel, plan)
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('Both model panels must use the same ordered holdout')
        margins = vectors.setdefault(subject, {label: [0] * len(held) for label in CONTROLS})
        for label, values in margins.items():
            for i, case in enumerate(held):
                values[i] += outcomes[CANDIDATE][case] - outcomes[label][case]
        for label, values in measured.items():
            totals[label].update({key: value for key, value in values.items() if type(value) is int})
        points[f'{subject}/{model}'] = measured
    ranges = prior.route.transfer.ranges(vectors, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
    cost = totals[CANDIDATE]['paidLookups']
    savings = {label: 1 - cost / totals[label]['paidLookups'] for label in prior.route.GEPA}
    threshold = 100 - plan['minimumLookupSavingPercent']
    budget_passed = all(100 * cost <= threshold * totals[label]['paidLookups'] for label in plan['primaryControls'])
    low, high = ranges['joint']
    gate = 'failed' if not budget_passed or high < 0 else 'passed' if low >= 0 else 'inconclusive'
    return {'designSha256': digest(plan), 'snapshotSha256': snapshot_sha256, 'totals': totals, 'panels': points,
            'uniqueHoldoutCases': sum(map(len, holdouts.values())),
            'comparison': {'jointGate': gate, 'lookupSavings': savings, 'caseRanges': ranges}}


def main():
    cli = ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', action='store_true')
    mode.add_argument('--capture', action='store_true')
    mode.add_argument('--replay', type=Path)
    cli.add_argument('--execute')
    cli.add_argument('--inventory', type=Path, help='local snapshot directory to check before freezing')
    cli.add_argument('--out', type=Path, required=True)
    args = cli.parse_args()
    if args.out.exists() or args.freeze == bool(args.execute) or (args.inventory is not None and not args.freeze):
        cli.error('Supply a fresh output path and the frozen seal for capture or replay')
    if args.freeze:
        plan = freeze(args.inventory if args.inventory is not None else SNAPSHOT.parent)
        result = {'design': plan, 'designSha256': digest(plan)}
    else:
        stored = source.read_json(DESIGN.read_bytes())
        plan = design(stored['design']['objects'], stored['design']['localPreCaptureInventory'])
        seal = digest(plan)
        if digest(stored['design']) != seal or stored['designSha256'] != seal or args.execute != seal:
            cli.error('The design or supplied seal differs from the published plan')
        if args.capture:
            with patch.multiple(transfer, EXPECTED=list(PANELS)):
                result = transfer.capture(plan)
        else:
            if version('gepa') != plan['gepaVersion']:
                cli.error('Use pinned GEPA 0.1.4')
            raw = args.replay.read_bytes()
            result = replay(plan, source.read_json(raw), sha256(raw).hexdigest())
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
