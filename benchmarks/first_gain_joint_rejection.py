"""Test whether paid validation and qualification can jointly rule out both challengers."""

import argparse
from dataclasses import replace
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import first_gain_precheck_stopping as previous
from cpo._contract import digest
from cpo.paired_qualification import QualificationObservation
from cpo.quoted_shared_validation_cycle import _schedule
from cpo.single_finalist import FinalistResult


earlier = previous.earlier
first_gain = earlier.first_gain
REFERENCE = '528b3704411f969432c186ae811c5545960b615ebcc29950dcbd31dbe3770b38'
PRIMARY = 'joint-after-4'
POLICIES = {PRIMARY: (4, 8), 'joint-after-7': (7, 8), 'joint-after-4-high': (4, 12),
            'joint-after-7-high': (7, 12)}


class RejectedPool(Exception):
    """Both challengers are blocked on the terminal cycle."""


@lru_cache(maxsize=131_072)
def choose_read(board, blocked, fallback):
    state = previous.counts(board)
    size = len(board)
    gaps = earlier.upper_margins(size, state)
    rivals = tuple(side for side in (1, 2) if side not in blocked and gaps[side - 1] > 0)
    if not rivals:
        return 0.0, None, None
    base_upper = size - state[0][1]
    if any(state[side][0] > base_upper for side in rivals):
        return float(fallback), None, None
    remaining = tuple(gaps[side - 1] for side in rivals)
    shared = min(size - sum(state[0]), max(remaining))
    if shared + sum(max(0, gap - shared) for gap in remaining) >= fallback:
        return float(fallback), None, None

    best = float(fallback), None, None
    for index, observed in enumerate(board):
        if index and observed == board[index - 1]:
            continue
        for side in (0, *rivals):
            if observed[side]:
                continue
            children = []
            for answer in (1, 2):
                replacement = observed[:side] + (answer,) + observed[side + 1:]
                revised = tuple(sorted(board[:index] + (replacement,) + board[index + 1:]))
                children.append(choose_read(revised, blocked, fallback)[0])
            probability = previous.pass_probability(observed, side, 5)
            cost = 1 + (1 - probability) * children[0] + probability * children[1]
            if cost < best[0] - 1e-12:
                best = cost, observed, side
    return best


def qualify_joint(board, blocked, fallback, observe):
    """Try to prove rejection of every validation-eligible challenger."""
    blocked = tuple(blocked)
    while True:
        margins = earlier.upper_margins(len(board), previous.counts(board))
        if all(side in blocked or margins[side - 1] <= 0 for side in (1, 2)):
            return True
        _, pattern, side = choose_read(tuple(sorted(board)), blocked, fallback)
        if side is None:
            return False
        index = board.index(pattern)
        grade = observe(side, index)
        if type(grade) is not bool:
            raise ValueError('Joint qualification requires an exact Boolean grade')
        board[index] = pattern[:side] + (1 + grade,) + pattern[side + 1:]


def screened(preview, fallback, incumbent, candidates, validation, proof, evaluate, *,
             metric_limit, qualify, seed, screen):
    funded = tuple(row for row, _ in _schedule(len(candidates), validation,
                                              min(metric_limit, first_gain._UNIFORM_CAP), False))
    if (len(proof) != 4 or any(row.critical for row in proof) or len({row.family for row in proof}) != 1
            or not 3 <= len(funded) <= 6):
        return earlier._RUN(incumbent, candidates, validation, proof, evaluate, metric_limit=metric_limit,
                            qualify=qualify, seed=seed, screen=screen)
    prompts = (incumbent, *candidates)
    proof_index = {row.id: index for index, row in enumerate(proof)}
    board = [(0, 0, 0)] * len(proof)
    proof_ledger = {}
    validation_ledger = {}
    state = ((0, 0),) * 3
    attempted = False

    def read_proof(prompt, row, repeat):
        key = prompt, row.id, repeat
        if key not in proof_ledger:
            grade = qualify(prompt, row, repeat)
            if type(grade) is not bool:
                raise ValueError('Joint qualification requires an exact Boolean grade')
            proof_ledger[key] = QualificationObservation(*key, grade)
        return proof_ledger[key].passed

    def observe(prompt, row, repeat):
        grade = read_proof(prompt, row, repeat)
        index, side = proof_index[row.id], prompts.index(prompt)
        before = board[index]
        board[index] = before[:side] + (1 + grade,) + before[side + 1:]
        return grade

    def read_pending_proof(side, index):
        return read_proof(prompts[side], proof[index], 0)

    def run_screen(start, roster, cases, read, cap):
        def next_validation(prompt, row):
            nonlocal state, attempted
            if len(validation_ledger) == preview and not attempted:
                attempted = True
                margins = earlier.upper_margins(len(funded), state)
                blocked = tuple(side for side in (1, 2) if margins[side - 1] <= 0)
                if qualify_joint(board, blocked, fallback, read_pending_proof):
                    raise RejectedPool
            value = read(prompt, row)
            validation_ledger[prompt, row.id] = value.passed
            state = earlier.certified_nomination._advance(state, prompts.index(prompt), value.passed)
            return value

        try:
            return screen(start, roster, cases, next_validation, cap)
        except RejectedPool:
            return FinalistResult(start, None, len(validation_ledger)), None

    result = earlier._RUN(incumbent, candidates, validation, proof, evaluate, metric_limit=metric_limit,
                          qualify=observe, seed=seed, screen=run_screen)
    return replace(result, qualification=replace(result.qualification, observations=tuple(proof_ledger.values())))


