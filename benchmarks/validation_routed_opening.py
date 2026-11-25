"""Route a CPO opening from incumbent validation replies and reuse their grades."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import fixed_opening_language_transfer as language
from benchmarks import full_roster_fixed_opening as math
from cpo._contract import digest
from cpo.full_roster_precheck.fixed_opening import run_fixed_opening_episode
from cpo.settled_episode import _MAX_VALIDATION_READS
from cpo.settled_episode_schedule import choose_schedule


LANGUAGE_RECEIPT = '6e76fd057e8f5db14c695fd521f41943cedd85fada7e4e85c9e43e802dd6a02c'
ROUTED = 'validation-routed-opening'
HALVING = 'successive-halving/4/6'
ACTIONS = (language.OPENING, language.OPENING, HALVING)


def play(incumbent, _training, cycles, evaluate, *, probe, qualify):
    """Replay on the benchmark's already-validated episode layout."""
    cycles = tuple(cycles)
    first = cycles[0]
    if len(first.validation) < 2 or not first.candidates or any(row.critical for row in first.validation):
        raise ValueError('This experiment requires two noncritical opening validation cases and a roster')
    prefix, reused = {}, set()
    first_ids = {row.id for row in first.validation}
    first_reads = 0

    def fetch(prompt, row):
        nonlocal first_reads
        if row.id in first_ids:
            if first_reads == _MAX_VALIDATION_READS:
                raise ValueError('The routing prefix and selected screen exhausted the first-cycle search cap')
            first_reads += 1
        return evaluate(prompt, row)

    def opening_grade(prompt, row):
        reply = fetch(prompt, row)
        prefix[row.id] = reply
        return reply.passed

    def read(prompt, row):
        if prompt == incumbent and row.id in prefix:
            reused.add(row.id)
            return prefix[row.id]
        return fetch(prompt, row)

    opening = choose_schedule(incumbent, first.validation[:2], opening_grade, actions=ACTIONS)
    result = run_fixed_opening_episode(incumbent, cycles, read, schedule=opening, qualify=qualify)
    # A pre-read outside the selected screen's funded cases remains payable.
    outcome = result.cycles[0]
    reads = outcome.search.evaluations + len(prefix.keys() - reused)
    if reads != first_reads:
        raise ValueError('Every routed first-cycle validation reply must reconcile')
    first_result = replace(outcome, search=replace(outcome.search, evaluations=reads))
    return replace(result, cycles=(first_result, *result.cycles[1:]))


def prepare():
    language_plan, _ = language.prepare()
    math_plan, data = math.prepare()
    locked = language.archive.locked
    prior = locked('docs/fixed-opening-language-transfer-v1.json', LANGUAGE_RECEIPT)
    reference = locked('docs/full-roster-fixed-opening-v1.json', language.ARC_RECEIPT)
    if (digest(language_plan) != digest(prior['plan']) or digest(language_plan) != prior['planSha256']
            or digest(math_plan) != digest(reference['plan']) or digest(math_plan) != reference['planSha256']):
        raise ValueError('Both prior fixed-opening studies must reproduce')
    plan = {'protocol': 'cpo-validation-routed-opening-v1', 'gepaVersion': math_plan['gepaVersion'],
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'languageReceiptSha256': LANGUAGE_RECEIPT, 'mathReceiptSha256': language.ARC_RECEIPT,
            'languagePlanSha256': prior['planSha256'], 'mathPlanSha256': reference['planSha256'],
            'actionsByIncumbentPasses': ACTIONS, 'firstCycleValidationCap': _MAX_VALIDATION_READS,
            'scope': ('Use up to two incumbent validation replies to select the episode opening. '
                      'Choose uniform as soon as a miss is observed, or halving after two passes. '
                      'Reuse the exact validation replies and charge every physical read. '
                      'Use the original disjoint qualification and unchanged follow-up behavior. '
                      'Measure on all original language episodes and both audit folds of each math layout, '
                      'with no routing calibration. Compare the locked CPO baselines, affordable controls '
                      'at the routed language cost, and the previously calibrated native math controls.')}
    return plan, language_plan, prior, math_plan, reference, data


def tally(total, trace, result, paid, grades, identity):
    if result.training_evaluations or any(role == 'training' for role, *_ in paid):
        raise ValueError('The route must not buy a training reply')
    total.update(holdoutPasses=sum(grades), paidLookups=len(paid),
                 overriddenCycles=sum(action != result.schedule for action in result.cycle_schedules))
    total.update(f'{role}Lookups' for role, *_ in paid)
    trace.update(bytes.fromhex(digest((*identity, result.prompt, result.cycle_schedules, paid))))


