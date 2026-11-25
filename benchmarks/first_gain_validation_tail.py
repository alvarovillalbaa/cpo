"""Recover first-gain nominations after a short validation panel stalls."""

import argparse
from dataclasses import replace
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import first_gain_validation_width as previous
from cpo._contract import digest
from cpo.single_finalist import FinalistResult


first_gain = previous.first_gain
transfer = previous.transfer
REFERENCE = '5c3db0d93b49136d74e4c792279899c61c54a7da2fb51e7f03e4438ea40cdb16'
PREFIX = 3
PRIMARY = 'first-gain/stalled-tail-6'
TAILS = {f'first-gain/stalled-tail-{cap}': cap for cap in (3, 6, 9)}
_RUN_WIDTH = previous.run


def screen(extra, incumbent, candidates, rows, evaluate, cap, *, prepaid, read_limit):
    """Widen after retention only, carrying every paid grade into the full panel."""
    funded = tuple(row for row, _ in first_gain._schedule(len(candidates), rows,
                                                         min(cap, first_gain._UNIFORM_CAP), False))
    if len(funded) <= PREFIX:
        return previous.screen(PREFIX, incumbent, candidates, rows, evaluate, cap,
                               prepaid=prepaid, read_limit=read_limit)

    depth = len(funded)
    prompts = (incumbent, *candidates)
    sides = {prompt: side for side, prompt in enumerate(prompts)}
    state = ((0, 0),) * len(prompts)
    seen = ({}, {}, {})

    def read(prompt, row):
        nonlocal state
        reply = evaluate(prompt, row)
        if type(reply.passed) is not bool:
            raise ValueError('First-gain validation requires an exact Boolean grade')
        side = sides[prompt]
        seen[side][row.id] = reply.passed
        state = first_gain._advance(state, side, reply.passed)
        return reply

    short, counts = previous.screen(PREFIX, incumbent, candidates, funded, read, cap,
                                    prepaid=prepaid, read_limit=read_limit)
    if short.finalist is not None:
        return short, counts

    paid = short.evaluations
    limit = min(paid + extra, depth * len(prompts), read_limit, cap)
    while True:
        winner = first_gain._strict_winner(depth, state)
        if winner is not None:
            finalist = prompts[winner]
            rates = tuple((state[side][0], sum(state[side])) for side in (0, winner))
            return FinalistResult(finalist, finalist, paid), rates
        _, _, side = first_gain._choose_read(depth, state, limit - paid)
        if side is None:
            return replace(short, evaluations=paid), None
        pending = (row for row in funded if row.id not in seen[side])
        row = min(pending, key=lambda row: seen[0].get(row.id) is not False) if side else next(pending)
        read(prompts[side], row)
        paid += 1


def run(setting, incumbent, training, cycles, evaluate, *, probe, qualify):
    if setting not in TAILS:
        return _RUN_WIDTH(setting, incumbent, training, cycles, evaluate, probe=probe, qualify=qualify)
    with patch.object(first_gain, '_screen', partial(screen, TAILS[setting])):
        return previous.earlier.parity.packaged(18, incumbent, training, cycles, evaluate,
                                               probe=probe, qualify=qualify)


def prepare():
    parent, math, prompt, controls, comparison = previous.prepare()
    reference = transfer.locked('docs/first-gain-validation-width-v1.json', REFERENCE)
    if digest(parent) != reference['planSha256'] or digest(reference['plan']) != reference['planSha256']:
        raise ValueError('Use the published fixed-width comparison and exact receipts')
    source = Path(__file__)
    return {
        'protocol': 'cpo-first-gain-validation-tail-v1', 'primary': PRIMARY, 'prefix': PREFIX, 'tailReadCaps': TAILS,
        'previousReceiptSha256': REFERENCE, 'previousPlanSha256': reference['planSha256'],
        'promptolutionCorpusSha256': parent['promptolutionCorpusSha256'],
        'sourceSha256': {**parent['sourceSha256'], str(source.relative_to(transfer.donor.ROOT)):
                         sha256(source.read_bytes()).hexdigest()},
        'scope': ('Keep a short proof-backed nominee and its existing independent qualification. If the three-case '
                  'screen retains, widen to the original funded panel with all paid grades and an extra allowance '
                  'of three, six, or nine distinct reads within the original search cap. Nominate from the wide '
                  'screen only after a strict full-panel gain. Reproduce all previous controls and layouts.'),
    }, math, prompt, controls, comparison, reference


def replay(math, prompt, controls, comparison, reference, corpus):
    modes = {**previous.WIDTHS, **{name: name for name in TAILS}}
    with patch.multiple(previous, WIDTHS=modes, run=run):
        results = previous.replay(math, prompt, controls, comparison, corpus)
    pairs = [(results['math'][subject][group], original) for subject, groups in reference['math'].items()
             for group, original in groups.items()]
    pairs.extend((results['promptolution'][group], original) for group, original in reference['promptolution'].items())
    for current, original in pairs:
        if current['episodes'] != original['episodes'] or any(
                current['arms'][name] != arm for name, arm in original['arms'].items()):
            raise ValueError('Every published fixed-width result must reproduce')
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
    corpus = transfer.donor.load_corpus(args.corpus.read_bytes())
    result = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, **replay(*inputs, corpus)}
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
