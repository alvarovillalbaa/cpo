"""Measure exact uniform read ordering with prepaid and paired case evidence."""

import argparse
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import two_challenger_uniform_order as independent
from benchmarks import validation_routed_tail_math as math
from cpo._contract import digest
from cpo.full_roster_precheck import fixed_opening
from cpo.full_roster_precheck.validation_routing import run_validation_routed_episode
from cpo.quoted_shared_validation_cycle import _schedule
from cpo.settled_episode import _limit, _MAX_VALIDATION_READS
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run


tail, depth = math.tail, math.depth
archive, transfer = math.archive, math.transfer
ORDERS = ('independent-order', 'prepaid-order', 'paired-order')
MATH_RECEIPT = 'b4dde888bad47ebbf1df551cb68f2b818ea0b6ef1afd8dfff87415e8b1fd5ead'


def best_paired_read(depth, state, funded, observed):
    choices = []
    for side, grades in enumerate(observed):
        passes, misses = state[side]
        if passes + misses == depth or (side and depth - misses <= state[0][0]):
            continue
        hit = independent.select_read(depth, independent.advance(state, side, True))[0]
        miss = independent.select_read(depth, independent.advance(state, side, False))[0]
        rate = (passes + 1) / (passes + misses + 2)
        for index, row in enumerate(funded):
            if row.id in grades:
                continue
            partners = [peer[row.id] for peer in observed if row.id in peer]
            likelihood = (rate + sum(partners) / len(partners)) / 2 if partners else rate
            choices.append((likelihood * hit + (1 - likelihood) * miss, side, index))
    _, side, index = min(choices)
    return side, funded[index]


def exact_screen(incumbent, candidates, rows, evaluate, cap, *, prepaid, paired):
    funded = tuple(row for row, _ in _schedule(len(candidates), rows, cap, False))
    count = len(funded)
    if len(candidates) != 2 or not 3 <= count <= 6 or any(row.critical for row in rows):
        return independent._ORIGINAL(incumbent, candidates, rows, evaluate, cap)

    prompts = (incumbent, *candidates)
    observed = ({}, {}, {})
    state = ((0, 0),) * 3

    def read(side, row):
        nonlocal state
        grade = evaluate(prompts[side], row).passed
        if type(grade) is not bool:
            raise ValueError('Exact uniform ordering requires boolean outcomes')
        observed[side][row.id] = grade
        state = independent.advance(state, side, grade)

    for row in funded:
        if row.id in prepaid:
            read(0, row)
    for measured in range(sum(map(len, observed)), count * len(prompts) + 1):
        winner = independent.certain_winner(count, state)
        if winner == 0:
            return FinalistResult(incumbent, None, measured), None
        if winner is not None and sum(state[0]) == sum(state[winner]) == count:
            nominee = prompts[winner]
            return FinalistResult(nominee, nominee, measured), ((state[0][0], count), (state[winner][0], count))
        if paired and winner is None:
            side, row = best_paired_read(count, state, funded, observed)
        else:
            _, side = independent.select_read(count, state)
            pending = [row for row in funded if row.id not in observed[side]]
            row = min(pending, key=lambda row: observed[0].get(row.id) is not False) if side else pending[0]
        read(side, row)
    raise RuntimeError('Exact uniform ordering must settle within the original quote')


def run_order(mode, incumbent, _training, cycles, evaluate, *, probe, qualify):
    original = fixed_opening._cycle
    opening, prepaid = True, set()

    def collect(prompt, row):
        reply = evaluate(prompt, row)
        if opening and prompt == incumbent:
            prepaid.add(row.id)
        return reply

    def adaptive(schedule, start, cycle, read, proof):
        nonlocal opening
        opening_rows = prepaid if opening else ()
        opening = False
        if schedule != depth.language.OPENING or len(cycle.candidates) != 2:
            return original(schedule, start, cycle, read, proof)
        screen = independent.screen if mode == ORDERS[0] else partial(
            exact_screen, prepaid=opening_rows, paired=mode == ORDERS[2],
        )
        return _run(start, cycle.candidates, cycle.validation, cycle.qualification, read,
                    metric_limit=_MAX_VALIDATION_READS, qualify=proof, seed=cycle.seed,
                    screen=partial(_limit, screen, len(cycle.candidates), tail.UNIFORM_CAP))

    with patch.object(fixed_opening, '_cycle', adaptive):
        return run_validation_routed_episode(incumbent, cycles, collect, qualify=qualify)