def run(policy, incumbent, training, cycles, evaluate, *, probe, qualify):
    if not isinstance(policy, str) or policy not in POLICIES:
        return previous.run(policy, incumbent, training, cycles, evaluate, probe=probe, qualify=qualify)
    cycles = tuple(cycles)
    last = tuple(row.id for row in cycles[-1].qualification)

    def terminal(start, candidates, validation, proof, reader, **settings):
        if tuple(row.id for row in proof) == last:
            return screened(*POLICIES[policy], start, candidates, validation, proof, reader, **settings)
        return earlier._RUN(start, candidates, validation, proof, reader, **settings)

    with patch.object(first_gain, '_run', terminal):
        return first_gain.run_first_gain_episode(incumbent, cycles, evaluate, qualify=qualify)


def prepare():
    plan, math, prompt, controls, _ = previous.prepare()
    receipt = earlier.transfer.locked('docs/first-gain-precheck-stopping-v1.json', REFERENCE)
    if digest(plan) != receipt['planSha256'] or digest(receipt['plan']) != receipt['planSha256']:
        raise ValueError('Use the published expected-cost stopping replay and its exact receipts')
    source = Path(__file__)
    return {
        'protocol': 'cpo-first-gain-joint-rejection-v1', 'primary': PRIMARY, 'settings': POLICIES,
        'previousPlanSha256': receipt['planSha256'], 'previousReceiptSha256': REFERENCE,
        'promptolutionCorpusSha256': plan['promptolutionCorpusSha256'],
        'sourceSha256': {**plan['sourceSha256'], str(source.relative_to(earlier.transfer.donor.ROOT)):
                         sha256(source.read_bytes()).hexdigest()},
        'scope': ('In the same terminal cycles, run the original validation order for a fixed prefix. Certify '
                  'retention if each contender is blocked by paid validation bounds or paid independent '
                  'qualification bounds. Otherwise finish the original nomination and reuse qualification '
                  'replies. Reproduce every archived deployment, earlier cycle, cost point and control.'),
    }, math, prompt, controls, receipt


def replay(math, prompt, controls, receipt, corpus):
    policies = {**earlier.POLICIES, **{name: name for name in (*previous.POLICIES, *POLICIES)}}
    with patch.multiple(earlier, POLICIES=policies, run=run):
        results = {'math': earlier.math_replay(math, controls['math']),
                   'promptolution': earlier.prompt_replay(prompt, controls['promptolution']['tasks'], corpus)}
    pairs = [(results['math'][subject][group], original) for subject, groups in receipt['math'].items()
             for group, original in groups.items()]
    pairs.extend((results['promptolution'][group], original) for group, original in receipt['promptolution'].items())
    for measured, original in pairs:
        original_arms = {arm: measured['arms'][arm] for arm in original['arms']}
        if {**measured, 'arms': original_arms} != original:
            raise ValueError('The previous spending and holdout results must reproduce')
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute', metavar='PLAN_SHA256')
    cli.add_argument('--corpus', type=Path)
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if not (args.execute or args.out or args.corpus):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or args.corpus is None:
        cli.error('Use the current seal, pinned corpus and a fresh output path')
    corpus = earlier.transfer.donor.load_corpus(args.corpus.read_bytes())
    result = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, **replay(*inputs, corpus)}
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
