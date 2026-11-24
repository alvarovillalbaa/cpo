"""Scout a fresh roster on cycles that packaged feedback would skip."""

import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import replace
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import language_roster_budget_frontier as frontier
from benchmarks import paid_prefix_archive_routing as routing
from benchmarks import promptolution_settled_episode_headroom as headroom
from benchmarks import promptolution_settled_episode_transfer as transfer
from benchmarks import promptolution_two_round_halving as two_round
from benchmarks import settled_episode_api_parity as parity
from benchmarks import settled_episode_refit as refit
from cpo import Observation, Row, feedback_episode as feedback, settled_episode as settled
from cpo._contract import digest
from cpo.bounded_uniform_validation import screen as uniform
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run


PACKAGED, SCOUT = transfer.FEEDBACK, 'rejection-scout'
TWO_ROUND, TWO_ROUND_SCOUT = 'two-round-feedback', 'two-round-rejection-scout'
FIRST_MISS, TWO_ROUND_FIRST_MISS = 'first-miss-scout', 'two-round-first-miss-scout'
API_SHA = 'a690b791eedeb3db94ca718fbd20a968d542b4dfef14e383d73301590c5e29e4'
TWO_ROUND_SHA = 'fcc852d0a9824325199c8f706ad13bfbd78e9c5b4f32fc477d12411d325fe8e9'
REFERENCES = {SCOUT: PACKAGED, TWO_ROUND_SCOUT: TWO_ROUND,
              FIRST_MISS: PACKAGED, TWO_ROUND_FIRST_MISS: TWO_ROUND}
SCOUT_DEPTHS = {SCOUT: 1, FIRST_MISS: 2}


def scout_cycle(incumbent, candidates, validation, qualification, evaluate, *, metric_limit, qualify, seed, depth=1):
    if any(row.critical for row in validation):
        return FixedPoolCycleResult(FinalistResult(incumbent, None, 0), None)

    def screen(base, roster, panel, read, cap):
        funded = roster[:4]
        opening = panel[:min(depth, max(0, cap - len(funded)))]
        for skipped, row in enumerate(opening):
            reply = read(base, row)
            if type(reply.passed) is not bool:
                raise ValueError('Validation requires exact boolean replies')
            if reply.passed:
                continue

            def reuse(prompt, case):
                return reply if prompt == base else read(prompt, case)

            result, counts = uniform(base, funded, (row,), reuse, cap - skipped, halve=False)
            return replace(result, evaluations=result.evaluations + skipped), counts
        return FinalistResult(base, None, len(opening)), None

    return _run(incumbent, candidates, validation, qualification, evaluate, metric_limit=metric_limit,
                qualify=qualify, seed=seed, screen=screen)


@contextmanager
def use_scout(overrides=None, *, scout=SCOUT):
    runner = partial(scout_cycle, depth=SCOUT_DEPTHS[scout])
    with patch.dict(feedback._FOLLOW_UP, {settled._ACTIONS[2]: scout}), patch.dict(
            feedback._FEEDBACK_RUNNERS, {scout: runner, **(overrides or {})}):
        yield


def prepare():
    api = transfer.locked('docs/settled-episode-feedback-api-parity-v1.json', API_SHA)
    previous = transfer.locked('docs/promptolution-two-round-halving-v1.json', TWO_ROUND_SHA)
    previous_plan, original, reference = two_round.prepare()
    if digest(previous_plan) != previous['planSha256'] or digest(previous['plan']) != previous['planSha256']:
        raise ValueError('Reproduce the two-round plan before measuring the scout')
    plan = {'protocol': 'cpo-feedback-rejection-scout-v1', 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'feedbackAPIReceiptSha256': API_SHA, 'languageTransferReceiptSha256': parity.LOCKS,
            'twoRoundReceiptSha256': TWO_ROUND_SHA, 'twoRoundPlanSha256': previous['planSha256'],
            'promptolutionCorpusSha256': original['corpusSha256'], 'gepaVersion': original['gepaVersion'],
            'scoutIncumbentRows': SCOUT_DEPTHS, 'scoutChallengers': 4, 'maxScoutValidationLookups': 6,
            'method': 'Replace the retain action after a rejected finalist in the two-pass opening state with '
                      'one shared validation case for at most four challengers. Scout the first case, or look '
                      'for the first incumbent miss within two cases. Keep independent qualification '
                      'and let its observed outcome drive the same follow-up rule. Retain critical panels. '
                      'Test with the original and two-round halving on Promptolution, and with the original '
                      'halving on the seven frozen language cohorts.'}
    return plan, api, previous, original, reference


