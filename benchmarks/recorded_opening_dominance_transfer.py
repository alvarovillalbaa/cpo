"""Replay the opening proof on the recorded ARC-AGI and AIME outcomes."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import gepa_cached_opening
from benchmarks.grounded_staged_case_evidence import case_resampling_range
from benchmarks.recorded_math_validation_ties import CORPUS, CORPUS_SHA, DATASETS, ROOT, load_cells, split_cases
from cpo import Observation, ProposalPair, Row
from cpo._contract import digest
from cpo.family_qualification import certify_family_qualification
from cpo.opening_screen_cycle import run_opening_screen_cycle


BASELINE = 'certified-validation'
CANDIDATE = 'opening-dominance'
CONTROLS = ('gepa-rewrite', 'gepa-sequential', 'gepa-batched')
ARMS = (BASELINE, CANDIDATE, *CONTROLS)


def prepare():
    raw = CORPUS.read_bytes()
    if sha256(raw).hexdigest() != CORPUS_SHA:
        raise ValueError('The recorded ARC and AIME matrices differ from their pinned source')
    sources = ('benchmarks/recorded_opening_dominance_transfer.py', 'benchmarks/recorded_math_validation_ties.py',
               'benchmarks/gepa_cached_opening.py', 'benchmarks/grounded_staged_case_evidence.py',
               'cpo/opening_certificate.py', 'cpo/opening_dominance.py', 'cpo/opening_validation.py',
               'cpo/opening_screen_cycle.py', 'cpo/family_qualification.py', 'cpo/paired_qualification.py',
               'cpo/optimizer.py', 'cpo/_contract.py', 'requirements-benchmark.txt')
    plan = {'protocol': 'recorded-opening-dominance-transfer-v1', 'corpusSha256': CORPUS_SHA,
            'gepaVersion': '0.1.4', 'datasets': DATASETS, 'arms': ARMS, 'incumbentGroups': ('root', 'rotated'),
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in sources},
            'openingPair': 'first two distinct nonincumbent IDs in the existing seeded roster',
            'screenSize': 'ceil(two-thirds of validation)', 'metricCap': 'three times validation size',
            'gepaMinibatchSize': 2, 'admission': 'same exact paired family certificate on separate cases',
            'historicalCosts': 'observed ARC evaluator charges, shared supplied proposals excluded for every arm',
            'scoring': 'archived binary grades and one family per archive'}
    return plan, json.loads(raw)


def trial(cells, incumbent, pair, cohorts, seed, arm):
    train, validation, admission, heldout = (tuple(Row(str(case), 'archive', fields=1) for case in cohort)
                                                for cohort in cohorts)
    search_cases = {row.id for row in validation}
    admission_cases = {row.id for row in admission}
    allowed = {incumbent, *pair}
    cap = 3 * len(validation)
    search, proof = [], []

    def evaluate(prompt, row):
        key = (prompt, row.id)
        if prompt not in allowed or row.id not in search_cases or key in search or len(search) >= cap:
            raise ValueError('Search exceeded its paid case, prompt, or budget scope')
        search.append(key)
        passed = bool(cells[prompt][int(row.id)][0])
        return Observation(passed, {}, int(passed))

    def qualify(prompt, row, repeat):
        key = (prompt, row.id)
        if prompt not in allowed or row.id not in admission_cases or key in proof or repeat != 0:
            raise ValueError('Admission exceeded its disjoint case scope')
        proof.append(key)
        return bool(cells[prompt][int(row.id)][0])

    if arm in CONTROLS:
        examples = {row.id: row for row in validation}
        groups = {'validation': [{'id': row.id, 'expected': {'pass': True}} for row in validation]}
        nominee = gepa_cached_opening.select_opening(
            incumbent, pair[:1] if arm == 'gepa-rewrite' else pair, groups,
            lambda prompt, case: evaluate(prompt, examples[case]), cap=cap, seed=seed,
            width=2 if arm == 'gepa-batched' else 1, minibatch_size=2)
    else:
        result = run_opening_screen_cycle(
            incumbent, train, validation, admission, evaluate, opening_pair=ProposalPair(*pair),
            metric_limit=cap, qualify=qualify, qualification_limit=0, screen_rows=(2 * len(validation) + 2) // 3,
            seed=seed, certify_opening=True, certify_validation=True, certify_dominance=arm == CANDIDATE)
        if result.search.evaluations != len(search):
            raise ValueError('The optimizer receipt differs from the paid search ledger')
        nominee = result.search.prompt

    admitted = certify_family_qualification(incumbent, nominee, admission, qualify, seed=seed)
    selected = admitted.prompt
    passed = [int(cells[selected][int(row.id)][0]) for row in heldout]
    totals = {'holdoutPasses': sum(passed), 'searchReads': len(search), 'admissionReads': len(proof),
              'paidReads': len(search) + len(proof)}
    if cells[incumbent][0][1] is not None:
        paid = [cells[prompt][int(case)] for prompt, case in (*search, *proof)]
        totals.update(historicalCostNanodollars=sum(row[1] for row in paid), historicalErrors=sum(row[2] for row in paid))
    return {'nominee': nominee, 'selected': selected, 'admission': admitted.status, 'passed': passed,
            'ledgerSha256': digest([search, proof]), 'totals': totals}


def measure_group(cells, settings, starts):
    size = len(next(iter(cells.values())))
    totals = {arm: Counter() for arm in ARMS}
    traces = {arm: [] for arm in ARMS}
    cases = {arm: [0] * size for arm in ARMS}
    paired_losses = Counter()
    decisions = {arm: {label: Counter(paths=0, gains=0, losses=0) for label in
                       ('onlyCpoPromoted', 'onlyGepaPromoted', 'bothPromotedDifferent')} for arm in CONTROLS}
    different_nominees = Counter()
    changes = Counter(pathsWithMoreReads=0, pathsWithFewerReads=0)
    for seed in settings['seeds']:
        cohorts = split_cases(size, seed, settings['cohorts'])
        for start in starts:
            available = [prompt for prompt in cells if prompt != start]
            pair = Random(f'{seed}/{start}').sample(available, len(available))[:2]
            matched = {arm: trial(cells, start, pair, cohorts, seed, arm) for arm in ARMS}
            before, after = matched[BASELINE], matched[CANDIDATE]
            if any(before[key] != after[key] for key in ('nominee', 'selected', 'admission', 'passed')):
                raise ValueError('The proof changed a fixed-reply opening or admission decision')
            delta = after['totals']['paidReads'] - before['totals']['paidReads']
            changes['pathsWithMoreReads'] += delta > 0
            changes['pathsWithFewerReads'] += delta < 0
            for arm in CONTROLS:
                other = matched[arm]
                different_nominees[arm] += after['nominee'] != other['nominee']
                if after['selected'] == other['selected']:
                    continue
                if other['selected'] == start:
                    route = 'onlyCpoPromoted'
                elif after['selected'] == start:
                    route = 'onlyGepaPromoted'
                else:
                    route = 'bothPromotedDifferent'
                pairs = list(zip(after['passed'], other['passed'], strict=True))
                decisions[arm][route].update(paths=1, gains=sum(a > b for a, b in pairs),
                                             losses=sum(a < b for a, b in pairs))
            for arm, result in matched.items():
                totals[arm].update(result['totals'])
                traces[arm].append([seed, start, pair, result])
                for case, outcome, ours in zip(cohorts[-1], result['passed'], after['passed'], strict=True):
                    cases[arm][case] += outcome
                    paired_losses[arm] += outcome > ours

    controls = {}
    for arm in CONTROLS:
        deltas = [ours - other for ours, other in zip(cases[CANDIDATE], cases[arm], strict=True)]
        controls[arm] = {'addedPasses': sum(deltas), 'pairedLosses': paired_losses[arm],
                         'casesWithLowerTotal': sum(delta < 0 for delta in deltas),
                         'caseResampling95PassDifference': case_resampling_range((deltas,)),
                         'pathsWithDifferentNominees': different_nominees[arm], 'selectionDisagreements': decisions[arm]}
    return {'pathsPerArm': len(traces[CANDIDATE]), 'heldoutUsesPerArm': len(traces[CANDIDATE]) * settings['cohorts'][-1],
            'totals': {arm: {**record, 'traceSha256': digest(traces[arm])} for arm, record in totals.items()},
            'proofReadChanges': changes, 'comparisons': controls}


def measure(plan, data):
    marks = {}
    for dataset, settings in plan['datasets'].items():
        cells = load_cells(dataset, data[dataset]['record'])
        starts = tuple(cells)
        marks[dataset] = {group: measure_group(cells, settings, starts[:1] if group == 'root' else starts[1:])
                          for group in plan['incumbentGroups']}
    return {'plan': plan, 'planSha256': digest(plan), 'results': marks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Use the current seal, GEPA 0.1.4, and a fresh output path')
    report = measure(plan, data)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
