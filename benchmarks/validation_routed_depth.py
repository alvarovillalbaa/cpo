"""Test two and four uniform validation cases on two-challenger CPO rosters."""

import argparse
from collections import Counter
from dataclasses import replace
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import validation_routed_roster_width as width
from cpo._contract import digest
from cpo.full_roster_precheck import fixed_opening
from cpo.full_roster_precheck.validation_routing import run_validation_routed_episode


language, transfer, prompt = width.language, width.controls, width.promptolution
ROSTER_RECEIPT = 'd61c82474aa60d31a17340704307ce585e879d45f5e4414b2ad410565ddd8562'
DEPTHS = {'uniform-depth-2': 2, 'uniform-depth-4': 4}
SETTLED, ROUTED = transfer.SETTLED, prompt.ROUTED


def limit_cycle(cycle, schedule, depth):
    if (schedule == language.OPENING and len(cycle.candidates) == 2
            and not any(row.critical for row in cycle.validation)):
        return replace(cycle, validation=cycle.validation[:depth])
    return cycle


def run_limited(depth, incumbent, _training, cycles, evaluate, *, probe, qualify):
    original = fixed_opening._cycle

    def capped(schedule, start, cycle, read, proof):
        return original(schedule, start, limit_cycle(cycle, schedule, depth), read, proof)

    with patch.object(fixed_opening, '_cycle', capped):
        return run_validation_routed_episode(incumbent, cycles, evaluate, qualify=qualify)


RUNNERS = {**width.CPO, **{arm: partial(run_limited, depth) for arm, depth in DEPTHS.items()}}


def prepare():
    original, _ = width.prepare()
    reference = transfer.locked('docs/validation-routed-roster-width-v1.json', ROSTER_RECEIPT)
    archived, *_ = prompt.prepare()
    prompt_reference = transfer.locked('docs/validation-routed-promptolution-v1.json', width.PROMPTOLUTION_SHA)
    if (digest(original) != digest(reference['plan']) or digest(original) != reference['planSha256']
            or digest(archived) != prompt_reference['planSha256']):
        raise ValueError('The published width and Promptolution comparisons must reproduce')
    plan = {**original, 'protocol': 'cpo-validation-routed-depth-v1', 'rosterWidthReceiptSha256': ROSTER_RECEIPT,
            'rosterWidths': (2,), 'arms': tuple(RUNNERS),
            'sourceSha256': {**original['sourceSha256'],
                             'benchmarks/validation_routed_depth.py': sha256(Path(__file__).read_bytes()).hexdigest()},
            'uniformValidationDepths': DEPTHS,
            'scope': ('Limit uniform validation to the first two or four cases when a cycle has exactly two '
                      'challengers and no critical validation rows. Keep opening probes, other schedules, '
                      'and independent admission unchanged. Compare both frozen depths with settled and '
                      'uncapped routed CPO on the enrolled language prefixes and Promptolution rosters. '
                      'Reprice the original affordable GEPA and halving settings at each realized budget.')}
    return plan, reference, prompt_reference


def measure_language(plan, target, panels, reference):
    refit = language.refit
    native = tuple(plan['nativeMethods'])
    simple = tuple(arm for arm in plan['controlSettings'] if arm not in native)
    peers = (*native, *simple, width.frontier.RETAIN)
    counts = {arm: Counter() for arm in (*RUNNERS, *peers)}
    vectors = {}
    episodes = 0
    for subject, _, matrix in panels:
        cells, _ = refit.transfer.case_cells(matrix)
        stored = {str(index): ''.join(map(str, row)) for index, row in enumerate(matrix)}
        for seed in target['seeds']:
            start, full = width.layouts.stages(subject, len(matrix[0]), len(matrix), seed, target)
            stages = [(local, roster[:2], roles) for local, roster, roles in full]
            held = stages[0][2][-1]
            windows = [(roster, roles[0], roles[1], roles[2]) for _, roster, roles in stages]
            measured = {}
            for arm, runner in RUNNERS.items():
                with patch.object(language.scout.feedback, 'run_feedback_episode', runner):
                    result, paid = language.scout.language_episode(cells, stages, start)
                cost = Counter(paidLookups=len(paid))
                cost.update(f'{role}Lookups' for role, *_ in paid)
                cost['overriddenCycles'] = sum(schedule != result.schedule for schedule in
                                               getattr(result, 'cycle_schedules', ()))
                measured[arm] = result.prompt, cost
            with patch.object(transfer.donor, 'START', start):
                for arm in peers:
                    winner, cost, _ = transfer.play(plan, stored, windows, seed, arm)
                    measured[arm] = winner, cost
            scores = vectors.setdefault(subject, {})
            for arm, (winner, cost) in measured.items():
                grades = [cells[winner][case] for case in held]
                counts[arm].update(cost, holdoutPasses=sum(grades))
                preceding = scores.setdefault(arm, [0] * len(held))
                scores[arm] = [left + right for left, right in zip(preceding, grades, strict=True)]
            episodes += 1
    if episodes != reference['episodesPerWidth'] or any(
            counts[arm] != expected for arm, expected in reference['totalsByWidth']['2'].items()):
        raise ValueError('The original two-challenger baseline and controls must reproduce')
    effects = refit.native.frozen.paired_effects.paired_effect
    return {
        'episodes': episodes, 'totals': counts,
        'paired': {name: {peer: effects(vectors, name, peer, target) for peer in (ROUTED, SETTLED)} for name in DEPTHS},
        'matchedControls': width.frontier.compare(
            counts, vectors, policies=tuple(DEPTHS), draws=target['bootstrapDraws'],
            seed=target['bootstrapSeed'], groups={'nativeGepa': native, 'halving': simple}),
    }


