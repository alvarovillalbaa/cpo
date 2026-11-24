"""Test two ways to order full-depth validation for two challengers."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import language_roster_budget_frontier as frontier
from benchmarks import promptolution_settled_episode_headroom as headroom
from benchmarks import promptolution_settled_episode_quote_depth as nominal
from benchmarks import promptolution_settled_episode_transfer as transfer
from benchmarks import two_challenger_uniform_order as uniform
from cpo import Observation, feedback_episode as feedback, settled_episode as settled
from cpo._contract import digest
from cpo.bounded_uniform_validation import screen as bounded_screen
from cpo.qualification_prefix_cycle import run_qualification_prefix_cycle
from cpo.quoted_shared_validation_cycle import _schedule, _screen as quoted_screen
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run


PARENT_SHA = '3ff606413b874ad251b2fb61c292fa621a1c8b3b8044c515d4550edffc9010f6'
BASE, UNIFORM, HALVING = settled._ACTIONS
METHODS = (transfer.SETTLED, transfer.FEEDBACK)


def screen(fallback, incumbent, candidates, rows, evaluate, cap):
    if len(candidates) != 2 or any(row.critical for row in rows):
        return fallback(incumbent, candidates, rows, evaluate, cap)
    funded = [row for row, _ in _schedule(2, rows, cap, True)]
    if len(funded) < 2:
        return fallback(incumbent, candidates, rows, evaluate, cap)

    paid = 0

    def read(prompt, row):
        nonlocal paid
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Shared validation requires exact boolean replies')
        paid += 1
        return grade

    base = []
    for row in funded:
        base.append(read(incumbent, row))
        if not base[-1]:
            break
    else:
        return FinalistResult(incumbent, None, paid), None

    # The first-round shortlist has one seat. A first-roster pass wins it
    # outright. Only a strict first-case gain lets the second take the seat.
    first = read(candidates[0], funded[0])
    second_wins = not first and read(candidates[1], funded[0])
    winner = candidates[1] if second_wins else candidates[0]
    contender_passes = first or second_wins
    base_passes = sum(base)
    depth = len(funded)
    for seen in range(1, depth + 1):
        if contender_passes + depth - seen <= base_passes:
            return FinalistResult(incumbent, None, paid), None
        if seen == depth:
            break
        grade = read(winner, funded[seen])
        contender_passes += grade
        # Progress the incumbent when another miss tightens the finalist's
        # upper bound. Keep the read order within each prompt unchanged.
        if not grade and len(base) < depth:
            base.append(read(incumbent, funded[len(base)]))
            base_passes += base[-1]

    for row in funded[len(base):]:
        base_passes += read(incumbent, row)
        if contender_passes <= base_passes:
            return FinalistResult(incumbent, None, paid), None
    return FinalistResult(winner, winner, paid), ((base_passes, depth), (contender_passes, depth))


_QUOTED = partial(quoted_screen, halve=True)
_BOUNDED = partial(bounded_screen, halve=True)


def opening_screen(fallback, incumbent, candidates, rows, evaluate, cap):
    if len(candidates) == 2:
        return screen(_QUOTED, incumbent, candidates, rows, evaluate, min(cap, 9))
    return fallback(incumbent, candidates, rows, evaluate, cap)


PAIRED_HALVING = {
    BASE: partial(run_qualification_prefix_cycle, screens=(
        settled._incumbent_first, partial(opening_screen, settled._OPENING_HALVING),
        partial(opening_screen, settled._OPENING_HALVING), partial(opening_screen, settled._OPENING_LIMIT),
    )),
    HALVING: partial(_run, screen=partial(settled._limit, partial(screen, _BOUNDED), 4, 6)),
    feedback._HALVING: partial(_run, screen=partial(settled._limit, partial(screen, _BOUNDED), 8, 14)),
}
VARIANTS = {
    'paired-halving': PAIRED_HALVING,
    'expected-uniform': {UNIFORM: partial(_run, screen=partial(settled._limit, uniform.screen, 8, 18))},
}


def play(original, matrix, windows, seed, method, overrides):
    routes = settled._RUNNERS if method == transfer.SETTLED else feedback._FEEDBACK_RUNNERS
    with patch.dict(routes, {name: runner for name, runner in overrides.items() if name in routes}):
        return transfer.play(original, matrix, windows, seed, method)


def count_depth_effect(matrix, windows, seed, transitions):
    incumbent = transfer.donor.START
    evidence = {}

    def grade(prompt, row):
        return matrix[prompt][int(row.id)] == '1'

    for index, ((roster, _, panel, proof), (schedule, finalist, selected)) in enumerate(
            zip(windows, transitions, strict=True)):
        if schedule != feedback._RETAIN:
            shallow = nominal.RUNNERS[schedule](
                incumbent, roster, transfer.rows(panel), transfer.rows(proof),
                lambda prompt, row: Observation(grade(prompt, row), {}),
                metric_limit=settled._MAX_VALIDATION_READS,
                qualify=lambda prompt, row, repeat: grade(prompt, row), seed=seed + index,
            )
            short_finalist = shallow.search.finalist
            evidence.setdefault(schedule, Counter()).update(
                cycles=1, changedFinalists=int(short_finalist != finalist),
                changedDeployments=int(shallow.prompt != selected),
                fullOnlyFinalists=int(finalist is not None and short_finalist is None),
                fullOnlyDeployments=int(selected != incumbent and shallow.prompt == incumbent),
                nominalOnlyDeployments=int(selected == incumbent and shallow.prompt != incumbent),
            )
        incumbent = selected
    return evidence


def decisions(trace):
    winner, transitions, paid = trace
    return winner, transitions, [item for item in paid if item[0][0] != 'validation']


def prepare():
    prior = transfer.locked('docs/promptolution-settled-episode-quote-depth-v1.json', PARENT_SHA)
    plan, original, parent = nominal.prepare()
    if digest(plan) != prior['planSha256'] or digest(prior['plan']) != prior['planSha256']:
        raise ValueError('The nominal-depth plan must reproduce')
    sources = (Path(__file__).resolve(), Path(uniform.__file__).resolve())
    plan = {**plan, 'protocol': 'cpo-promptolution-settled-episode-read-order-v1',
            'nominalDepthReceiptSha256': PARENT_SHA, 'nominalDepthPlanSha256': prior['planSha256'],
            'sourceSha256': {**plan['sourceSha256'], **{
                str(source.relative_to(transfer.donor.ROOT)): sha256(source.read_bytes()).hexdigest()
                for source in sources}},
            'method': 'Attribute shallow-depth transitions at the original incumbent. Test each read order alone. '
                      'In two-challenger halving, keep the original shortlist and defer remaining incumbent reads '
                      'until the finalist misses or needs exact qualification counts. In two-challenger uniform, '
                      'use independent Beta(1,1) priors to choose the next side, with exact terminal bounds.'}
    return plan, original, parent


def measure(plan, original, parent, archive):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA environment')
    tasks = {}
    pooled = []
    baseline_menus = headroom.capture(original, archive, parent)
    native = (transfer.BASE, *original['nativeMethods'])
    controls = (transfer.BASE, *transfer.WITNESS, *original['controlSettings'])
    variants = {f'{order}/{method}': (method, overrides)
                for method in METHODS for order, overrides in VARIANTS.items()}

    def compare(menus):
        return {variant: {'packaged': frontier.summarize([menu[method] for menu in menus]),
                          'reordered': frontier.summarize([menu[variant] for menu in menus]),
                          'nativeHindsight': headroom.evaluate(menus, variant, native, None),
                          'allControlsHindsight': headroom.evaluate(menus, variant, controls, None)}
                for variant, (method, _) in variants.items()}

    for task, menus in baseline_menus.items():
        panel = archive[task]
        matrix = panel['correctness']
        held = sorted(Random(f"{original['holdoutSeed']}/{task}").sample(
            range(len(panel['caseIDs'])), transfer.donor.HOLDOUT,
        ))
        accounting = {variant: Counter() for variant in variants}
        traces = {variant: [] for variant in variants}
        attribution = {method: {} for method in METHODS}
        for seed, menu in zip(original['seeds'], menus, strict=True):
            windows = transfer.layout(original, task, seed, held)
            reference = {}
            for method in METHODS:
                _, cost, trace = reference[method] = transfer.play(original, matrix, windows, seed, method)
                if cost['paidLookups'] != menu[method].cost:
                    raise ValueError('The original cost must reproduce')
                impact = count_depth_effect(matrix, windows, seed, trace[1])
                for schedule, counts in impact.items():
                    attribution[method].setdefault(schedule, Counter()).update(counts)
            for variant, (method, overrides) in variants.items():
                incumbent, cost, trace = reference[method]
                winner, reordered_cost, reordered_trace = play(original, matrix, windows, seed, method, overrides)
                if winner != incumbent or decisions(trace) != decisions(reordered_trace):
                    raise ValueError('Every transition and qualification reply must reproduce')
                delta = reordered_cost['paidLookups'] - cost['paidLookups']
                accounting[variant].update(savedEpisodes=int(delta < 0), tiedEpisodes=int(delta == 0),
                                           costlierEpisodes=int(delta > 0), grossSavings=max(0, -delta),
                                           grossExtraLookups=max(0, delta))
                traces[variant].append(reordered_trace)
                menu[variant] = frontier.Point(menu[method].passes, reordered_cost['paidLookups'], (variant,))
        tasks[task] = {'episodes': len(menus), 'sameIncumbentDepthEffect': attribution,
                       'readOrderAccounting': accounting, 'traceSha256': {m: digest(t) for m, t in traces.items()},
                       'comparisons': compare(menus)}
        pooled.extend(menus)
    return {'plan': plan, 'planSha256': digest(plan), 'tasks': tasks, 'pooled': compare(pooled), 'providerRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, original, parent = prepare()
    seal = digest(plan)
    if not (args.corpus or args.execute or args.out):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if not args.corpus or args.execute != seal or not args.out or args.out.exists():
        parser.error('Replay requires the pinned corpus, current seal, and a fresh output')
    report = measure(plan, original, parent, transfer.donor.load_corpus(args.corpus.read_bytes()))
    with args.out.open('x') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
