"""Test a value-based stopping rule for terminal qualification prechecks."""

import argparse
from functools import lru_cache, partial
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import first_gain_proof_precheck as earlier
from cpo._contract import digest


REFERENCE = '74051c3bef57474309a37fc7fbdf8516b2b31ddea3013bbd080f3800313132c3'
PRIMARY = 'stop-correlated-8'
POLICIES = {PRIMARY: (8, 5), 'stop-independent-8': (8, 1), 'stop-correlated-12': (12, 5)}
BOARDS = tuple(product((1, 2), repeat=3))
BASE_RUN = earlier.run


def counts(rows):
    return tuple((sum(row[side] == 2 for row in rows), sum(row[side] == 1 for row in rows))
                 for side in range(3))


@lru_cache(maxsize=256)
def pass_probability(observed, side, agreement):
    """Condition a fixed exchangeable grade distribution on this case's paid replies."""
    passes = misses = 0
    for case in BOARDS:
        if all(known == 0 or known == actual for known, actual in zip(observed, case, strict=True)):
            weight = agreement if case[0] == case[1] == case[2] else 1
            if case[side] == 2:
                passes += weight
            else:
                misses += weight
    return passes / (passes + misses)


@lru_cache(maxsize=131_072)
def choose_read(rows, fallback, agreement):
    """Minimize estimated additional work, with a fixed cost for falling back."""
    depth = len(rows)
    state = counts(rows)
    gaps = earlier.upper_margins(depth, state)
    if max(gaps) <= 0:
        return 0.0, None, None
    base_upper = depth - state[0][1]
    if max(side[0] for side in state[1:]) > base_upper:
        return float(fallback), None, None
    shared = min(depth - sum(state[0]), max(gaps))
    if shared + sum(max(0, gap - shared) for gap in gaps) >= fallback:
        return float(fallback), None, None

    best = float(fallback), None, None
    for index, observed in enumerate(rows):
        if index and observed == rows[index - 1]:
            continue
        for side, grade in enumerate(observed):
            if grade or (side and gaps[side - 1] <= 0):
                continue
            values = []
            for answer in (1, 2):
                revised = observed[:side] + (answer,) + observed[side + 1:]
                children = tuple(sorted(rows[:index] + (revised,) + rows[index + 1:]))
                values.append(choose_read(children, fallback, agreement)[0])
            probability = pass_probability(observed, side, agreement)
            cost = 1 + (1 - probability) * values[0] + probability * values[1]
            if cost < best[0] - 1e-12:
                best = cost, observed, side
    return best


def initial_board(fallback, agreement, rows, observe, *, allowance, trigger):
    if allowance != 12 or trigger:
        raise ValueError('This stopping rule needs the full four-case board after the usual incumbent prefix')
    board = [(0, 0, 0)] * len(rows)

    def read(index, side):
        grade = observe(side, rows[index])
        if type(grade) is not bool:
            raise ValueError('Qualification requires a Boolean grade')
        before = board[index]
        board[index] = before[:side] + (1 + grade,) + before[side + 1:]
        return grade

    for index in range(len(rows)):
        if not read(index, 0):
            break
    while True:
        state = counts(board)
        if max(earlier.upper_margins(len(rows), state)) <= 0:
            return state
        _, observed, side = choose_read(tuple(sorted(board)), fallback, agreement)
        if side is None:
            return None
        read(board.index(observed), side)


def run(policy, *args, **kwargs):
    if not isinstance(policy, str):
        return BASE_RUN(policy, *args, **kwargs)
    with patch.object(earlier, 'initial_board', partial(initial_board, *POLICIES[policy])):
        return BASE_RUN((12, 0), *args, **kwargs)


def prepare():
    previous, math, prompt, controls = earlier.prepare()
    receipt = earlier.transfer.locked('docs/first-gain-proof-precheck-v1.json', REFERENCE)
    if digest(previous) != receipt['planSha256'] or digest(receipt['plan']) != receipt['planSha256']:
        raise ValueError('Use the published capped precheck and its exact receipts')
    source = Path(__file__)
    plan = {
        'protocol': 'cpo-first-gain-precheck-stopping-v1', 'primary': PRIMARY, 'policies': POLICIES,
        'previousPlanSha256': receipt['planSha256'], 'previousReceiptSha256': REFERENCE,
        'promptolutionCorpusSha256': previous['promptolutionCorpusSha256'],
        'sourceSha256': {**previous['sourceSha256'], str(source.relative_to(earlier.transfer.donor.ROOT)):
                         sha256(source.read_bytes()).hexdigest()},
        'scope': ('In the same terminal cycles, buy a qualification reply only when its expected continuation '
                  'cost beats handing off to validation. Use full-board independent or same-case grade models '
                  'and charge a fixed fallback in lookup units. Only paid exact bounds can skip validation. '
                  'Reproduce prior costs, point controls, layouts and deployments.'),
    }
    return plan, math, prompt, controls, receipt


def replay(math, prompt, controls, receipt, corpus):
    policies = {**earlier.POLICIES, **{name: name for name in POLICIES}}
    with patch.multiple(earlier, POLICIES=policies, run=run):
        results = {'math': earlier.math_replay(math, controls['math']),
                   'promptolution': earlier.prompt_replay(prompt, controls['promptolution']['tasks'], corpus)}
    pairs = [(results['math'][subject][group], original) for subject, groups in receipt['math'].items()
             for group, original in groups.items()]
    pairs.extend((results['promptolution'][group], original) for group, original in receipt['promptolution'].items())
    for measured, original in pairs:
        original_arms = {arm: measured['arms'][arm] for arm in original['arms']}
        if {**measured, 'arms': original_arms} != original:
            raise ValueError('The previous capped precheck receipt must reproduce in every group')
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
