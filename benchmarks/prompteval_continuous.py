"""Carry qualified prompts forward across four recorded optimization cycles."""

import argparse
from collections import deque
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import prompteval_proxy as proxy, prompteval_transfer as transfer, prompteval_witnesses as witnesses
from cpo import Observation, ProposalBatch, ProposalPair, Row, run_cycle, select_pool
from cpo._contract import digest


SEEDS = tuple(range(47101, 47709, 19))
CYCLES = 4
QUALIFY_ROWS = 8
CPO = ('cpo-cycle', 'cpo-pool-two', 'cpo-pool-four', 'cpo-pool-margin')
GEPA = ('gepa-sequential', 'gepa-batched')
ARMS = (*CPO, *GEPA)


def prepare(phase):
    data, sizes, fingerprint = witnesses.read_source('confirmation') if phase == 'development' else proxy.read_source()
    base = transfer.plan(data, sizes, fingerprint)
    root = Path(__file__).resolve().parents[1]
    files = (Path(__file__), Path(witnesses.__file__), Path(proxy.__file__), root / 'cpo/cycle.py')
    sources = {file.relative_to(root).as_posix(): sha256(file.read_bytes()).hexdigest() for file in files}
    return {**base, 'protocol': 'prompteval-continuous-cycles-v1', 'phase': phase, 'subjects': list(sizes),
            'seeds': list(SEEDS), 'arms': list(ARMS), 'primary': CPO[0], 'cycles': CYCLES,
            'qualificationRowsPerCycle': QUALIFY_ROWS, 'minimumQualificationGain': 1,
            'accounting': 'Every search lookup and both sides of each qualification pair are charged',
            'sourceSha256': {**base['sourceSha256'], **sources}}, data


def schedule(case_count, template_count, holdout, seed, plan):
    rng = Random(seed)
    allowed = sorted(set(range(case_count)).difference(holdout))
    rng.shuffle(allowed)
    width = plan['poolSize'] - 1
    count, qualify_rows = plan['cycles'], plan['qualificationRowsPerCycle']
    total_qualify = count * qualify_rows
    prompts = [str(prompt) for prompt in rng.sample(range(template_count), 1 + count * width)]
    training_count, validation_count = plan['trainRows'], plan['validationRows']
    cycles = []
    for index in range(count):
        search_rows = rng.sample(allowed[total_qualify:], training_count + validation_count)
        cycles.append({'seed': rng.randrange(2**31), 'train': search_rows[:training_count],
                       'validation': search_rows[training_count:],
                       'qualify': allowed[index * qualify_rows:(index + 1) * qualify_rows],
                       'alternatives': prompts[1 + index * width:1 + (index + 1) * width]})
    return prompts[0], cycles


