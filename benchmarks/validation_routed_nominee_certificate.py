"""Stop narrow uniform validation once the full-panel nominee is certified."""

import argparse
from functools import lru_cache, partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import validation_routed_certificate_floor as floor
from cpo._contract import digest
from cpo.quoted_shared_validation_cycle import _schedule
from cpo.single_finalist import FinalistResult


order = floor.previous
math, tail, depth = order.math, order.tail, order.depth
archive, transfer, independent = order.archive, order.transfer, order.independent
MODES = ('certificate-paid-rates', 'certificate-neutral-rates')
FLOOR_RECEIPT = '6a7194d43269da853d4c91d45e390c406a8d47af2d1b7313f3d87d1ac6a6b599'


@lru_cache(maxsize=None)
def next_read(depth, state):
    if independent.certain_winner(depth, state) is not None:
        return 0, None
    options = []
    for side, (passes, misses) in enumerate(state):
        if passes + misses == depth or (side and depth - misses <= state[0][0]):
            continue
        hit = next_read(depth, independent.advance(state, side, True))[0]
        miss = next_read(depth, independent.advance(state, side, False))[0]
        options.append((1 + (hit * (passes + 1) + miss * (misses + 1)) / (passes + misses + 2), side))
    return min(options)


def screen(incumbent, candidates, rows, evaluate, cap, *, prepaid, use_rates):
    funded = tuple(row for row, _ in _schedule(len(candidates), rows, cap, False))
    depth = len(funded)
    if len(candidates) != 2 or not 3 <= depth <= 6 or any(row.critical for row in rows):
        return independent._ORIGINAL(incumbent, candidates, rows, evaluate, cap)

    prompts = (incumbent, *candidates)
    state = ((0, 0),) * len(prompts)
    seen = ({}, {}, {})

    def observe(side, row):
        nonlocal state
        grade = evaluate(prompts[side], row).passed
        if type(grade) is not bool:
            raise ValueError('An exact nominee certificate requires boolean grades')
        state = independent.advance(state, side, grade)
        seen[side][row.id] = grade

    for row in funded:
        if row.id in prepaid:
            observe(0, row)
    for paid in range(sum(map(len, seen)), depth * len(prompts) + 1):
        winner = independent.certain_winner(depth, state)
        if winner == 0:
            return FinalistResult(incumbent, None, paid), None
        if winner is not None:
            counts = tuple((state[side][0], sum(state[side])) for side in (0, winner))
            nominee = prompts[winner]
            return FinalistResult(nominee, nominee, paid), counts if use_rates else ((0, 0), (0, 0))
        _, side = next_read(depth, state)
        pending = [row for row in funded if row.id not in seen[side]]
        row = min(pending, key=lambda row: seen[0].get(row.id) is not False) if side else pending[0]
        observe(side, row)
    raise RuntimeError('The full funded panel must settle the nominee')


def run_certificate(use_rates, incumbent, training, cycles, evaluate, *, probe, qualify):
    def certify(incumbent, candidates, rows, evaluate, cap, *, prepaid, paired):
        return screen(incumbent, candidates, rows, evaluate, cap, prepaid=prepaid, use_rates=use_rates)

    with patch.object(order, 'exact_screen', certify):
        return order.run_order('prepaid-order', incumbent, training, cycles, evaluate, probe=probe, qualify=qualify)


RUNNERS = {**tail.RUNNERS, **{arm: partial(run_certificate, index == 0) for index, arm in enumerate(MODES)}}


def prepare():
    base, corpus, math_reference, prompt_reference = order.prepare()
    floor_plan, *_ = floor.prepare()
    bound = transfer.locked('docs/validation-routed-certificate-floor-v1.json', FLOOR_RECEIPT)
    if bound['planSha256'] != digest(floor_plan) or digest(bound['plan']) != digest(floor_plan):
        raise ValueError('Keep the original certificate floor and its baseline')
    file = Path(__file__)
    plan = {**base, 'protocol': 'cpo-validation-routed-nominee-certificate-v1', 'primary': MODES[0],
            'arms': (*math.POLICIES, *MODES), 'promptolutionArms': tuple(RUNNERS),
            'sourceSha256': {**floor_plan['sourceSha256'], str(file.relative_to(transfer.donor.ROOT)):
                             sha256(file.read_bytes()).hexdigest()},
            'floorReceiptSha256': FLOOR_RECEIPT,
            'scope': ('Reuse paid routing grades and use the Beta model to minimize modeled remaining reads '
                      'to an exact nominee instead of full scores. Stop when the complete-panel nominee '
                      'and incumbent-first ties are settled by paid bounds. Run the same exact independent '
                      'qualification with either observed counts or neutral priors to order its replies. '
                      'Require per-cycle nominee and deployment parity and measure all paid calls.')}
    return plan, corpus, math_reference, prompt_reference, bound['results']


def replay(plan, corpus, math_reference, prompt_reference, floor_reference, prompt_corpus):
    original = archive.play
    old_compare = math.paired
    baseline = None

    def checked(*args):
        nonlocal baseline
        arm = args[-1]
        result = original(*args)
        if arm in (depth.ROUTED, *MODES):
            context = transfer.donor.START, args[2], args[3]
            decisions = context, result[2][:2]
            if arm == depth.ROUTED:
                baseline = decisions
            elif decisions != baseline:
                raise ValueError('Each cycle must preserve the exact nominee, schedule and deployed prompt')
        return result

    def compare_math(*args):
        direct, matched = {}, {}
        for arm in MODES:
            with patch.object(math, 'STALLED', arm):
                direct[arm], matched[arm] = old_compare(*args)
        return direct, matched

    prompt_plan, *_ = archive.prepare()
    prompt_original = transfer.locked('docs/validation-routed-promptolution-v1.json', depth.width.PROMPTOLUTION_SHA)
    policies = {**depth.DEPTHS, **tail.TAILS, **dict.fromkeys(MODES)}
    with patch.object(archive, 'play', checked):
        with patch.object(depth, 'DEPTHS', policies), patch.dict(archive.RUNNERS, {name: RUNNERS[name] for name in policies}):
            prompt_result = depth.prompt_replay(prompt_plan, prompt_original, prompt_corpus)
        tail.verify_totals(prompt_result['tasks'], prompt_reference)
        with patch.multiple(math, POLICIES=plan['arms'], paired=compare_math), patch.dict(tail.RUNNERS, RUNNERS):
            math_result = math.replay(plan, corpus)
    for subject, groups in math_reference.items():
        for group, prior in groups.items():
            current = math_result[subject][group]
            if current['layoutSha256'] != prior['layoutSha256']:
                raise ValueError('The trial layout must reproduce')
            current['costFloors'] = floor_reference['math'][subject][group]
        tail.verify_totals(math_result[subject], groups)
    for task, point in prompt_result['tasks'].items():
        point['costFloors'] = floor_reference['promptolution'][task]
    return {'math': math_result, 'promptolution': prompt_result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if not (args.execute or args.out or args.corpus):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if (args.execute != seal or args.out is None or args.out.exists() or args.corpus is None
            or version('gepa') != plan['gepaVersion']):
        parser.error('Replay requires the pinned corpus, current seal, pinned GEPA and a fresh output path')
    prompt_corpus = transfer.donor.load_corpus(args.corpus.read_bytes())
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
              'results': replay(plan, *inputs, prompt_corpus)}
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
