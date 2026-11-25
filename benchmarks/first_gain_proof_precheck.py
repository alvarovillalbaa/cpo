"""Test whether independent rejection certificates can avoid a validation screen."""

import argparse
from collections import Counter
from dataclasses import replace
from functools import lru_cache, partial
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import certified_first_gain_api_parity as parity
from cpo._contract import digest
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.full_roster_precheck import certified_nomination, first_gain
from cpo.paired_qualification import QualificationDecision, QualificationObservation
from cpo.single_finalist import FinalistResult


sweep, transfer = parity.sweep, parity.transfer
BASE = 'strict-gain/cap-18'
POLICIES = {'proof-early-8': (8, 0), 'proof-early-12': (12, 0),
            'proof-early-8-after-two': (8, 2), 'proof-early-12-after-two': (12, 2)}
PARITY_SHA = 'e925474dbc13eb4564f5645a856ae313a7bcb50309cbe5636c4ecd63bbc0e585'
_RUN = first_gain._run


def upper_margins(depth, state):
    return tuple(depth - state[0][0] - state[side][1] for side in (1, 2))


@lru_cache(maxsize=32_768)
def choose_read(depth, state, remaining):
    """Order reads by modeled chance of proving both exact rejections."""
    gaps = upper_margins(depth, state)
    if max(gaps) <= 0:
        return 1.0, 0.0, None
    base_upper = depth - state[0][1]
    if max(side[0] for side in state[1:]) > base_upper:
        return 0.0, 0.0, None
    base_room = depth - sum(state[0])
    shared = min(base_room, max(gaps))
    if shared + sum(max(0, gap - shared) for gap in gaps) > remaining:
        return 0.0, 0.0, None
    options = []
    for side, (passes, misses) in enumerate(state):
        if passes + misses == depth or (side and gaps[side - 1] <= 0):
            continue
        hit, miss = (choose_read(depth, certified_nomination._advance(state, side, grade), remaining - 1)
                     for grade in (True, False))
        rate = (passes + 1) / (passes + misses + 2)
        chance = rate * hit[0] + (1 - rate) * miss[0]
        work = 1 + rate * hit[1] + (1 - rate) * miss[1]
        options.append((chance, work, side))
    return min(options, key=lambda item: (-round(item[0], 14), round(item[1], 12), item[2]))


def initial_board(rows, observe, *, allowance, trigger):
    """Pay the original incumbent prefix, then try to certify two rejections."""
    state = ((0, 0),) * 3
    seen = (set(), set(), set())
    depth = len(rows)

    def read(side, row):
        nonlocal state
        grade = observe(side, row)
        if type(grade) is not bool:
            raise ValueError('A qualification certificate requires a Boolean grade')
        state = certified_nomination._advance(state, side, grade)
        seen[side].add(row.id)
        return grade

    for row in rows:
        if not read(0, row):
            break
    if state[0][0] < trigger:
        return None
    while max(upper_margins(depth, state)) > 0:
        _, _, side = choose_read(depth, state, allowance - sum(map(len, seen)))
        if side is None:
            return None
        read(side, next(row for row in rows if row.id not in seen[side]))
    return state


def prechecked(allowance, trigger, incumbent, candidates, validation, rows, evaluate, *,
               metric_limit, qualify, seed, screen):
    if len(rows) != 4 or len({row.family for row in rows}) != 1 or any(row.critical for row in rows):
        return _RUN(incumbent, candidates, validation, rows, evaluate, metric_limit=metric_limit,
                    qualify=qualify, seed=seed, screen=screen)
    ledger = {}
    prompts = (incumbent, *candidates)

    def read(prompt, row, repeat):
        key = prompt, row.id, repeat
        if key not in ledger:
            grade = qualify(prompt, row, repeat)
            if type(grade) is not bool:
                raise ValueError('A qualification certificate requires a Boolean grade')
            ledger[key] = QualificationObservation(*key, grade)
        return ledger[key].passed

    state = initial_board(rows, lambda side, row: read(prompts[side], row, 0), allowance=allowance, trigger=trigger)
    if state is not None:
        lower = max(side[0] - len(rows) + state[0][1] for side in state[1:])
        decision = QualificationDecision('rejected', incumbent, tuple(ledger.values()), lower,
                                         max(upper_margins(len(rows), state)))
        return FixedPoolCycleResult(FinalistResult(incumbent, None, 0), decision)
    result = _RUN(incumbent, candidates, validation, rows, evaluate, metric_limit=metric_limit,
                  qualify=read, seed=seed, screen=screen)
    return replace(result, qualification=replace(result.qualification, observations=tuple(ledger.values())))


