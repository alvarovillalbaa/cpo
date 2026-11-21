"""Spend extra validation reads when the recorded two-finalist screen ties."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from math import lcm
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import prompteval_rotating_witness_case_evidence as evidence
from benchmarks import prompteval_rotating_witness_transfer as transfer
from cpo._contract import digest


ROOT = transfer.ROOT
BASELINE = transfer.CANDIDATE
ADAPTIVE = 'extend-tied-finalists'
ALWAYS = 'always-extend-finalists'
EXTENSIONS = (ADAPTIVE, ALWAYS)
CONTROLS = ('retain-start', 'gepa-sequential/52', 'gepa-batched/80', transfer.PRIMARY, 'gepa-batched/136')
EXTRA_CASES = 3
EXTERNAL = ROOT / 'benchmarks/data/independent-mmlu-transfer-v1.json'
EXTERNAL_SHA = '4f759dfcf44b4e591d3dd3aa15c3394b43fd131ee50816820df4a4bfc510beb4'


def choose(incumbent, layout, observe, limits, *, always, counts):
    seen = {}

    def measure(prompt, case):
        key = prompt, case
        if key not in seen:
            seen[key] = observe(prompt, case)
        return seen[key]

    original = transfer.discovery.witness_challenger(incumbent, layout, measure, limits, rotate=True, finalists=2)
    validation = list(layout['validation'])
    Random(layout['seed']).shuffle(validation)
    first_pass = next((case for case in validation if seen.get((incumbent, case)) is True), None)
    first_miss = next((case for case in validation if seen.get((incumbent, case)) is False), None)
    finalists = tuple(
        prompt for prompt in layout['alternatives']
        if seen.get((prompt, first_miss)) is True and (first_pass is None or seen.get((prompt, first_pass)) is True)
    )
    if len(finalists) != 2:
        return original
    extra_cases = [case for case in validation if case not in (first_pass, first_miss)]
    if not extra_cases:
        return original
    tie, *remaining = extra_cases
    if any((prompt, tie) not in seen for prompt in finalists):
        return original
    scores = {prompt: int(seen[prompt, tie]) for prompt in finalists}
    counts['twoFinalistCycles'] += 1
    counts['firstCaseTies'] += len(set(scores.values())) == 1
    for case in remaining[:EXTRA_CASES]:
        if len(seen) + 2 > limits['evaluationLookupLimit'] or (not always and len(set(scores.values())) > 1):
            break
        for prompt in finalists:
            scores[prompt] += measure(prompt, case)
        counts['extraValidationReads'] += 2
    selected = max(finalists, key=scores.__getitem__)
    counts['differentNominations'] += selected != original
    return selected


def prepare():
    source, baseline, prior_corpus, _, reference = evidence.prepare()
    raw = EXTERNAL.read_bytes()
    if sha256(raw).hexdigest() != EXTERNAL_SHA:
        raise ValueError('The additional archived subject panels differ from the pinned source')
    external = transfer.dataset.read_json(raw)
    if {p['subject'] for p in prior_corpus['panels']} & {p['subject'] for p in external['panels']}:
        raise ValueError('The additional archive shares subjects with the previous transfer')
    plan = {'protocol': 'prompteval-witness-tie-budget-v1', 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'caseAnalysisSourceSha256': source['analysisSourceSha256'],
            'priorExecutionSha256': reference['executionSha256'], 'priorReceiptSha256': source['transferReceiptSha256'],
            'additionalCorpusSha256': EXTERNAL_SHA, 'priorSchedule': baseline['schedule'],
            'searchCeiling': baseline['searchCaps'][BASELINE], 'extraPairedValidationCases': EXTRA_CASES,
            'methods': [BASELINE, *EXTENSIONS], 'primary': ADAPTIVE, 'additionalNativeControls': list(CONTROLS),
            'pairedCaseDraws': evidence.DRAWS, 'resamplingSeed': evidence.SEED,
            'scope': ('Keep the original fixed candidate roster and independent qualification. '
                      'The adaptive arm stops at the first difference in validation scores. '
                      'The always-extend arm pays for each of the same paired probes that fits.')}
    data = {'prior-transfer': prior_corpus['panels'], 'additional-subjects': external['panels']}
    return plan, baseline, data, reference


def paired_ranges(subjects, method, plan):
    bands = []
    panels = list(subjects.values())
    normalizer = lcm(*(len(group['cases'][method]) * group['decisionsPerCase'] for group in panels))
    for sample_subjects in (False, True):
        rng = Random(plan['resamplingSeed'])
        totals = []
        for _ in range(plan['pairedCaseDraws']):
            drawn = rng.choices(panels, k=len(panels)) if sample_subjects else panels
            total = 0
            for group in drawn:
                a, b = (group['cases'][arm] for arm in (method, BASELINE))
                denominator = len(a) * group['decisionsPerCase']
                total += normalizer // denominator * sum(a[i] - b[i] for i in rng.choices(range(len(a)), k=len(a)))
            totals.append(total)
        bands.append(evidence.ranges(totals, normalizer * len(panels)))
    return {'casesWithinFixedSubjects': bands[0], 'subjectsAndCases': bands[1]}


def measure_panels(panels, baseline, plan, expected=None):
    arms = (BASELINE, *EXTENSIONS)
    if expected is None:
        arms += CONTROLS
    caps = {method: baseline['searchCaps'].get(method, plan['searchCeiling']) for method in arms}
    original = transfer.replay.run_arm
    totals, subjects, receipts = {arm: Counter() for arm in arms}, {}, {}
    activity = {method: Counter() for method in EXTENSIONS}

    def route(method, incumbent, layout, observe, active):
        if method in EXTENSIONS:
            return choose(incumbent, layout, observe, active, always=method == ALWAYS, counts=activity[method])
        return transfer.select(method, incumbent, layout, observe, active)

    for panel in panels:
        final = {arm: [] for arm in arms}

        def capture(matrix, holdout, initial, layouts, active, arm, policy):
            result = original(matrix, holdout, initial, layouts, active, arm, policy)
            final[arm].append(int(result[0]))
            return result

        with (patch.object(transfer, 'POINTS', caps), patch.object(transfer.replay, 'run_arm', capture),
              patch.object(transfer.replay, 'search', route)):
            point = transfer.measure_panel(panel, {**baseline, 'searchCaps': caps})
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        key = f'{subject}/{model}'
        methods = point['methods']
        if expected is not None and methods[BASELINE] != expected[key]['methods'][BASELINE]:
            raise ValueError(f'The frozen rotating-witness control changed for {key}')
        held = transfer.replay.transfer.holdout(subject, len(matrix[0]))
        group = subjects.setdefault(subject, {'decisionsPerCase': 0, 'caseIds': held,
                                              'cases': {arm: [0] * len(held) for arm in arms}})
        if held != group['caseIds']:
            raise ValueError('The models must use the same physical holdout cases')
        group['decisionsPerCase'] += point['episodeCount']
        for arm in arms:
            votes = [sum(matrix[prompt][row] == '1' for prompt in final[arm]) for row in held]
            if point['episodeCount'] != len(final[arm]) or methods[arm]['holdoutPasses'] != sum(votes):
                raise ValueError('Recorded case totals disagree with episode selections')
            group['cases'][arm] = [a + b for a, b in zip(group['cases'][arm], votes, strict=True)]
            totals[arm].update({k: methods[arm][k] for k in ('holdoutPasses', 'paidLookups')})
        receipts[key] = methods
    macros = {arm: str(sum(Fraction(sum(group['cases'][arm]), len(group['caseIds']) * group['decisionsPerCase'])
                           for group in subjects.values()) / len(subjects)) for arm in arms}
    if expected is not None:
        for arm in CONTROLS:
            total = totals.setdefault(arm, Counter())
            by_subject = {}
            for key, panel in expected.items():
                total.update({key: panel['methods'][arm][key] for key in ('holdoutPasses', 'paidLookups')})
                subject = key.split('/')[0]
                outcome = by_subject.setdefault(subject, Counter())
                outcome['passes'] += panel['methods'][arm]['holdoutPasses']
                outcome['decisions'] += panel['holdoutRows'] * panel['episodeCount']
            macros[arm] = str(sum(Fraction(row['passes'], row['decisions']) for row in by_subject.values()) /
                              len(by_subject))
    return {'totals': totals, 'macroAccuracy': macros, 'panels': receipts, 'extraSearchActivity': activity,
            'distinctCases': sum(len(group['caseIds']) for group in subjects.values()),
            'caseRangesVsOriginalWitness': {name: paired_ranges(subjects, name, plan) for name in EXTENSIONS}}


def execute(plan, baseline, data, reference):
    if version('gepa') != baseline['gepaVersion']:
        raise ValueError('Use the pinned GEPA 0.1.4 package')
    module = import_module('gepa.optimize_anything')
    original = module.optimize_anything

    def split_safe(*args, dataset, valset, **settings):
        train, validation = [transfer.CaseRows({**row, 'id': row['case']} for row in rows) for rows in (dataset, valset)]
        if train.by_id.keys() & validation.by_id.keys():
            raise ValueError('Native GEPA train and validation case IDs overlapped')
        return original(*args, dataset=train, valset=validation, **settings)

    with patch.object(module, 'optimize_anything', split_safe):
        results = {phase: measure_panels(panels, baseline, plan, reference['panels'] if phase == 'prior-transfer' else None)
                   for phase, panels in data.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'phases': results, 'newProviderRequests': 0}


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
        parser.error('Use the current design seal and a fresh output path')
    result = execute(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