RUNNERS = {**tail.RUNNERS, **{name: partial(run_order, name) for name in ORDERS}}


def prepare():
    original, corpus = math.prepare()
    math_receipt = transfer.locked('docs/validation-routed-tail-math-v1.json', MATH_RECEIPT)
    prompt_receipt = transfer.locked('docs/validation-routed-tail-v1.json', math.ARTIFACTS['docs/validation-routed-tail-v1.json'])
    if math_receipt['planSha256'] != digest(original) or digest(math_receipt['plan']) != digest(original):
        raise ValueError('Keep the original math replay and layout')
    files = (Path(__file__), Path(independent.__file__))
    sources = {str(path.relative_to(transfer.donor.ROOT)): sha256(path.read_bytes()).hexdigest() for path in files}
    plan = {**original, 'protocol': 'cpo-validation-routed-exact-order-v1', 'primary': ORDERS[-1],
            'arms': (*math.POLICIES, *ORDERS), 'mathReceiptSha256': MATH_RECEIPT,
            'promptolutionCorpusSha256': transfer.donor.CORPUS_SHA,
            'promptolutionArms': tuple(RUNNERS), 'sourceSha256': {**original['sourceSha256'], **sources},
            'scope': ('Keep the exact uniform nominee and counts on the full funded two-challenger panel. '
                      'Replay the existing independent Beta planner. Then initialize it with incumbent '
                      'grades already paid during routing. The last variant averages the own-side Beta probability '
                      'with observed partner grades on each case and uses the independent planner as its '
                      'cost-to-go estimate. Validate decision, qualification, and deployed prompt parity.'),
            }
    return plan, corpus, math_receipt['results'], prompt_receipt['promptolution']['tasks']


def replay(plan, corpus, math_reference, prompt_reference, prompt_corpus):
    original = archive.play
    comparisons = math.paired
    baseline = None

    def checked(*args):
        nonlocal baseline
        arm = args[-1]
        result = original(*args)
        finalist, steps, paid = result[2]
        if arm in (depth.ROUTED, *ORDERS):
            context = transfer.donor.START, args[2], args[3]
            decisions = context, finalist, steps, [item for item in paid if item[0][0] != 'validation']
            if arm == depth.ROUTED:
                baseline = decisions
            elif decisions != baseline:
                raise ValueError('Read ordering must preserve nominees, deployments and qualification calls')
        return result

    def compare_math(*args):
        direct, matched = {}, {}
        for arm in ORDERS:
            with patch.object(math, 'STALLED', arm):
                direct[arm], matched[arm] = comparisons(*args)
        return direct, matched

    prompt_plan, *_ = archive.prepare()
    prompt_original = transfer.locked('docs/validation-routed-promptolution-v1.json', depth.width.PROMPTOLUTION_SHA)
    policies = {**depth.DEPTHS, **tail.TAILS, **dict.fromkeys(ORDERS)}
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
        tail.verify_totals(math_result[subject], groups)
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
    if (args.execute != seal or not args.out or args.out.exists() or not args.corpus
            or version('gepa') != plan['gepaVersion']):
        parser.error('Replay requires the pinned corpus, current seal, pinned GEPA and a fresh output path')
    prompt_corpus = transfer.donor.load_corpus(args.corpus.read_bytes())
    result = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
              'results': replay(plan, *inputs, prompt_corpus)}
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