def run(policy, incumbent, _training, cycles, evaluate, *, probe, qualify):
    cycles = tuple(cycles)
    final_ids = tuple(row.id for row in cycles[-1].qualification)

    def terminal(start, candidates, validation, rows, evaluator, **settings):
        if tuple(row.id for row in rows) == final_ids:
            return prechecked(*policy, start, candidates, validation, rows, evaluator, **settings)
        return _RUN(start, candidates, validation, rows, evaluator, **settings)

    with patch.object(first_gain, '_run', terminal):
        return first_gain.run_first_gain_episode(incumbent, cycles, evaluate, qualify=qualify)


def prepare():
    package, math, prompt = parity.prepare()
    reference = transfer.locked('docs/first-gain-episode-parity-v1.json', PARITY_SHA)
    if digest(package) != reference['planSha256'] or digest(reference['plan']) != reference['planSha256']:
        raise ValueError('Use the published 18-read package and exact parity baseline')
    native = transfer.locked('docs/certified-nomination-gepa-sweep-v1.json', parity.math_study.SWEEP_SHA)
    runner = Path(__file__)
    plan = {'protocol': 'cpo-first-gain-proof-precheck-v1', 'primary': 'proof-early-8-after-two',
            'baseline': BASE, 'policies': POLICIES, 'parityReceiptSha256': PARITY_SHA,
            'promptolutionCorpusSha256': transfer.donor.CORPUS_SHA,
            'nativeSweepReceiptSha256': parity.math_study.SWEEP_SHA,
            'sourceSha256': {**package['sources'], str(runner.relative_to(transfer.donor.ROOT)):
                             sha256(runner.read_bytes()).hexdigest()},
            'scope': ('Preserve every deployment while moving some independent replies before validation in the last '
                      'cycle. Only skip its uniform screen after both challengers cannot qualify. Otherwise run the '
                      'original selector and reuse exact qualification replies. Compare published native and halving '
                      'point counts at each realized budget and compute an optimistic rejection-certificate floor.')}
    return plan, math, prompt, native


def best_affordable(totals, budget, metric, allowed):
    arm = min((arm for arm in allowed if totals[arm][metric] <= budget),
              key=lambda arm: (-totals[arm]['holdoutPasses'], totals[arm][metric], arm))
    return {'arm': arm, **totals[arm]}