def prompt_replay(original, reference, previous, archive):
    baseline = headroom.capture(original, archive, reference)
    tasks, observations, pooled = {}, [], []
    controls = (transfer.BASE, *transfer.WITNESS, *original['controlSettings'])
    native = (transfer.BASE, *original['nativeMethods'])

    def compare(data, menus):
        return {name: {'paired': transfer.compare(original, data, name, (peer,), enforce_cap=False),
                       'nativeHindsight': headroom.evaluate(menus, name, native, None),
                       'allControlsHindsight': headroom.evaluate(menus, name, controls, None)}
                for name, peer in REFERENCES.items()}

    for task, menus in baseline.items():
        panel = archive[task]
        matrix = panel['correctness']
        held = sorted(Random(f"{original['holdoutSeed']}/{task}").sample(
            range(len(panel['caseIDs'])), transfer.donor.HOLDOUT,
        ))
        methods = (PACKAGED, TWO_ROUND, *REFERENCES)
        totals = {name: Counter() for name in methods}
        vectors = {name: [0] * len(held) for name in methods}
        divergence = {}
        traces = {name: [] for name in methods}
        for seed, menu in zip(original['seeds'], menus, strict=True):
            windows = transfer.layout(original, task, seed, held)
            play = transfer.play
            archived = {PACKAGED: play(original, matrix, windows, seed, PACKAGED),
                        TWO_ROUND: two_round.prior.play(original, matrix, windows, seed, PACKAGED, two_round.OVERRIDES)}
            for name, scout in ((SCOUT, SCOUT), (TWO_ROUND_SCOUT, SCOUT),
                                (FIRST_MISS, FIRST_MISS), (TWO_ROUND_FIRST_MISS, FIRST_MISS)):
                overrides = two_round.OVERRIDES if REFERENCES[name] == TWO_ROUND else None
                with use_scout(overrides, scout=scout):
                    archived[name] = play(original, matrix, windows, seed, PACKAGED)
            for name, (winner, costs, trace) in archived.items():
                grades = [matrix[winner][case] == '1' for case in held]
                totals[name].update(costs, holdoutPasses=sum(grades))
                totals[name]['scoutCycles'] += sum(schedule in SCOUT_DEPTHS for schedule, _, _ in trace[1])
                vectors[name] = [a + b for a, b in zip(vectors[name], grades, strict=True)]
                traces[name].append(trace)
                point = frontier.Point(sum(grades), costs['paidLookups'], (name,))
                if name in menu and menu[name] != point:
                    raise ValueError('Packaged feedback must reproduce every reference result')
                menu[name] = point
            if task == 'gsm8k' and seed == 47139:
                divergence = {name: {'transitions': trace[1], 'holdoutPasses': menu[name].passes,
                                     'paidLookups': menu[name].cost}
                              for name, (_, _, trace) in archived.items()}
        if digest(traces[TWO_ROUND]) != previous['tasks'][task]['traceSha256'][TWO_ROUND]:
            raise ValueError('Two-round feedback must reproduce its paid trace exactly')
        tasks[task] = {'episodes': len(menus), 'totals': totals, 'comparisons': compare([(totals, vectors)], menus),
                       'traceSha256': {name: digest(tape) for name, tape in traces.items()}, 'episode47139': divergence}
        observations.append((totals, vectors))
        pooled.extend(menus)
    return {'tasks': tasks, 'pooled': compare(observations, pooled)}


def language_episode(cells, stages, start):
    paid = []

    def grade(prompt, row):
        passed = bool(cells[prompt][int(row.id)])
        paid.append((row.family, prompt, row.id, passed))
        return passed

    def qualify(prompt, row, repeat):
        if repeat != 0:
            raise ValueError('Archived admission supplies one grade per case')
        return grade(prompt, row)

    training = tuple(Row(str(case), 'training') for case in stages[0][2][0][:2])
    cycles = tuple(settled.EpisodeCycle(tuple(roster), tuple(Row(str(case), 'validation') for case in roles[1]),
                                       tuple(Row(str(case), 'qualification') for case in roles[2]), seed)
                   for seed, roster, roles in stages)
    result = feedback.run_feedback_episode(start, training, cycles, lambda p, row: Observation(grade(p, row), {}),
                                           probe=grade, qualify=qualify)
    if len(paid) != result.evaluations or len({reply[:3] for reply in paid}) != len(paid):
        raise ValueError('Every paid callback must be counted once')
    incumbent = start
    for (_, _, roles), cycle in zip(stages, result.cycles, strict=True):
        routing.verify_qualification(cells, incumbent, roles, cycle, None, 1)
        incumbent = cycle.prompt
    return result, paid