def step(arm, matrix, incumbent, layout, plan):
    train, validation, qualify_rows, alternatives, seed = (
        layout[key] for key in ('train', 'validation', 'qualify', 'alternatives', 'seed'))
    candidates = {incumbent, *alternatives}
    combined = train + validation + qualify_rows
    if len(candidates) != 1 + len(alternatives) or len(set(combined)) != len(combined):
        raise ValueError('Cycle needs distinct candidates and disjoint search and qualification')
    allowed, qualification = set(train + validation), set(qualify_rows)
    search_log, quality_log = {}, {}
    budget = plan['evaluationLookupLimit']
    minimum_gain = plan['minimumQualificationGain']

    def observe(prompt, case):
        key = (prompt, case)
        if prompt not in candidates or case not in allowed:
            raise ValueError('Search left its sealed pool')
        if key not in search_log:
            if len(search_log) >= budget:
                raise ValueError('Cycle exceeded its search cap')
            search_log[key] = matrix[int(prompt)][case] == '1'
        return search_log[key]

    def qualify(prompt, row, _repeat):
        case = int(row.id)
        if prompt not in candidates or case not in qualification or (prompt, case) in quality_log:
            raise ValueError('Invalid qualification request')
        result = quality_log[prompt, case] = matrix[int(prompt)][case] == '1'
        return result

    train_rows, validation_rows, cohort = ([Row(str(case), 'task') for case in rows]
                                           for rows in (train, validation, qualify_rows))

    def measure(prompt, row):
        passed = observe(prompt, int(row.id))
        return Observation(passed, {'correct': passed})

    if arm == CPO[0]:
        offered = deque(alternatives[2:])

        def propose(_parent, _feedback, _history, width):
            proposals = tuple(offered.popleft() for _ in range(min(width, len(offered))))
            return ProposalBatch(proposals, exhausted=not offered)

        result = run_cycle(incumbent, train_rows, validation_rows, cohort, measure, propose,
                           metric_limit=budget, rounds=len(alternatives) // 2, train_per_round=plan['probeSize'],
                           qualify=qualify, minimum_gain=minimum_gain, seed=seed,
                           opening_pair=ProposalPair(*alternatives[:2]))
        tentative, promoted = result.search.prompt, result.prompt
        if len(search_log) != result.search.evaluations or len(quality_log) != result.qualification_evaluations:
            raise ValueError('Public CPO cycle lookup totals differ from the journal')
    else:
        if arm in GEPA:
            tentative = transfer.optimize_gepa(incumbent, alternatives, train, validation, observe,
                                               batched=arm == GEPA[1], seed=seed)
        else:
            width = 2 if arm == 'cpo-pool-two' else 4
            tentative = select_pool([incumbent, *alternatives[:width]], validation_rows, measure,
                                    metric_limit=budget, adaptive_rejection=True).prompt
        if arm == 'cpo-pool-margin' and tentative != incumbent:
            gain = sum(search_log[tentative, row] - search_log[incumbent, row] for row in validation)
            if gain == 1:
                current_margin = sum(observe(tentative, row) - observe(incumbent, row)
                                     for row in train[:plan['probeSize']])
                if current_margin < 0:
                    tentative = incumbent
        promoted = incumbent
        if tentative != incumbent:
            order = Random(seed)
            for row in cohort:
                pair = [incumbent, tentative]
                order.shuffle(pair)
                for prompt in pair:
                    qualify(prompt, row, 0)
            gain = sum(quality_log[tentative, row] - quality_log[incumbent, row] for row in qualify_rows)
            if gain >= minimum_gain:
                promoted = tentative
    expected = 2 * len(qualify_rows) if tentative != incumbent else 0
    if len(quality_log) != expected:
        raise ValueError('A different prompt must receive full paired qualification')
    return {'incumbent': incumbent, 'challenger': tentative, 'selected': promoted,
            'searchLookups': len(search_log), 'qualificationLookups': len(quality_log),
            'searchSha256': digest([(prompt, case, passed) for (prompt, case), passed in search_log.items()]),
            'qualification': [(prompt, case, passed) for (prompt, case), passed in quality_log.items()]}


def episode(matrix, holdout, seed, plan):
    initial, layouts = schedule(len(matrix[0]), len(matrix), holdout, seed, plan)
    outcomes = {}
    for arm in ARMS:
        incumbent = initial
        steps = []
        for layout in layouts:
            result = step(arm, matrix, incumbent, layout, plan)
            steps.append(result)
            incumbent = result['selected']
        outcomes[arm] = {'candidate': incumbent, 'steps': steps,
                         'evaluations': sum(item['searchLookups'] + item['qualificationLookups'] for item in steps)}
    for value in outcomes.values():
        value['holdoutPasses'] = sum(matrix[int(value['candidate'])][case] == '1' for case in holdout)
    return {'seed': seed, 'initial': initial, 'initialPasses': sum(matrix[int(initial)][case] == '1' for case in holdout),
            'layouts': layouts, 'arms': outcomes}


def summarize(episodes):
    totals, paired = {}, {}
    for arm in ARMS:
        results = [episode['arms'][arm] for episode in episodes]
        steps = [step for result in results for step in result['steps']]
        totals[arm] = {'holdoutPasses': sum(result['holdoutPasses'] for result in results),
                       'searchLookups': sum(step['searchLookups'] for step in steps),
                       'qualificationLookups': sum(step['qualificationLookups'] for step in steps),
                       'promotions': sum(step['incumbent'] != step['selected'] for step in steps)}
    for arm in CPO:
        paired[arm] = {}
        for control in GEPA:
            outcomes = [(episode['arms'][arm], episode['arms'][control]) for episode in episodes]
            gaps = [a['holdoutPasses'] - b['holdoutPasses'] for a, b in outcomes]
            difference = sum(gaps)
            cost, reference = (sum(result['evaluations'] for result in series) for series in zip(*outcomes))
            paired[arm][control] = {'passDelta': difference, 'lookupDelta': cost - reference,
                                    'episodesWithLoss': sum(gap < 0 for gap in gaps),
                                    'qualified': difference >= 0 and cost <= reference and
                                                 (difference > 0 or 10 * cost <= 9 * reference)}
    return {'initialPasses': sum(episode['initialPasses'] for episode in episodes),
            'totals': totals, 'comparisons': paired}


def execute(plan, source):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        outcomes = [episode(matrix, plan['holdoutCaseIDs'][subject], seed, plan) for seed in plan['seeds']]
        panels[f'{subject}/{model}'] = {**summarize(outcomes), 'episodes': outcomes}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('development', 'retrospective-transfer'), required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    result = execute(plan, data)
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
