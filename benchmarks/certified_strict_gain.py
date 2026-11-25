"""Replay a capped search for any exact validation gain on the math archives."""

import argparse
from functools import lru_cache, partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import certified_nomination_gepa_sweep as sweep
from cpo._contract import digest
from cpo.full_roster_precheck import certified_nomination as certified
from cpo.quoted_shared_validation_cycle import _schedule
from cpo.single_finalist import FinalistResult


SWEEP_SHA = 'd266328c7d95fdcfcea5dfa3bc9b0339a898dac59a195051d8fea5ade156d629'
CAPS = {f'strict-gain/cap-{cap}': cap for cap in (10, 14, 18)}


def strict_winner(depth, state):
    upper = depth - state[0][1]
    return next((side for side in (1, 2) if state[side][0] > upper), None)


@lru_cache(maxsize=131_072)
def choose_read(depth, state, allowance):
    """Maximize modeled chance of a proof, then minimize expected reads."""
    if strict_winner(depth, state) is not None:
        return 1.0, 0.0, None
    incumbent_passes, incumbent_misses = state[0]
    possible = tuple(side for side in (1, 2) if depth - state[side][1] > incumbent_passes)
    if not possible or all(depth - incumbent_misses - state[side][0] >= allowance for side in possible):
        return 0.0, 0.0, None

    options = []
    for side in (0, *possible):
        passes, misses = state[side]
        if passes + misses == depth:
            continue
        hit, miss = (choose_read(depth, certified._advance(state, side, grade), allowance - 1)
                     for grade in (True, False))
        rate = (passes + 1) / (passes + misses + 2)
        chance = rate * hit[0] + (1 - rate) * miss[0]
        cost = 1 + rate * hit[1] + (1 - rate) * miss[1]
        options.append((chance, cost, side))
    return min(options, key=lambda option: (-round(option[0], 14), round(option[1], 12), option[2]))


def screen(limit, incumbent, candidates, rows, evaluate, cap, *, prepaid, use_validation_rates):
    """Keep the full funded panel and cap how many of its grades can be read."""
    funded = tuple(row for row, _ in _schedule(len(candidates), rows, min(cap, certified._UNIFORM_CAP), False))
    depth = len(funded)
    if not 3 <= depth <= 6:
        return _ORIGINAL_SCREEN(incumbent, candidates, rows, evaluate, cap, prepaid=prepaid,
                                use_validation_rates=use_validation_rates)

    prompts = (incumbent, *candidates)
    state = ((0, 0),) * len(prompts)
    seen = ({}, {}, {})

    def read(side, row):
        nonlocal state
        grade = evaluate(prompts[side], row).passed
        if type(grade) is not bool:
            raise ValueError('Strict validation certificates require boolean grades')
        seen[side][row.id] = grade
        state = certified._advance(state, side, grade)

    for row in funded:
        if row.id in prepaid:
            read(0, row)
    spent = sum(map(len, seen))
    limit = min(limit, depth * len(prompts), cap)
    while True:
        winner = strict_winner(depth, state)
        if winner is not None:
            nominee = prompts[winner]
            rates = tuple((state[side][0], sum(state[side])) for side in (0, winner))
            return FinalistResult(nominee, nominee, spent), rates if use_validation_rates else ((0, 0), (0, 0))
        _, _, side = choose_read(depth, state, limit - spent)
        if side is None:
            return FinalistResult(incumbent, None, spent), None
        pending = (row for row in funded if row.id not in seen[side])
        row = min(pending, key=lambda row: seen[0].get(row.id) is not False) if side else next(pending)
        read(side, row)
        spent += 1


_ORIGINAL_SCREEN = certified._screen


def run(limit, *args, **kwargs):
    with patch.object(certified, '_screen', partial(screen, limit)):
        return sweep.parity.packaged(True, *args, **kwargs)


def prepare():
    prior, corpus, _ = sweep.prepare()
    reference = sweep.transfer.locked('docs/certified-nomination-gepa-sweep-v1.json', SWEEP_SHA)
    if digest(prior) != reference['planSha256'] or digest(reference['plan']) != reference['planSha256']:
        raise ValueError('The expanded GEPA benchmark must reproduce its sealed plan')
    path = Path(__file__)
    fingerprints = {str(path.relative_to(sweep.transfer.donor.ROOT)): sha256(path.read_bytes()).hexdigest()}
    plan = {
        **{key: value for key, value in prior.items() if not key.startswith('promptolution')},
        'protocol': 'cpo-certified-strict-gain-v1', 'primary': 'strict-gain/cap-14',
        'arms': (sweep.CANDIDATE, *CAPS), 'strictGainCaps': CAPS, 'sweepReceiptSha256': SWEEP_SHA,
        'sourceSha256': {**prior['sourceSha256'], **fingerprints},
        'scope': ('Transfer caps 10, 14 and 18 to the four original math groups. With two challengers and a '
                  'noncritical uniform panel, stop on the first exact strict improvement against the incumbent, '
                  'or retain with no proof within the allowance. Keep the qualification gate and remaining '
                  'schedules fixed. Reproduce every previous comparator and reselect by budget within each draw.'),
    }
    return plan, corpus, reference['math']


def replay(plan, corpus, reference):
    benchmark = sweep.math
    original = benchmark.paired
    arms = plan['arms']
    candidates = {sweep.CANDIDATE: partial(sweep.parity.packaged, True),
                  **{name: partial(run, cap) for name, cap in plan['strictGainCaps'].items()}}

    def compare(config, totals, vectors, peers):
        native = sweep.distinct_controls(config['nativeMethods'], [(totals, vectors)], priced=True)
        peer_menu = (*native, *(arm for arm in peers if arm not in config['nativeMethods']))
        direct, matched = {}, {}
        for name in candidates:
            with patch.multiple(benchmark, STALLED=name, POLICIES=(sweep.CANDIDATE, name)):
                direct[name], matched[name] = original({**config, 'nativeMethods': native}, totals, vectors, peer_menu)
        return direct, matched

    with (patch.multiple(benchmark, POLICIES=arms, paired=compare),
          patch.dict(benchmark.tail.RUNNERS, candidates), patch.object(sweep.archive, 'play', sweep.play)):
        measured = benchmark.replay(plan, corpus)
    for subject, groups in measured.items():
        for group, current in groups.items():
            previous = reference[subject][group]
            if current['layoutSha256'] != previous['layoutSha256'] or current['episodes'] != previous['episodes']:
                raise ValueError('The previous math episode layout must reproduce')
            if any(current['totals'][arm] != stats for arm, stats in previous['totals'].items()):
                raise ValueError('Every prior math cost and holdout count must reproduce')
    return measured


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, corpus, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'math': replay(plan, corpus, reference)}
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