def language_replay(plan, reference):
    refit = language.refit
    base, context, baseline = refit.contract()
    fitted = transfer.locked('docs/settled-episode-refit-v1.json', language.parity.FIT_SHA)
    results = {}
    for cohort, lock in plan['languageReceiptSha256'].items():
        target, (panels, *_) = refit.target(cohort, base, context, baseline, fitted)
        previous = transfer.locked(f'docs/settled-episode-refit-transfer-{cohort.lower()}-v1.json', lock)
        if digest(target) != digest(previous['plan']) or digest(target) != previous['planSha256']:
            raise ValueError('Use the original language case splits')
        results[cohort] = measure_language(plan, target, panels, reference['cohorts'][cohort])
    return results


def prompt_replay(plan, reference, archive):
    native = plan['nativeMethods']
    peers = (transfer.BASE, *transfer.WITNESS, *plan['controlSettings'])
    arms = (ROUTED, SETTLED, *DEPTHS, *peers)

    def compare(panels):
        return {name: {'routed': transfer.compare(plan, panels, name, (ROUTED,), enforce_cap=False),
                       'settled': transfer.compare(plan, panels, name, (SETTLED,), enforce_cap=False),
                       'nativeGepa': transfer.compare(plan, panels, name, native),
                       'allControls': transfer.compare(plan, panels, name, peers)} for name in DEPTHS}

    reports, pooled = {}, []
    for task in plan['tasks']:
        panel = archive[task]
        observed = reference['tasks'][task]
        held = sorted(Random(f"{plan['holdoutSeed']}/{task}").sample(range(len(panel['caseIDs'])), transfer.donor.HOLDOUT))
        holdout = digest([panel['caseIDs'][case] for case in held])
        if holdout != observed['heldCaseSha256']:
            raise ValueError('Keep the original Promptolution case identities')
        counts = {name: Counter() for name in arms}
        vectors = {name: [0] * len(held) for name in arms}
        for seed in plan['seeds']:
            windows = transfer.layout(plan, task, seed, held)
            matrix = panel['correctness']
            for arm in arms:
                winner, cost, _ = prompt.play(plan, matrix, windows, seed, arm)
                grades = [matrix[winner][case] == '1' for case in held]
                counts[arm].update(cost, holdoutPasses=sum(grades))
                vectors[arm] = [left + right for left, right in zip(vectors[arm], grades, strict=True)]
        if any(counts[name] != observed['totals'][name] for name in (ROUTED, SETTLED, *peers)):
            raise ValueError('The original Promptolution baselines must reproduce')
        pair = counts, vectors
        pooled.append(pair)
        reports[task] = {'episodes': len(plan['seeds']), 'totals': counts, 'comparisons': compare([pair])}
    return {'tasks': reports, 'pooledComparisons': compare(pooled)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, reference, prompt_reference = prepare()
    seal = digest(plan)
    if not (args.execute or args.out or args.corpus):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if (args.execute != seal or not args.out or args.out.exists() or not args.corpus
            or version('gepa') != plan['gepaVersion']):
        parser.error('Replay requires the pinned corpus, current seal, pinned GEPA and a fresh output path')
    archive = transfer.donor.load_corpus(args.corpus.read_bytes())
    prompt_plan, *_ = prompt.prepare()
    with patch.dict(prompt.RUNNERS, {name: RUNNERS[name] for name in DEPTHS}):
        promptolution = prompt_replay(prompt_plan, prompt_reference, archive)
    result = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
              'promptolution': promptolution, 'language': language_replay(plan, reference)}
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