def verify_group(config, layout, matrix, prices, expected, controls, *, math):
    runners = {BASE: partial(parity.packaged, 18), **{name: partial(run, setting) for name, setting in POLICIES.items()}}
    totals = {name: Counter() for name in runners}
    changes = {name: Counter() for name in POLICIES}
    floor = Counter()
    for start, windows, held, seed in layout:
        with patch.object(transfer.donor, 'START', start):
            measured = {name: parity.measure(runner, config, matrix, windows, seed, name)[0]
                        for name, runner in runners.items()}
        retained, baseline, (_, steps, ledger) = measured[BASE]
        for name, (chosen, cost, (_, decisions, paid)) in measured.items():
            if chosen != retained or decisions[:-1] != steps[:-1]:
                raise ValueError('The precheck must preserve all earlier decisions and the final deployed prompt')
            totals[name].update(cost, holdoutPasses=sum(int(matrix[chosen][case]) for case in held))
            if math:
                totals[name]['promotions'] += chosen != start
            if prices is not None:
                totals[name][sweep.math.PRICE] += sum(prices[prompt][case] for (_, prompt, case), _ in paid)
            if name != BASE:
                delta = cost['paidLookups'] - baseline['paidLookups']
                changes[name].update(cheaper=int(delta < 0), dearer=int(delta > 0), same=int(delta == 0))
        roster, _, validation, proof = windows[-1]
        if steps[-1][0] == first_gain._UNIFORM:
            incumbent = steps[-2][2] if len(steps) > 1 else start
            passes = tuple(sum(int(matrix[prompt][case]) for case in proof) for prompt in (incumbent, *roster))
            if passes[0] >= max(passes[1:]):
                floor['allChallengersRejected'] += 1
                opening = 0 if len(steps) > 1 else 1 + int(matrix[incumbent][validation[0]])
                terminal_cases = set((*validation, *proof))
                terminal_paid = sum(case in terminal_cases for (_, _, case), _ in ledger)
                # With hindsight, every observed incumbent pass reduces the required misses on both challengers.
                certificate = 2 * len(proof) - passes[0]
                floor['possibleLookupSavings'] += max(0, terminal_paid - opening - certificate)
    if totals[BASE] != expected['totals'][BASE]:
        raise ValueError('The original 18-read score and both cost tallies must reproduce')
    metrics = ('paidLookups', sweep.math.PRICE) if prices is not None else ('paidLookups',)
    results = {}
    for name, stats in totals.items():
        allowed = tuple(controls['totals'])
        native = tuple(arm for arm in allowed if arm.startswith('gepa-'))
        simple = tuple(arm for arm in allowed if arm.startswith('halving/'))
        results[name] = {'totals': stats, 'matchedPoints': {
            metric: {'nativeGepa': best_affordable(controls['totals'], stats[metric], metric, (*native, transfer.BASE)),
                     'halving': best_affordable(controls['totals'], stats[metric], metric, (*simple, transfer.BASE))}
            for metric in metrics}}
        if name in changes:
            results[name]['episodeCostChanges'] = changes[name]
    return {'arms': results, 'episodes': len(layout), 'optimisticEarlyRejection': floor}


def math_replay(math, controls):
    config, corpus, expected = math
    original = sweep.math.math
    results = {}
    for subject, settings in config['datasets'].items():
        cells = original.math.load_cells(subject, corpus[subject]['record'])
        matrix = {prompt: ''.join(str(int(cell[0])) for cell in values) for prompt, values in cells.items()}
        prices = ({prompt: tuple(cell[1] for cell in values) for prompt, values in cells.items()}
                  if subject == 'arc' else None)
        results[subject] = {}
        for group in config['incumbentGroups']:
            layouts = [(start, [(tuple(roster), tuple(train), tuple(val[:config['validationPerCycle']]),
                                 tuple(proof[:config['admissionPerCycle']]))], held, seed)
                       for start, roster, (train, val, proof, held), seed in original.trials(
                           cells, settings, group, config['rosterWidth'])]
            prior = expected[subject][group]
            if digest(layouts) != prior['layoutSha256']:
                raise ValueError('The original math episode layouts must reproduce')
            results[subject][group] = verify_group(config, layouts, matrix, prices, prior, controls[subject][group],
                                                   math=True)
    return results


def prompt_replay(prompt, controls, corpus):
    config, expected, old_holdouts = prompt
    results = {}
    for name in config['tasks']:
        panel = corpus[name]
        held = sorted(Random(f"{config['holdoutSeed']}/{name}").sample(
            range(len(panel['caseIDs'])), transfer.donor.HOLDOUT))
        if digest([panel['caseIDs'][index] for index in held]) != old_holdouts[name]['heldCaseSha256']:
            raise ValueError('The original Promptolution holdout must reproduce')
        layouts = [(transfer.donor.START, transfer.layout(config, name, seed, held), held, seed)
                   for seed in config['seeds']]
        prior = expected[name]
        if digest([(seed, windows) for _, windows, _, seed in layouts]) != prior['layoutSha256']:
            raise ValueError('The original Promptolution episode layouts must reproduce')
        results[name] = verify_group(config, layouts, panel['correctness'], None, prior, controls[name], math=False)
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute', metavar='PLAN_SHA256')
    cli.add_argument('--out', type=Path)
    cli.add_argument('--corpus', type=Path)
    args = cli.parse_args()
    plan, math, prompt, controls = prepare()
    seal = digest(plan)
    if not (args.execute or args.out or args.corpus):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or args.corpus is None:
        cli.error('Use the current seal, pinned corpus and a fresh output path')
    corpus = transfer.donor.load_corpus(args.corpus.read_bytes())
    result = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'math': math_replay(math, controls['math']),
              'promptolution': prompt_replay(prompt, controls['promptolution']['tasks'], corpus)}
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
