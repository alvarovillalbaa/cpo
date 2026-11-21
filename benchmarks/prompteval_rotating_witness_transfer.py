"""Verify the frozen two-finalist witness screen on other archived model panels."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import independent_mmlu_transfer as dataset
from benchmarks import prompteval_first_proof_budget as discovery
from benchmarks import prompteval_qualification_case_reuse as replay
from benchmarks.gepa_disjoint_cases import CaseRows
from cpo._contract import digest


ROOT = replay.ROOT
DESIGN = ROOT / 'docs/prompteval-rotating-witness-transfer-design-v1.json'
DATA = ROOT / 'benchmarks/data/prompteval-rotating-witness-transfer-v1.json'
DISCOVERY = ROOT / 'docs/prompteval-first-proof-budget-results-v1.json'
DISCOVERY_SHA = '2d507b5b2715ffe0a44dde9c8bb7e9194291ef229a9589ca554a7d984e370f31'
SUBJECTS = ('astronomy', 'clinical_knowledge', 'electrical_engineering', 'high_school_biology',
            'high_school_chemistry', 'human_aging', 'human_sexuality', 'moral_scenarios', 'professional_medicine')
MODELS = ('google_flan_t5_xxl', 'google_gemma_7b_it')
PANELS = [(subject, model) for subject in SUBJECTS for model in MODELS]
CANDIDATE = 'rotating-witness-two-finalists'
PRIMARY = 'gepa-batched/88'
POINTS = {
    'retain-start': 0, CANDIDATE: 56, 'cpo-cycle': 88,
    'gepa-sequential/52': 52, 'gepa-sequential/88': 88, 'gepa-sequential/136': 136,
    'gepa-batched/80': 80, PRIMARY: 88, 'gepa-batched/136': 136,
}
SCHEDULE = {
    'seeds': list(range(57101, 57709, 19)), 'cycles': 4, 'poolSize': 13,
    'trainRows': 12, 'probeSize': 2, 'validationRows': 24,
    'qualificationRowsPerCycle': 8, 'minimumQualificationGain': 1,
    'qualificationPolicy': 'extend-ties', 'maximumExtensionRows': 4,
}


def design():
    raw = DISCOVERY.read_bytes()
    if sha256(raw).hexdigest() != DISCOVERY_SHA:
        raise ValueError('The witness discovery receipt changed')
    parent = dataset.read_json(raw)
    sources = [str(path.relative_to(ROOT)) for path in sorted((ROOT / 'cpo').glob('*.py'))]
    sources.extend((
        'benchmarks/prompteval_rotating_witness_transfer.py', 'benchmarks/independent_mmlu_transfer.py',
        'benchmarks/prompteval_first_proof_budget.py', 'benchmarks/prompteval_qualification_case_reuse.py',
        'benchmarks/prompteval_continuous.py', 'benchmarks/prompteval_transfer.py',
        'benchmarks/gepa_disjoint_cases.py', 'benchmarks/grounded.py', 'requirements-benchmark.txt',
    ))
    fingerprints = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}
    witness_path = 'benchmarks/prompteval_first_proof_budget.py'
    if fingerprints[witness_path] != parent['plan']['sourceSha256'][witness_path]:
        raise ValueError('The frozen witness implementation changed')
    return {
        'protocol': 'prompteval-rotating-witness-transfer-v1', 'discoveryPlanSha256': parent['planSha256'],
        'discoveryResultSha256': DISCOVERY_SHA, 'sourceDataset': dataset.DATASET,
        'sourceRevision': dataset.REVISION, 'templateCount': 100, 'gepaVersion': '0.1.4',
        'subjects': list(SUBJECTS), 'models': list(MODELS), 'sourceSha256': fingerprints,
        'schedule': SCHEDULE, 'searchCaps': POINTS, 'candidate': CANDIDATE, 'primaryControl': PRIMARY,
        'qualificationBank': 'retire-assigned',
        'gate': ('Strictly positive equal-subject held-out accuracy gain overall and after each single subject '
                 'omission, with no increase in total paid lookups, against the primary control.'),
    }


def seal_record(plan):
    return {'design': plan, 'designSha256': digest(plan)}


def execution_plan(design_hash, corpus_hash):
    binding = {'designSha256': design_hash, 'corpusSha256': corpus_hash}
    return {**binding, 'executionSha256': digest(binding)}


def frozen_design():
    plan = design()
    if dataset.read_json(DESIGN.read_bytes()) != seal_record(plan):
        raise ValueError('The pre-capture design differs from the replay source')
    return plan


def select(method, incumbent, layout, observe, plan):
    if method == CANDIDATE:
        return discovery.witness_challenger(incumbent, layout, observe, plan, rotate=True, finalists=2)
    if method == 'retain-start':
        return incumbent
    native = method.split('/')[0]
    with patch.object(replay.transfer, 'LOOKUP_LIMIT', plan['evaluationLookupLimit']):
        return ORIGINAL_SEARCH(native, incumbent, layout, observe, plan)


ORIGINAL_SEARCH = replay.search


def measure_panel(panel, plan):
    subject, matrix = panel['subject'], panel['correctness']
    holdout = replay.transfer.holdout(subject, len(matrix[0]))
    schedule = plan['schedule']
    totals = {method: Counter() for method in POINTS}
    traces = {method: [] for method in POINTS}
    for seed in schedule['seeds']:
        initial, layouts = replay.schedule(len(matrix[0]), len(matrix), holdout, seed, schedule)
        for method, cap in plan['searchCaps'].items():
            active = {**schedule, 'evaluationLookupLimit': cap}
            final, counts, trace = replay.run_arm(matrix, holdout, initial, layouts, active, method,
                                                 plan['qualificationBank'])
            totals[method].update(counts)
            traces[method].append((seed, final, trace))
    initial_reads = len(schedule['seeds']) * schedule['cycles'] * schedule['validationRows']
    for method, counts in totals.items():
        if method.startswith('gepa-') and counts['searchLookups'] <= initial_reads:
            raise ValueError(f'Native control {method} never advanced beyond incumbent validation for {subject}')
    return {'holdoutRows': len(holdout), 'episodeCount': len(schedule['seeds']),
            'methods': {method: {**count, 'traceSha256': digest(traces[method])} for method, count in totals.items()}}


def compare(panels, candidate, control):
    totals = {}
    for subject, panel in panels:
        row = totals.setdefault(subject, Counter())
        row['decisionCount'] += panel['holdoutRows'] * panel['episodeCount']
        for field in ('holdoutPasses', 'paidLookups'):
            row[field] += panel['methods'][candidate][field] - panel['methods'][control][field]
    deltas = {subject: Fraction(row['holdoutPasses'], row['decisionCount']) for subject, row in totals.items()}
    aggregate = sum(deltas.values())
    loo = {subject: (aggregate - effect) / (len(deltas) - 1) for subject, effect in deltas.items()}
    macro = aggregate / len(deltas)
    cost = sum(row['paidLookups'] for row in totals.values())
    return {
        'pooledPassDelta': sum(row['holdoutPasses'] for row in totals.values()), 'paidLookupDelta': cost,
        'macroAccuracyDelta': str(macro), 'leaveOneSubjectOutAccuracyDelta': {k: str(v) for k, v in loo.items()},
        'subjects': {subject: {**row, 'accuracyDelta': str(deltas[subject])} for subject, row in totals.items()},
        'qualifies': macro > 0 and cost <= 0 and all(effect > 0 for effect in loo.values()),
    }


def execute(plan, snapshot, corpus_hash):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the hash-pinned GEPA 0.1.4 package')
    with patch.object(dataset, 'EXPECTED', PANELS):
        dataset.check_corpus(snapshot, plan)
    module = import_module('gepa.optimize_anything')
    original = module.optimize_anything

    def disjoint(*args, dataset, valset, **settings):
        train, validation = [CaseRows({**row, 'id': row['case']} for row in rows) for rows in (dataset, valset)]
        if train.by_id.keys() & validation.by_id.keys():
            raise ValueError('The native control received overlapping row IDs')
        return original(*args, dataset=train, valset=validation, **settings)

    panels = {}
    with patch.object(module, 'optimize_anything', disjoint), patch.object(replay, 'search', select):
        for panel in snapshot['panels']:
            key = f"{panel['subject']}/{panel['model']}"
            panels[key] = measure_panel(panel, plan)
    groups = [(key.split('/')[0], row) for key, row in panels.items()]
    comparisons = {method: compare(groups, CANDIDATE, method) for method in POINTS if method != CANDIDATE}
    return {'design': plan, **execution_plan(digest(plan), corpus_hash), 'panels': panels, 'comparisons': comparisons,
            'newProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--design', action='store_true')
    action.add_argument('--capture')
    action.add_argument('--execution-plan', action='store_true')
    action.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.design:
        if args.out:
            parser.error('Design preview writes to standard output')
        print(json.dumps(seal_record(design()), sort_keys=True, indent=2))
        return
    plan = frozen_design()
    if args.capture is not None:
        if args.capture != digest(plan) or args.out is None or args.out.exists():
            parser.error('Capture requires the frozen design seal and a fresh output path')
        with patch.object(dataset, 'EXPECTED', PANELS):
            result = dataset.capture(plan)
    else:
        raw = DATA.read_bytes()
        corpus_hash = sha256(raw).hexdigest()
        binding = execution_plan(digest(plan), corpus_hash)
        if args.execution_plan:
            if args.out:
                parser.error('Execution plan preview writes to standard output')
            print(json.dumps(binding, indent=2, sort_keys=True))
            return
        if args.execute != binding['executionSha256'] or args.out is None or args.out.exists():
            parser.error('Replay requires the seal binding the frozen design and corpus, and a fresh path')
        result = execute(plan, dataset.read_json(raw), corpus_hash)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
