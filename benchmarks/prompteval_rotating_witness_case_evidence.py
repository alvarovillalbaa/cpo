"""Assess the frozen rotating-witness comparison with physical cases paired."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from math import lcm
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import prompteval_rotating_witness_transfer as transfer
from cpo._contract import digest


REFERENCE = transfer.ROOT / 'docs/prompteval-rotating-witness-transfer-results-v1.json'
REFERENCE_SHA = 'e234c20ec178745ca55ff2e01aabf9f75e69377997690302fc615d7d8b6cc5ac'
SEED = 20261121
DRAWS = 4096
CANDIDATE = transfer.CANDIDATE
NATIVE = ('retain-start', *(arm for arm in transfer.POINTS if arm.startswith('gepa-')))
POINTS = (CANDIDATE, *NATIVE)


def prepare():
    raw = REFERENCE.read_bytes()
    if sha256(raw).hexdigest() != REFERENCE_SHA:
        raise ValueError('The published transfer receipt differs from its hash')
    reference = transfer.dataset.read_json(raw)
    baseline = transfer.frozen_design()
    corpus = transfer.DATA.read_bytes()
    corpus_hash = sha256(corpus).hexdigest()
    if (reference['design'] != baseline or reference['corpusSha256'] != corpus_hash or
            reference['executionSha256'] != transfer.execution_plan(digest(baseline), corpus_hash)['executionSha256']):
        raise ValueError('The analysis must use the sealed transfer inputs')
    plan = {'protocol': 'prompteval-rotating-witness-case-evidence-v1', 'transferReceiptSha256': REFERENCE_SHA,
            'transferExecutionSha256': reference['executionSha256'], 'analysisSourceSha256': sha256(
                Path(__file__).read_bytes()).hexdigest(), 'draws': DRAWS, 'seed': SEED,
            'primaryControl': transfer.PRIMARY, 'nativeBudgetPoints': list(NATIVE),
            'averaging': 'Give each subject equal weight and retain its two model panels and all seeds per case.',
            'resampling': ['Resample original holdout cases within each fixed subject.',
                           'Resample subjects, then their original holdout cases, with replacement.'],
            'affordability': ('Use original costs for fixed subjects and resample subject costs with each subject. '
                              'Select the highest-scoring funded fixed native point on every draw.')}
    return plan, baseline, transfer.dataset.read_json(corpus), corpus_hash, reference


def reconstruct(baseline, corpus, corpus_hash, reference):
    subjects = {}
    panel_measure, arm_run = transfer.measure_panel, transfer.replay.run_arm

    def collect(panel, plan):
        subject, matrix = panel['subject'], panel['correctness']
        finals = {arm: [] for arm in POINTS}

        def observe(matrix, holdout, initial, layouts, active, arm, policy):
            result = arm_run(matrix, holdout, initial, layouts, active, arm, policy)
            if arm in finals:
                finals[arm].append(int(result[0]))
            return result

        with patch.object(transfer.replay, 'run_arm', observe):
            outcome = panel_measure(panel, plan)
        holdout = transfer.replay.transfer.holdout(subject, len(matrix[0]))
        group = subjects.setdefault(subject, {'caseIds': holdout, 'decisionsPerCase': 0,
                                              'paidLookups': Counter(), 'cases': {arm: [0] * len(holdout) for arm in POINTS}})
        if holdout != group['caseIds']:
            raise ValueError('Recorded models must score the same cases for each subject')
        group['decisionsPerCase'] += outcome['episodeCount']
        for arm, prompts in finals.items():
            votes = [sum(matrix[prompt][case] == '1' for prompt in prompts) for case in holdout]
            record = outcome['methods'][arm]
            if len(prompts) != outcome['episodeCount'] or sum(votes) != record['holdoutPasses']:
                raise ValueError('Reconstructed case votes differ from the sealed arm totals')
            group['cases'][arm] = [a + b for a, b in zip(group['cases'][arm], votes, strict=True)]
            group['paidLookups'][arm] += record['paidLookups']
        return outcome

    with patch.object(transfer, 'measure_panel', collect):
        replayed = transfer.execute(baseline, corpus, corpus_hash)
    encoded = (json.dumps(replayed, indent=2, sort_keys=True) + '\n').encode()
    if replayed != reference or sha256(encoded).hexdigest() != REFERENCE_SHA:
        raise ValueError('The published transfer receipt did not reproduce byte for byte')
    return subjects


def affordable(scores, costs):
    return min((arm for arm in NATIVE if costs[arm] <= costs[CANDIDATE]),
               key=lambda arm: (-scores[arm], costs[arm], arm))


def ranges(samples, denominator):
    ordered = sorted(samples)
    endpoints = [ordered[(len(ordered) - 1) * q // 1000] for q in (25, 975)]
    return {'interval95PercentagePoints': [round(100 * value / denominator, 9) for value in endpoints],
            'drawsHigher': sum(value > 0 for value in samples),
            'drawsEqual': samples.count(0), 'drawsLower': sum(value < 0 for value in samples)}


def resample(subjects, plan, *, resample_subjects):
    rng = Random(plan['seed'])
    panels = tuple(subjects[subject] for subject in sorted(subjects))
    count = len(panels)
    fixed_cost = sum((Counter(unit['paidLookups']) for unit in panels), Counter())
    denominators = [len(panel['caseIds']) * panel['decisionsPerCase'] for panel in panels]
    common = lcm(*denominators)
    panels = tuple((panel, common // n) for panel, n in zip(panels, denominators, strict=True))
    samples, choices = {arm: [] for arm in (*NATIVE, 'best-affordable-gepa')}, Counter()
    for _ in range(plan['draws']):
        chosen = rng.choices(panels, k=count) if resample_subjects else panels
        scores = Counter()
        costs = Counter() if resample_subjects else fixed_cost
        for panel, weight in chosen:
            size = len(panel['caseIds'])
            indexes = rng.choices(range(size), k=size)
            if resample_subjects:
                costs.update(panel['paidLookups'])
            for arm in POINTS:
                scores[arm] += weight * sum(panel['cases'][arm][i] for i in indexes)
        for arm in NATIVE:
            samples[arm].append(scores[CANDIDATE] - scores[arm])
        control = affordable(scores, costs)
        choices[control] += 1
        samples['best-affordable-gepa'].append(scores[CANDIDATE] - scores[control])
    return {'comparisons': {arm: ranges(values, common * count) for arm, values in samples.items()},
            'affordableSelections': choices}


def native_allocation(subjects, ceiling):
    """Find the best retrospective per-subject native allocation at the same total cost."""
    frontier = {0: (Fraction(0), ())}
    for subject in sorted(subjects):
        panel = subjects[subject]
        denominator = len(panel['caseIds']) * panel['decisionsPerCase']
        scores = {arm: Fraction(sum(panel['cases'][arm]), denominator) for arm in NATIVE}
        extended = {}
        for cost, (score, path) in frontier.items():
            for arm, gain in scores.items():
                value = cost + panel['paidLookups'][arm]
                if value <= ceiling:
                    point = (score + gain, (*path, arm))
                    if value not in extended or point > extended[value]:
                        extended[value] = point
        frontier, best = {}, Fraction(-1)
        for cost, point in sorted(extended.items()):
            if point[0] > best:
                frontier[cost] = point
                best = point[0]
    cost, (score, path) = max(frontier.items(), key=lambda item: (item[1][0], -item[0]))
    return {'paidLookups': cost, 'macroAccuracy': str(score / len(subjects)),
            'nativeArmsBySubject': dict(zip(sorted(subjects), path, strict=True))}


def summarize(subjects, plan):
    costs = sum((Counter(panel['paidLookups']) for panel in subjects.values()), Counter())
    quality = {}
    for arm in POINTS:
        quality[arm] = sum(Fraction(sum(panel['cases'][arm]), len(panel['caseIds']) * panel['decisionsPerCase'])
                           for panel in subjects.values()) / len(subjects)
    best = affordable(quality, costs)
    oracle = native_allocation(subjects, costs[CANDIDATE])
    return {'distinctHeldoutCasesBySubject': {subject: len(panel['caseIds']) for subject, panel in subjects.items()},
            'decisionsPerCaseBySubject': {subject: panel['decisionsPerCase'] for subject, panel in subjects.items()},
            'paidLookupsByArm': costs, 'macroAccuracyByArm': {arm: str(value) for arm, value in quality.items()},
            'observedBestAffordableFixedNative': best,
            'oracleNativeAllocation': {**oracle, 'cpoMacroAccuracyDelta': str(quality[CANDIDATE] - Fraction(
                oracle['macroAccuracy']))},
            'fixedSubjects': resample(subjects, plan, resample_subjects=False),
            'resampledSubjects': resample(subjects, plan, resample_subjects=True),
            'pairedCaseVotesSha256': digest(subjects)}


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
        parser.error('Use the current analysis seal and a fresh output path')
    result = {'plan': plan, 'planSha256': seal, **summarize(reconstruct(*inputs), plan), 'newProviderRequests': 0}
    with args.out.open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
