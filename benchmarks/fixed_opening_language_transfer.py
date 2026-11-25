"""Transfer the ARC-selected CPO opening to the seven archived language cohorts."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import feedback_rejection_scout as scout
from benchmarks import settled_episode_api_parity as parity
from benchmarks import settled_episode_refit as refit
from benchmarks import promptolution_settled_episode_transfer as archive
from cpo._contract import digest
from cpo.full_roster_precheck import run_full_roster_feedback_episode
from cpo.full_roster_precheck.fixed_opening import run_fixed_opening_episode


ARC_RECEIPT = 'f0b747ac89f2a1e57fe9c42e81c0e383a4a53f2b4d1e6cbc018bfd932a3f021b'
BASELINE_RECEIPT = '636cc17bbfd8d330557c3b683b6fe0e5bca795744b9f520472e9d095ef4743a7'
OPENING = 'uniform/8/18'
ADAPTIVE, FIXED = 'adaptive-full-roster', 'fixed-uniform'
ARMS = ADAPTIVE, FIXED


def prepare():
    origin = archive.locked('docs/full-roster-fixed-opening-v1.json', ARC_RECEIPT)
    if digest(origin['plan']) != origin['planSha256'] or any(
            item['fixedSetting'] != OPENING
            for width in (4, 8) for item in origin['results']['arc'][f'root/{width}']['directions']):
        raise ValueError('Use the exact opening chosen on both ARC-AGI root rosters and folds')
    reference = archive.locked('docs/full-roster-precheck-verification-v1.json', BASELINE_RECEIPT)
    cohorts = reference['archivedReplay']['language']
    if set(cohorts) != set(refit.discovery.COHORTS):
        raise ValueError('Use all seven archived language cohorts')
    files = (__file__, scout.__file__, refit.__file__, refit.parent.__file__,
             refit.transfer.ROOT / 'cpo/full_roster_precheck/fixed_opening.py',
             refit.transfer.ROOT / 'cpo/full_roster_precheck/__init__.py')
    sources = {str(Path(file).resolve().relative_to(refit.transfer.ROOT)): sha256(Path(file).read_bytes()).hexdigest()
               for file in files}
    plan = {'protocol': 'cpo-fixed-opening-language-transfer-v1', 'sourceSha256': sources,
            'arcReceiptSha256': ARC_RECEIPT, 'arcPlanSha256': origin['planSha256'],
            'baselineReceiptSha256': BASELINE_RECEIPT,
            'languageReceiptSha256': {cohort: parity.LOCKS[cohort.lower()] for cohort in refit.discovery.COHORTS},
            'languageDiscoveryFitSha256': parity.FIT_SHA, 'gepaVersion': origin['plan']['gepaVersion'],
            'opening': OPENING, 'arms': ARMS,
            'scope': ('Transfer the ARC root choice to each frozen language cohort without tuning. '
                      'Keep all seeds, ordered rosters, starting prompts, folds and independent qualification. '
                      'Compare with adaptive full-roster CPO, replayed native GEPA anchors, '
                      'and archived uniform and halving controls at the fixed arm\'s paid lookup count. '
                      'Report cohort-specific paired case ranges and existing native budget bounds.')}
    return plan, cohorts


def play_fixed(incumbent, _training, cycles, evaluate, *, probe, qualify):
    return run_fixed_opening_episode(incumbent, cycles, evaluate, schedule=OPENING, qualify=qualify)


def measure(target, panels, gepa, simple, reference):
    totals, traces = {arm: Counter() for arm in ARMS}, {arm: sha256() for arm in ARMS}
    costs_by_opening, vectors = {}, {}
    add = refit.native.paired.frontier.transfer.fitted.prior.add_vector
    effects = refit.native.frozen.paired_effects.paired_effect
    for subject, model, seed, cells, stages, start in refit.previous.episodes(target, panels):
        paths = {}
        for arm, runner in ((ADAPTIVE, run_full_roster_feedback_episode), (FIXED, play_fixed)):
            with patch.object(scout.feedback, 'run_feedback_episode', runner):
                result, paid = scout.language_episode(cells, stages, start)
            if arm == FIXED and (result.training_evaluations or any(row[0] == 'training' for row in paid)):
                raise ValueError('A fixed opening must not buy any training replies')
            paths[arm] = result, len(paid)
            grades = [cells[result.prompt][case] for case in stages[0][2][-1]]
            scores = vectors.setdefault(subject, {})
            add(scores.setdefault(arm, [0] * len(grades)), grades)
            totals[arm].update(holdoutPasses=sum(grades), paidLookups=len(paid),
                               overriddenCycles=sum(action != result.schedule for action in result.cycle_schedules))
            totals[arm].update(f'{role}Lookups' for role, *_ in paid)
            traces[arm].update(bytes.fromhex(digest((subject, model, seed, result.prompt, result.cycle_schedules, paid))))
        baseline, before = paths[ADAPTIVE]
        fixed, after = paths[FIXED]
        stratum = costs_by_opening.setdefault(baseline.schedule, Counter())
        stratum.update(episodes=1, changedFinalPrompts=int(fixed.prompt != baseline.prompt),
                       paidLookupDelta=after - before)
        if baseline.schedule == OPENING and (baseline.cycles != fixed.cycles or
                                            baseline.cycle_schedules != fixed.cycle_schedules or
                                            before - after != baseline.training_evaluations):
            raise ValueError('Matching openings must agree aside from the paid training prefix')

    hashes = {arm: trace.hexdigest() for arm, trace in traces.items()}
    episodes = sum(point['episodes'] for point in costs_by_opening.values())
    if (episodes != reference['episodes'] or totals[ADAPTIVE] != reference['totals']
            or hashes[ADAPTIVE] != reference['paidTraceSha256']):
        raise ValueError('The published adaptive control must reproduce exactly')
    budget = totals[FIXED]['paidLookups']
    bounds, native_controls = refit.parent.compare_native(
        target, panels, gepa, budget, simple['settingsTotals'][refit.RETAIN]['holdoutPasses'], vectors)
    simple_controls = refit.parent.compare_simple(target, panels, simple, budget, vectors)
    return {'episodes': episodes, 'totals': totals, 'paidTraceSha256': hashes,
            'byAdaptiveOpening': costs_by_opening, 'nativeBoundsAtFixedCost': bounds,
            'replayedNativeAnchors': native_controls, 'simpleAtFixedCost': simple_controls,
            'paired': {control: effects(vectors, FIXED, control, target)
                       for control in (ADAPTIVE, *native_controls, *simple_controls)}}


def replay(plan, references):
    base, context, baseline = refit.contract()
    fitted = archive.locked('docs/settled-episode-refit-v1.json', parity.FIT_SHA)
    results = {}
    for cohort, lock in plan['languageReceiptSha256'].items():
        target, (panels, _, _, gepa, simple, _) = refit.target(cohort, base, context, baseline, fitted)
        old = archive.locked(f'docs/settled-episode-refit-transfer-{cohort.lower()}-v1.json', lock)
        if digest(target) != digest(old['plan']) or digest(target) != old['planSha256']:
            raise ValueError('Use the frozen language cohort layout')
        results[cohort] = measure(target, panels, gepa, simple, references[cohort])
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'cohorts': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, references = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    result = replay(plan, references)
    with args.out.open('x') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
