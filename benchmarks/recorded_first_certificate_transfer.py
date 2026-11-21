"""Transfer the frozen first-certificate policy to three recorded task cohorts."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import prompteval_transfer as source, recorded_first_training_certificate as study
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
ARCHIVES = {
    'prompteval-transfer-v1.json': '2c79f692d761cb816e0066269b1f330f7d961f885177f166e067221f10263243',
    'independent-mmlu-transfer-v1.json': '4f759dfcf44b4e591d3dd3aa15c3394b43fd131ee50816820df4a4bfc510beb4',
    'tie-extension-cross-benchmark-v1.json': '8a820a2254fac09d1550af8ddcfc35775938f10f2fa2e1f0c7c72c58dc256103',
}
REFERENCE = 'docs/recorded-first-training-certificate-results-v1.json'
REFERENCE_SHA256 = 'ec23a9fba84c50f7a69bec6c0af41e68df674a5f3fd6425e8b2c5e1446fb7897'
METHODS = (study.FIRST, *study.parent.ARMS, 'retain-start')
CONTROL_NAMES = study.prior.CONTROLS


def load_panels():
    panels, known = [], {}
    for name, expected in ARCHIVES.items():
        raw = (ROOT / 'benchmarks/data' / name).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError('Use the published archived outcome matrices')
        for entry in json.loads(raw)['panels']:
            subject, model, matrix = (entry[key] for key in ('subject', 'model', 'correctness'))
            count = len(matrix[0])
            cohort = entry.get('benchmark', 'MMLU')
            by_model = known.setdefault((cohort, subject), {})
            cases = tuple(entry.get('caseIDs', range(count)))
            templates = tuple(map(str, entry.get('templateIDs', range(len(matrix)))))
            identity = cases, templates
            if (model in by_model or len(matrix) != 100 or len(set(cases)) != count or len(set(templates)) != 100
                    or any(len(row) != count or set(row) - {'0', '1'} for row in matrix)
                    or any(item != identity for item in by_model.values())):
                raise ValueError('Both model panels must preserve the case and template alignment')
            by_model[model] = identity
            panels.append((cohort, subject, model, matrix))
    if any(len(models) != 2 for models in known.values()):
        raise ValueError('Each transfer subject must have exactly two aligned model panels')
    return panels


def prepare():
    parent, _, _ = study.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or json.loads(raw)['planSha256'] != digest(parent):
        raise ValueError('Use the exact published first-certificate policy')
    panels = load_panels()
    paths = (Path(__file__), Path(source.__file__))
    plan = {**{key: parent[key] for key in ('gepaVersion', 'searchCap', 'minimumLookupSavingPercent',
                                           'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-first-certificate-transfer-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': REFERENCE_SHA256, 'archivesSha256': ARCHIVES,
            'sourceSha256': {str(path.resolve().relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
                             for path in paths},
            'methods': METHODS, 'seeds': source.SEEDS, 'challengers': 8,
            'caseCounts': parent['datasets']['aime']['cohorts'][:3],
            'panels': [(cohort, subject, model) for cohort, subject, model, _ in panels],
            'scope': 'Apply the frozen AIME search and split widths without refitting to MMLU, BBH, and LMentry. '
                     'Keep each archived subject holdout and use paired seeds, starts, rosters, and disjoint '
                     'roles for both model panels. Use the same expected-cost qualification across CPO and GEPA. '
                     'The gate requires the original cost and paired quality thresholds in each cohort.'}
    return plan, panels


def schedule(subject, case_count, prompt_count, seed, plan):
    held = source.holdout(subject, case_count)
    train, validation, proof = plan['caseCounts']
    available = sorted(set(range(case_count)) - set(held))
    sampled = Random(f'{seed}/{subject}/first-certificate/cases').sample(available, train + validation + proof)
    prompts = Random(f'{seed}/{subject}/first-certificate/roster').sample(range(prompt_count), 1 + plan['challengers'])
    start, *roster = map(str, prompts)
    return start, roster, (sampled[:train], sampled[train:train + validation], sampled[train + validation:], held)


def measure_panel(matrix, subject, plan):
    cells = {str(index): tuple((int(passed), None, False) for passed in vector) for index, vector in enumerate(matrix)}
    totals = {arm: Counter() for arm in METHODS}
    traces = {arm: [] for arm in METHODS}
    held = source.holdout(subject, len(matrix[0]))
    scores = {arm: [0] * len(held) for arm in METHODS}
    for seed in plan['seeds']:
        start, roster, cohorts = schedule(subject, len(matrix[0]), len(matrix), seed, plan)
        cap = plan['searchCap']
        for arm in METHODS:
            if arm == 'retain-start':
                point, trace, grades = study.math.run_trial(cells, start, roster, cohorts, seed, arm, cap)
            else:
                point, trace, grades = study.trial(cells, start, roster, cohorts, seed, cap, arm)
            if (point['searchLookups'] > cap or point['qualificationLookups'] > 2 * len(cohorts[2])
                    or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']):
                raise ValueError('A transfer trial exceeded its search or proof allowance')
            totals[arm].update(point)
            traces[arm].append(trace)
            for i, value in enumerate(grades):
                scores[arm][i] += value
    return ({arm: {**count, 'traceSha256': digest(traces[arm])} for arm, count in totals.items()}, scores)


def compare(plan, totals, vectors):
    modes = (*CONTROL_NAMES.values(), study.prior.CANDIDATE, 'retain-start')
    rng = Random(plan['bootstrapSeed'])
    samples = {arm: [] for arm in (*modes, 'joint')}
    for _ in range(plan['bootstrapDraws']):
        diff = Counter()
        for subject in sorted(vectors):
            rows = vectors[subject]
            indices = rng.choices(range(len(rows[study.FIRST])), k=len(rows[study.FIRST]))
            for arm in modes:
                diff[arm] += sum(rows[study.FIRST][i] - rows[arm][i] for i in indices)
        for arm in modes:
            samples[arm].append(diff[arm])
        samples['joint'].append(min(diff[arm] for arm in CONTROL_NAMES.values()))
    ranges = {arm: study.math.interval(values) for arm, values in samples.items()}
    native_ranges = {**ranges, **{arm: ranges[name] for arm, name in CONTROL_NAMES.items()}}
    matched = {**totals, **{arm: totals[name] for arm, name in CONTROL_NAMES.items()}}
    verdict = study.math.comparison(study.FIRST, matched, native_ranges, plan)
    return {'caseSensitivityRanges': ranges, 'gate': verdict['gate'], 'lookupSavingFractions': verdict['lookupSavingFractions']}


def replay(plan, panels):
    cohorts = defaultdict(dict)
    for cohort, subject, model, matrix in panels:
        counts, scores = measure_panel(matrix, subject, plan)
        cohorts[cohort][subject, model] = (counts, scores)
    report = {}
    for cohort, entries in cohorts.items():
        totals = {arm: Counter() for arm in METHODS}
        vectors = {}
        details = {}
        for (subject, model), (counts, scores) in entries.items():
            details[f'{subject}/{model}'] = {'totals': counts, 'holdoutCases': len(scores[study.FIRST])}
            combined = vectors.setdefault(subject, {arm: [0] * len(scores[arm]) for arm in METHODS})
            for arm in METHODS:
                totals[arm].update({key: value for key, value in counts[arm].items() if key != 'traceSha256'})
                combined[arm] = [old + new for old, new in zip(combined[arm], scores[arm], strict=True)]
        verdict = compare(plan, totals, vectors)
        report[cohort] = {'totals': totals, 'panels': details, 'caseVectorsBySubject': vectors, **verdict}
    eligible = [row['gate'] for row in report.values()]
    gate = 'failed' if 'failed' in eligible else 'passed' if all(value == 'passed' for value in eligible) else 'inconclusive'
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'cohorts': report, 'gate': gate}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, panels)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
