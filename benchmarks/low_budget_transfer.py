"""Replicate a frozen low-budget CPO comparison on new archived MMLU panels."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import independent_mmlu_cost_uncertainty as prior
from benchmarks import independent_mmlu_transfer as transfer
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
SUBJECTS = ('clinical_knowledge', 'college_physics', 'electrical_engineering', 'high_school_biology',
            'moral_scenarios', 'professional_medicine')
MODELS = ('google_flan_ul2', 'mistralai_mixtral_8x7b_instruct_v01')
EXPECTED = [(subject, model) for subject in SUBJECTS for model in MODELS]
PRIOR_SHA256 = '6151722d65597149fc2b234825a6fd99b5fff7218009f4f572b9de21b9627f00'
CANDIDATE = 'cpo-28'
PRIMARY = 'gepa-sequential-31'
METHODS = {
    CANDIDATE: (transfer.gepa.CPO, 28),
    'cpo-52': (transfer.gepa.CPO, 52),
    PRIMARY: (transfer.gepa.METHODS[0], 31),
    'gepa-batched-39': (transfer.gepa.METHODS[1], 39),
    'gepa-batched-44': (transfer.gepa.METHODS[1], 44),
}


def design():
    previous, *_ = prior.prepare()
    raw = (ROOT / 'docs/independent-mmlu-cost-uncertainty-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != PRIOR_SHA256 or transfer.read_json(raw)['planSha256'] != digest(previous):
        raise ValueError('The source audit differs from its published replay')
    parent = transfer.design()
    paths = (Path(__file__), Path(transfer.__file__), Path(prior.__file__))
    return {
        'protocol': 'cpo-low-budget-transfer-v1', 'subjects': list(SUBJECTS), 'models': list(MODELS),
        **{k: parent[k] for k in ('sourceDataset', 'sourceRevision', 'sourceLicense', 'templateCount',
                                 'validationRows', 'schedule', 'holdout', 'gepaVersion')},
        'priorPlanSha256': digest(previous), 'priorReportSha256': PRIOR_SHA256,
        'sourceSha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in paths},
        'methods': {name: {'optimizer': method, 'cap': cap} for name, (method, cap) in METHODS.items()},
        'primaryComparison': {'candidate': CANDIDATE, 'control': PRIMARY, 'minimumLookupSavingPercent': 10,
                              'minimumLowerRangePassDifference': 0},
        'bootstrapDraws': 4096, 'bootstrapSeed': 20261120,
        'scope': ('Fixed settings selected from the earlier archive before capture. Draw paired holdout cases '
                  'within each new subject and keep both models and all episodes together.'),
    }


def check_and_collect(plan, raw):
    corpus = transfer.read_json(raw)
    with patch.object(transfer, 'EXPECTED', EXPECTED):
        transfer.check_corpus(corpus, plan)
    panels, by_subject = {}, {}
    for p in corpus['panels']:
        subject, model, matrix = (p[k] for k in ('subject', 'model', 'correctness'))
        held = transfer.transfer.holdout(subject, len(matrix[0]))
        rows = by_subject.setdefault(subject, {case: Counter() for case in held})
        if tuple(rows) != tuple(held):
            raise ValueError('Both models must share ordered holdout cases')
        points = {}
        for name, (optimizer, cap) in METHODS.items():
            finals, point = prior.final_prompts(matrix, held, plan['schedule'], plan, optimizer, cap)
            case_scores = prior.case_totals(matrix, held, finals)
            if sum(case_scores.values()) != point['holdoutPasses']:
                raise ValueError('Per-case counts differ from the recorded evaluator totals')
            for case, count in case_scores.items():
                rows[case][name] += count
            points[name] = point
        starts = [int(archive.continuous.schedule(len(matrix[0]), len(matrix), held, seed, plan['schedule'])[0])
                  for seed in plan['schedule']['seeds']]
        initial = prior.case_totals(matrix, held, starts)
        points['retain-start'] = {'holdoutPasses': sum(initial.values()), 'paidLookups': 0}
        for case, count in initial.items():
            rows[case]['retain-start'] += count
        panels[f'{subject}/{model}'] = {'holdoutCaseIDs': held, 'methods': points}
    return panels, by_subject


def case_resampling(plan, by_subject, comparisons):
    rng = Random(plan['bootstrapSeed'])
    names = sorted(by_subject)
    values = {control: [tuple(case[CANDIDATE] - case[control] for case in by_subject[name].values())
                        for name in names] for control in comparisons}
    draws = {control: [] for control in comparisons}
    for _ in range(plan['bootstrapDraws']):
        samples = [rng.choices(range(len(by_subject[name])), k=len(by_subject[name])) for name in names]
        for control, columns in values.items():
            draws[control].append(sum(scores[i] for scores, ids in zip(columns, samples, strict=True) for i in ids))
    result = {}
    for control, series in draws.items():
        ordered = sorted(series)
        result[control] = {'observedPassDifference': sum(sum(row) for row in values[control]),
                           'interval95PassDifferences': [ordered[(len(series) - 1) * q // 1000] for q in (25, 975)],
                           'drawsCpoHigher': sum(p > 0 for p in series),
                           'drawsTied': series.count(0), 'drawsCpoLower': sum(p < 0 for p in series)}
    return result


def classify_primary(plan, cpo, control, range_):
    gate = plan['primaryComparison']
    max_cost = 100 - gate['minimumLookupSavingPercent']
    threshold = gate['minimumLowerRangePassDifference']
    if 100 * cpo['paidLookups'] > max_cost * control['paidLookups'] or range_[1] < threshold:
        return 'failed'
    if range_[0] >= threshold:
        return 'passed'
    return 'inconclusive'


def replay(plan, raw):
    panels, by_subject = check_and_collect(plan, raw)
    totals = {}
    for panel in panels.values():
        for method, point in panel['methods'].items():
            totals.setdefault(method, Counter()).update({k: point[k] for k in ('holdoutPasses', 'paidLookups')})
    controls = ('retain-start', 'cpo-52', PRIMARY, 'gepa-batched-39', 'gepa-batched-44')
    comparisons = case_resampling(plan, by_subject, controls)
    primary = classify_primary(plan, totals[CANDIDATE], totals[PRIMARY], comparisons[PRIMARY]['interval95PassDifferences'])
    if any(row['observedPassDifference'] != totals[CANDIDATE]['holdoutPasses'] - totals[ref]['holdoutPasses']
           for ref, row in comparisons.items()):
        raise ValueError('The paired aggregation must reproduce the original outcome counts')
    return {'plan': plan, 'planSha256': digest(plan), 'corpusSha256': sha256(raw).hexdigest(),
            'panels': panels, 'totals': totals, 'comparisons': comparisons, 'primaryGate': primary,
            'distinctCasesBySubject': {name: len(cases) for name, cases in by_subject.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--design', action='store_true')
    mode.add_argument('--capture', action='store_true')
    mode.add_argument('--replay', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan = design()
    seal = digest(plan)
    if args.design and args.execute is None and args.out is None:
        print(json.dumps({'design': plan, 'designSha256': seal}, sort_keys=True, indent=2))
        return
    if args.design or args.execute != seal or args.out is None or args.out.exists():
        parser.error('Capture and replay require the sealed design and a fresh output path')
    if args.capture:
        with patch.object(transfer, 'EXPECTED', EXPECTED):
            result = transfer.capture(plan)
    else:
        if version('gepa') != plan['gepaVersion']:
            raise ValueError('Use the pinned GEPA version')
        result = replay(plan, args.replay.read_bytes())
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
