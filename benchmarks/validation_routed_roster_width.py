"""Test the two-challenger transfer of settled and validation-routed CPO."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import continuous_archive_routing as layouts
from benchmarks import fixed_opening_language_transfer as language
from benchmarks import promptolution_settled_episode_transfer as controls
from benchmarks import validation_routed_promptolution as promptolution
from benchmarks import witness_validation_cost_frontier as frontier
from cpo._contract import digest


PROMPTOLUTION_SHA = '9ec426250c2c460cf08ef38ec7cd15ddd86e77e1a0f8dc2868ca7fbb97760522'
CPO = {controls.SETTLED: controls.run_settled_episode, promptolution.ROUTED: promptolution.routed}
WIDTHS = (2, 8)


def prepare():
    language_plan, _ = language.prepare()
    wide = controls.locked('docs/validation-routed-opening-v1.json', promptolution.ROUTING_RECEIPT_SHA)
    origin = controls.locked('docs/validation-routed-promptolution-v1.json', PROMPTOLUTION_SHA)
    transfer, *_ = promptolution.prepare()
    if (digest(wide['plan']) != wide['planSha256'] or digest(language_plan) != wide['plan']['languagePlanSha256']
            or digest(transfer) != digest(origin['plan']) or digest(transfer) != origin['planSha256']):
        raise ValueError('The published narrow and wide comparisons must reproduce')
    root = language.refit.transfer.ROOT
    files = (__file__, layouts.__file__, language.scout.__file__, language.refit.__file__,
             promptolution.__file__, frontier.__file__)
    sources = {str(Path(file).resolve().relative_to(root)): sha256(Path(file).read_bytes()).hexdigest()
               for file in files}
    plan = {**language_plan, 'protocol': 'cpo-validation-routed-roster-width-v1',
            'promptolutionReceiptSha256': PROMPTOLUTION_SHA,
            'wideRoutedReceiptSha256': promptolution.ROUTING_RECEIPT_SHA,
            'rosterWidths': WIDTHS, 'nativeMethods': transfer['nativeMethods'],
            'controlSettings': transfer['controlSettings'],
            'sourceSha256': {**language_plan['sourceSha256'], **transfer['sourceSha256'], **sources},
            'scope': ('For every existing language episode, replay both packaged CPO policies on the original '
                      'eight-challenger rosters and their ordered two-challenger prefixes. Keep initial prompts, '
                      'seeds, case splits and independent qualification. Compare the two-challenger policies '
                      'with the frozen Promptolution native GEPA and halving settings on the same rosters. '
                      'Resample paired cases by subject and reselect the strongest affordable control per draw. '
                      'Measure whether the routed-versus-settled quality difference changes with roster width.')}
    return plan, wide


def play_cpo(cells, stages, start, arm):
    with patch.object(language.scout.feedback, 'run_feedback_episode', CPO[arm]):
        return language.scout.language_episode(cells, stages, start)


def measure(plan, target, panels, reference):
    refit = language.refit
    routed = promptolution.ROUTED
    settled = controls.SETTLED
    native = tuple(plan['nativeMethods'])
    simple = tuple(name for name in plan['controlSettings'] if name not in native)
    competitors = (*native, *simple, frontier.RETAIN)
    arm_counts = {width: {arm: Counter() for arm in (*CPO, *(competitors if width == 2 else ()))}
                  for width in WIDTHS}
    vectors = {width: {} for width in WIDTHS}
    traces = sha256()
    episodes = 0
    for subject, model, matrix in panels:
        cells, _ = refit.transfer.case_cells(matrix)
        stored = {str(index): ''.join(map(str, row)) for index, row in enumerate(matrix)}
        for seed in target['seeds']:
            start, original_stages = layouts.stages(subject, len(matrix[0]), len(matrix), seed, target)
            if any(len(roster) != max(WIDTHS) for _, roster, _ in original_stages):
                raise ValueError('Compare against the full original ordered roster')
            held = original_stages[0][2][-1]
            for width in WIDTHS:
                stages = [(local, roster[:width], roles) for local, roster, roles in original_stages]
                measured = {}
                for arm in CPO:
                    result, paid = play_cpo(cells, stages, start, arm)
                    cost = Counter(paidLookups=len(paid))
                    cost.update(f'{role}Lookups' for role, *_ in paid)
                    cost['overriddenCycles'] = sum(schedule != result.schedule for schedule in
                                                   getattr(result, 'cycle_schedules', ()))
                    measured[arm] = result.prompt, cost
                    if arm == routed and width == max(WIDTHS):
                        traces.update(bytes.fromhex(digest(
                            (subject, model, seed, result.prompt, result.cycle_schedules, paid))))
                if width == min(WIDTHS):
                    windows = [(roster, roles[0], roles[1], roles[2]) for _, roster, roles in stages]
                    with patch.object(controls.donor, 'START', start):
                        for arm in competitors:
                            prompt, cost, _ = controls.play(plan, stored, windows, seed, arm)
                            measured[arm] = prompt, cost
                scores = vectors[width].setdefault(subject, {})
                for arm, (prompt, cost) in measured.items():
                    grades = [cells[prompt][case] for case in held]
                    arm_counts[width][arm].update(cost, holdoutPasses=sum(grades))
                    preceding = scores.setdefault(arm, [0] * len(held))
                    scores[arm] = [before + grade for before, grade in zip(preceding, grades, strict=True)]
            episodes += 1
    if (episodes != reference['episodes'] or arm_counts[8][routed] != reference['totals'][routed]
            or traces.hexdigest() != reference['paidTraceSha256'][routed]):
        raise ValueError('The original wide-roster routed trajectory must reproduce')

    effects = refit.native.frozen.paired_effects.paired_effect
    interaction = {
        subject: {
            'differenceOfDifferences': [r2 - s2 - r8 + s8 for r2, s2, r8, s8 in zip(
                scores[routed], scores[settled], vectors[8][subject][routed], vectors[8][subject][settled],
                strict=True)],
            'zero': [0] * len(scores[routed]),
        } for subject, scores in vectors[2].items()
    }
    paired = {width: effects(vectors[width], routed, settled, target) for width in WIDTHS}
    matched = frontier.compare(
        arm_counts[2], vectors[2], policies=tuple(CPO), draws=target['bootstrapDraws'],
        seed=target['bootstrapSeed'], groups={'nativeGepa': native, 'halving': simple},
    )
    return {'episodesPerWidth': episodes, 'totalsByWidth': arm_counts, 'pairedRoutedVsSettledByWidth': paired,
            'widthInteraction': effects(interaction, 'differenceOfDifferences', 'zero', target),
            'twoChallengerControls': matched, 'wideRoutedPaidTraceSha256': traces.hexdigest()}


def replay(plan, wide):
    refit = language.refit
    base, context, baseline = refit.contract()
    fitted = controls.locked('docs/settled-episode-refit-v1.json', language.parity.FIT_SHA)
    results = {}
    for cohort, lock in plan['languageReceiptSha256'].items():
        target, (panels, *_) = refit.target(cohort, base, context, baseline, fitted)
        original = controls.locked(f'docs/settled-episode-refit-transfer-{cohort.lower()}-v1.json', lock)
        if digest(target) != digest(original['plan']) or digest(target) != original['planSha256']:
            raise ValueError('Use the original language case splits')
        results[cohort] = measure(plan, target, panels, wide['language'][cohort])
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'cohorts': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, wide = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    result = replay(plan, wide)
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
