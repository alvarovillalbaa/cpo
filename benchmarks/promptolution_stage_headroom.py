"""Price the incumbent-veto, nomination, and qualification headroom in CPO."""

import argparse
from functools import cache
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import language_roster_budget_frontier as frontier
from benchmarks import promptolution_settled_episode_headroom as headroom
from benchmarks import promptolution_settled_episode_transfer as transfer
from cpo import Observation, feedback_episode as feedback, settled_episode as settled
from cpo._contract import digest
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.paired_qualification import certify_paired_qualification
from cpo.settled_episode_schedule import choose_schedule
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _screen


SCOUT_SHA = '384596a6dc3a077e333fbc6ba96a2a7d3782b8d1948c1b6546607d22e40afb1e'
VETO, NOMINATION, QUALIFICATION = 'veto-promotions', 'choose-nominee', 'qualification-upper-bound'
TIERS = (VETO, NOMINATION, QUALIFICATION)


def edges(incumbent, packaged, alternatives, tier):
    """Pay for the observed proof even if hindsight overrides its decision."""
    for name, result in (('packaged', packaged), *alternatives):
        nominee = result.search.finalist or ''
        rejected = bool(nominee and result.qualification.status == 'rejected')
        spent = result.search.evaluations + result.qualification_evaluations
        if name == 'packaged' or result.promoted:
            yield (result.prompt, rejected), spent, (name, nominee, result.prompt, rejected, spent)
        if name == 'packaged' and result.promoted:
            yield (incumbent, False), spent, ('veto', nominee, incumbent, False, spent)
        if tier == QUALIFICATION and rejected:
            yield (nominee, True), spent, ('allow-rejected', nominee, nominee, True, spent)


def reachable(start, cycles, step, tier, training_cost, score):
    states = {(start, False): (training_cost, ())}
    for index in range(cycles):
        following = {}
        for state, (paid, path) in states.items():
            for outcome, cost, action in step(index, *state, tier):
                arrival = paid + cost, (*path, action)
                if outcome not in following or arrival < following[outcome]:
                    following[outcome] = arrival
        states = following
    return frontier.efficient(frontier.Point(score(prompt), cost, path)
                              for (prompt, _), (cost, path) in states.items())


def episode(matrix, windows, seed, arm, held):
    start = transfer.donor.START

    def grade(prompt, case):
        return matrix[prompt][case] == '1'

    def evaluate(prompt, row):
        return Observation(grade(prompt, int(row.id)), {})

    def qualify(prompt, row, repeat):
        if repeat != 0:
            raise ValueError('Archive qualification includes one reply per prompt and case')
        return grade(prompt, int(row.id))

    training = tuple(windows[0][1][:2])
    opening = choose_schedule(start, training, grade, actions=settled._ACTIONS)
    adapt = arm == transfer.FEEDBACK
    inputs = [(roster, transfer.rows(panel), transfer.rows(proof)) for roster, _, panel, proof in windows]

    @cache
    def packaged(index, incumbent, rejected):
        schedule = feedback._FOLLOW_UP[opening] if adapt and rejected else opening
        if schedule == feedback._RETAIN:
            return schedule, FixedPoolCycleResult(FinalistResult(incumbent, None, 0), None)
        roster, panel, proof = inputs[index]
        result = feedback._FEEDBACK_RUNNERS[schedule](
            incumbent, roster, panel, proof, evaluate, metric_limit=settled._MAX_VALIDATION_READS,
            qualify=qualify, seed=seed + index,
        )
        return schedule, result

    @cache
    def roster_options(index, incumbent):
        roster, panel, proof = inputs[index]
        candidates = []
        for prompt in roster:
            search, _ = _screen(incumbent, (prompt,), panel, evaluate,
                                settled._MAX_VALIDATION_READS, expected=True)
            if search.finalist is not None:
                decision = certify_paired_qualification(incumbent, prompt, proof, qualify, seed=seed + index)
                candidates.append(('known-nominee', FixedPoolCycleResult(search, decision)))
        return tuple(candidates)

    def step(index, incumbent, rejected, tier):
        schedule, result = packaged(index, incumbent, rejected)
        alternatives = roster_options(index, incumbent) if tier != VETO and schedule != feedback._RETAIN else ()
        return edges(incumbent, result, alternatives, tier)

    def score(prompt):
        return sum(grade(prompt, case) for case in held)

    # Reconstruct the exact packaged path, including the state that drives feedback.
    incumbent, rejected = start, False
    paid, decisions = len(training), []
    for index in range(len(windows)):
        schedule, result = packaged(index, incumbent, rejected)
        (incumbent, rejected), cost, _ = next(edges(incumbent, result, (), VETO))
        paid += cost
        decisions.append((schedule, result.search.finalist, incumbent))
    baseline = incumbent, tuple(decisions), paid
    menus = {tier: reachable(start, len(windows), step, tier, len(training), score) for tier in TIERS}
    return baseline, menus