def measure_language(plan, previous):
    refit = language.refit
    base, context, baseline = refit.contract()
    fitted = language.archive.locked('docs/settled-episode-refit-v1.json', language.parity.FIT_SHA)
    add = refit.native.paired.frontier.transfer.fitted.prior.add_vector
    effects = refit.native.frozen.paired_effects.paired_effect
    outcomes = {}
    for cohort, lock in plan['languageReceiptSha256'].items():
        target, (panels, _, _, gepa, simple, _) = refit.target(cohort, base, context, baseline, fitted)
        sealed = language.archive.locked(f'docs/settled-episode-refit-transfer-{cohort.lower()}-v1.json', lock)
        if digest(target) != digest(sealed['plan']) or digest(target) != sealed['planSha256']:
            raise ValueError('Use the sealed language layouts')
        expected = previous['cohorts'][cohort]
        trace = {name: sha256() for name in (language.ADAPTIVE, language.FIXED, ROUTED)}
        totals = {name: Counter() for name in trace}
        opening, vectors = Counter(), {}
        for subject, model, seed, cells, stages, start in refit.previous.episodes(target, panels):
            for arm, runner in ((language.ADAPTIVE, language.run_full_roster_feedback_episode),
                                (language.FIXED, language.play_fixed), (ROUTED, play)):
                with patch.object(language.scout.feedback, 'run_feedback_episode', runner):
                    result, paid = language.scout.language_episode(cells, stages, start)
                grades = [cells[result.prompt][case] for case in stages[0][2][-1]]
                by_subject = vectors.setdefault(subject, {})
                add(by_subject.setdefault(arm, [0] * len(grades)), grades)
                if arm == ROUTED:
                    tally(totals[arm], trace[arm], result, paid, grades, (subject, model, seed))
                    opening[result.schedule] += 1
                else:
                    trace[arm].update(bytes.fromhex(digest(
                        (subject, model, seed, result.prompt, result.cycle_schedules, paid))))
        hashes = {arm: trace[arm].hexdigest() for arm in trace}
        if (sum(opening.values()) != expected['episodes'] or any(
                hashes[arm] != expected['paidTraceSha256'][arm] for arm in language.ARMS)):
            raise ValueError('The adaptive and fixed baseline trajectories must reproduce')
        totals.update(expected['totals'])
        budget = totals[ROUTED]['paidLookups']
        bounds, controls = refit.parent.compare_native(
            target, panels, gepa, budget, simple['settingsTotals'][refit.RETAIN]['holdoutPasses'], vectors)
        simple_controls = refit.parent.compare_simple(target, panels, simple, budget, vectors)
        outcomes[cohort] = {'episodes': expected['episodes'], 'openings': opening, 'totals': totals,
                            'paidTraceSha256': hashes, 'nativeBoundsAtBudget': bounds, 'nativeAnchors': controls,
                            'simpleAtBudget': simple_controls,
                            'paired': {peer: effects(vectors, ROUTED, peer, target)
                                       for peer in (*language.ARMS, *controls, *simple_controls)}}
    return outcomes


def measure_math(plan, reference, data):
    transfer = math.transfer
    effects = math.NATIVE.native.frozen.paired_effects.paired_effect
    outcomes = {}
    for subject, layout in plan['datasets'].items():
        cells = transfer.math.load_cells(subject, data[subject]['record'])
        outcomes[subject] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                key = f'{group}/{width}'
                expected = reference['results'][subject][key]
                vectors, totals, opening, trace = {}, Counter(), Counter(), sha256()
                for direction in expected['directions']:
                    fold = direction['auditFold']
                    subset, trials, _ = math.crossfit.get_fold(cells, layout, fold, group, width)
                    if len(trials) != direction['trials']:
                        raise ValueError('Use the original math audit layout')
                    labels = tuple(dict.fromkeys((math.ADAPTIVE, direction['fixedSetting'])))
                    points, grades = math.cpo_points(plan, subset, trials, labels)
                    peer = direction['audit']
                    calibrated_gepa, native = math.gepa_point(plan, subset, trials, direction['calibrationGepa']['setting'])
                    if (points[math.ADAPTIVE] != peer[math.ADAPTIVE]
                            or points[direction['fixedSetting']] != peer[math.FIXED] or calibrated_gepa != peer[math.GEPA]):
                        raise ValueError('Every locked math comparison must reproduce')
                    routed = [0] * len(next(iter(subset.values())))
                    for trial in trials:
                        result, _, held, paid = transfer.episode(play, subset, trial)
                        tally(totals, trace, result, paid, held, (fold, trial[0], trial[-1]))
                        opening[result.schedule] += 1
                        math.NATIVE.accumulate(routed, trial[2][-1], held)
                    vectors[f'fold-{fold}'] = {ROUTED: routed, math.ADAPTIVE: grades[math.ADAPTIVE],
                                              math.FIXED: grades[direction['fixedSetting']], math.GEPA: native}
                outcomes[subject][key] = {'episodes': sum(opening.values()), 'openings': opening,
                                          'totals': {**expected['auditTotals'], ROUTED: totals},
                                          'paidTraceSha256': trace.hexdigest(),
                                          'paired': {peer: effects(vectors, ROUTED, peer, plan)
                                                     for peer in (math.ADAPTIVE, math.FIXED, math.GEPA)}}
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, language_plan, prior, math_plan, reference, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    result = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
              'language': measure_language(language_plan, prior), 'math': measure_math(math_plan, reference, data)}
    with args.out.open('x') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