def language_cohort(plan, panels, gepa, simple, reference):
    totals = {name: Counter() for name in (PACKAGED, *SCOUT_DEPTHS)}
    schedules = {name: Counter() for name in totals}
    hashes = {name: sha256() for name in totals}
    add = refit.native.paired.frontier.transfer.fitted.prior.add_vector
    effects = refit.native.frozen.paired_effects.paired_effect
    vectors, episodes = {}, 0
    for subject, model, seed, cells, stages, start in refit.previous.episodes(plan, panels):
        observed = {PACKAGED: language_episode(cells, stages, start)}
        for name in SCOUT_DEPTHS:
            with use_scout(scout=name):
                observed[name] = language_episode(cells, stages, start)
        for name, (episode, paid) in observed.items():
            grades = [cells[episode.prompt][case] for case in stages[0][2][-1]]
            add(vectors.setdefault(subject, {}).setdefault(name, [0] * len(grades)), grades)
            totals[name].update(holdoutPasses=sum(grades), paidLookups=len(paid),
                                trainingLookups=episode.training_evaluations,
                                overriddenCycles=sum(action != episode.schedule for action in episode.cycle_schedules))
            schedules[name].update(episode.cycle_schedules)
            hashes[name].update(bytes.fromhex(digest((subject, model, seed, episode.prompt, episode.cycle_schedules, paid))))
        episodes += 1
    traces = {name: item.hexdigest() for name, item in hashes.items()}
    if (episodes != reference['episodes'] or totals[PACKAGED] != reference['totals']
            or schedules[PACKAGED] != reference['cycleSchedules'] or traces[PACKAGED] != reference['paidTraceSha256']):
        raise ValueError('Reproduce the exact packaged feedback archive before comparing the scout')
    comparisons = {}
    for name in SCOUT_DEPTHS:
        peers = {subject: dict(scores) for subject, scores in vectors.items()}
        bounds, anchors = refit.parent.compare_native(
            plan, panels, gepa, totals[name]['paidLookups'], simple['settingsTotals'][refit.RETAIN]['holdoutPasses'], peers,
        )
        comparisons[name] = {'nativeBoundsAtCost': bounds, 'nativeAnchors': anchors,
                             'paired': {peer: effects(peers, name, peer, plan) for peer in (PACKAGED, *anchors)}}
    return {'episodes': episodes, 'totals': totals, 'schedules': schedules, 'traceSha256': traces,
            'comparisons': comparisons}


def language_replay(api):
    plan, context, baseline = refit.contract()
    frozen = json.loads(refit.transfer.read_locked('docs/settled-episode-refit-v1.json', parity.FIT_SHA))
    results = {}
    for cohort in refit.discovery.COHORTS:
        target, (panels, _, _, gepa, simple, _) = refit.target(cohort, plan, context, baseline, frozen)
        key = cohort.lower()
        archived = transfer.locked(f'docs/settled-episode-refit-transfer-{key}-v1.json', parity.LOCKS[key])
        if digest(target) != archived['planSha256'] or digest(archived['plan']) != archived['planSha256']:
            raise ValueError('Use the original language cohort layout')
        results[cohort] = language_cohort(target, panels, gepa, simple, api['cohorts'][cohort])
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, api, previous, original, reference = prepare()
    seal = digest(plan)
    if not (args.corpus or args.execute or args.out):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if not args.corpus or args.execute != seal or not args.out or args.out.exists():
        parser.error('Replay requires the pinned corpus, current seal, and a fresh output')
    if version('gepa') != plan['gepaVersion']:
        parser.error('Use the pinned GEPA environment')
    archive = transfer.donor.load_corpus(args.corpus.read_bytes())
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
              'promptolution': prompt_replay(original, reference, previous, archive),
              'language': language_replay(api)}
    with args.out.open('x') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