def prepare():
    scout = transfer.locked('docs/feedback-rejection-scout-v1.json', SCOUT_SHA)
    if digest(scout['plan']) != scout['planSha256']:
        raise ValueError('Use the sealed scout replay')
    parent, original, reference = headroom.prepare()
    source = Path(__file__).resolve()
    plan = {**parent, 'protocol': 'cpo-promptolution-stage-headroom-v1', 'scoutReceiptSha256': SCOUT_SHA,
            'sourceSha256': {**parent['sourceSha256'], str(source.relative_to(transfer.donor.ROOT)):
                             sha256(source.read_bytes()).hexdigest()},
            'method': 'Price the original screen and qualification on every reached state. Add paid retention '
                      'after a successful proof, then a known roster nominee with a paid full-panel validation '
                      'certificate and independent qualification. Finally allow paid but rejected finalists '
                      'as a separate retrospective bound. Keep the original feedback outcome and skip routing '
                      'on each chosen edge. Choose routes with final holdout in hindsight at the published '
                      'per-episode or pooled budget. Price the cheapest path matching the broad control ceiling. '
                      'These choices are not deployable policies.'}
    return plan, original, reference


def summarize(menus, baselines):
    actual = frontier.summarize(baselines)
    last = (actual['holdoutPasses'], actual['holdoutPasses'])
    results = {}
    for tier, options in menus.items():
        local = [max((point for point in menu if point.cost <= baseline.cost),
                     key=lambda p: (p.passes, -p.cost)) for menu, baseline in zip(options, baselines, strict=True)]
        pooled = frontier.pool(options, actual['paidLookups'])
        local_point, pooled_point = frontier.summarize(local), frontier.summarize(pooled)
        scores = (local_point['holdoutPasses'], pooled_point['holdoutPasses'])
        if scores[0] < last[0] or scores[1] < last[1] or scores[1] < scores[0]:
            raise ValueError('Expanding the decision menu or the budget scope cannot reduce headroom')
        results[tier] = {'perEpisodeCaps': local_point, 'pooledCap': pooled_point,
                         'pooledAttainingPathsSha256': digest([point.actions for point in pooled]),
                         'pooledActions': sorted((action, sum(step[0] == action for point in pooled for step in point.actions))
                                                 for action in ('packaged', 'veto', 'known-nominee', 'allow-rejected'))}
        last = scores
    return {'packaged': actual, 'bounds': results}


def price_match(menus, target):
    curve = headroom.cost_frontier(menus)
    price = min((cost for passes, cost in curve.items() if passes >= target), default=None)
    if price is None:
        return None
    selected = frontier.pool(menus, price)
    point = frontier.summarize(selected)
    if point['holdoutPasses'] < target or point['paidLookups'] != price:
        raise ValueError('The minimum budget needs an attaining trajectory')
    return {'targetPasses': target, **point, 'attainingPathsSha256': digest([item.actions for item in selected])}


def measure(plan, original, reference, archive):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA environment')
    baseline = headroom.capture(original, archive, reference)
    tasks, pooled = {}, {arm: {tier: [] for tier in TIERS} for arm in transfer.RUNNERS}
    points = {arm: [] for arm in transfer.RUNNERS}
    for task in original['tasks']:
        panel = archive[task]
        matrix = panel['correctness']
        held = sorted(Random(f"{original['holdoutSeed']}/{task}").sample(
            range(len(panel['caseIDs'])), transfer.donor.HOLDOUT,
        ))
        task_points = {arm: [] for arm in transfer.RUNNERS}
        task_menus = {arm: {tier: [] for tier in TIERS} for arm in transfer.RUNNERS}
        for seed, menu in zip(original['seeds'], baseline[task], strict=True):
            windows = transfer.layout(original, task, seed, held)
            for arm in transfer.RUNNERS:
                winner, cost, trace = transfer.play(original, matrix, windows, seed, arm)
                verified, options = episode(matrix, windows, seed, arm, held)
                if verified != (winner, tuple(trace[1]), cost['paidLookups']) or verified[2] != menu[arm].cost:
                    raise ValueError('Every packaged deployment, feedback transition, and charge must reproduce')
                task_points[arm].append(menu[arm])
                for tier, candidates in options.items():
                    task_menus[arm][tier].append(candidates)
        tasks[task] = {arm: summarize(task_menus[arm], task_points[arm]) for arm in transfer.RUNNERS}
        for arm in transfer.RUNNERS:
            points[arm].extend(task_points[arm])
            for tier in TIERS:
                pooled[arm][tier].extend(task_menus[arm][tier])
    controls = (transfer.BASE, *transfer.WITNESS, *original['controlSettings'])
    native = (transfer.BASE, *original['nativeMethods'])
    original_menus = [menu for task in original['tasks'] for menu in baseline[task]]
    ceilings = {arm: {'nativeGEPA': headroom.evaluate(original_menus, arm, native, None),
                      'allControls': headroom.evaluate(original_menus, arm, controls, None)}
                for arm in transfer.RUNNERS}
    prices = {arm: {tier: price_match(options, ceilings[arm]['allControls']['hindsightAtBudget']['holdoutPasses'])
                    for tier, options in tiers.items()} for arm, tiers in pooled.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'episodes': len(original_menus), 'providerRequests': 0,
            'tasks': tasks, 'pooled': {arm: summarize(pooled[arm], points[arm]) for arm in transfer.RUNNERS},
            'controlsAtPackagedBudget': ceilings, 'priceToMatchBroaderHindsight': prices}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, original, reference = prepare()
    seal = digest(plan)
    if not (args.corpus or args.execute or args.out):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if not args.corpus or args.execute != seal or not args.out or args.out.exists():
        parser.error('Replay requires the pinned corpus, current seal, and a fresh output')
    report = measure(plan, original, reference, transfer.donor.load_corpus(args.corpus.read_bytes()))
    with args.out.open('x') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
