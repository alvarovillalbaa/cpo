"""Transfer the frozen full-roster feedback runner to recorded math rosters."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import recorded_math_router_transfer as math_transfer
from benchmarks import recorded_math_validation_ties as math
from cpo import Observation, Row
from cpo._contract import digest
from cpo.feedback_episode import run_feedback_episode
from cpo.full_roster_precheck import run_full_roster_feedback_episode
from cpo.settled_episode import EpisodeCycle


PROTOTYPE_SHA = '636cc17bbfd8d330557c3b683b6fe0e5bca795744b9f520472e9d095ef4743a7'
FEEDBACK, FULL_ROSTER = 'cpo-feedback', 'cpo-full-roster-precheck'
HISTORICAL = math_transfer.prior.HISTORICAL
RUNNERS = {FEEDBACK: run_feedback_episode, FULL_ROSTER: run_full_roster_feedback_episode}


def prepare():
    original, data = math.prepare()
    verify = (math.ROOT / 'docs/full-roster-precheck-verification-v1.json').read_bytes()
    if sha256(verify).hexdigest() != PROTOTYPE_SHA:
        raise ValueError('Use the published opt-in runner and its original verification')
    files = (__file__, math_transfer.__file__, math_transfer.prior.__file__,
             math.ROOT / 'cpo/full_roster_precheck/__init__.py', math.ROOT / 'cpo/feedback_episode.py')
    source = {str(Path(file).resolve().relative_to(math.ROOT)): sha256(Path(file).read_bytes()).hexdigest()
              for file in files}
    plan = {**{name: original[name] for name in ('datasets', 'corpusSha256', 'gepaVersion', 'challengerCounts',
                                                 'incumbentGroups', 'searchCap', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'cpo-full-roster-precheck-math-transfer-v1', 'archivedMathPlanSha256': digest(original),
            'optInVerificationSha256': PROTOTYPE_SHA, 'sourceSha256': {**original['sourceSha256'], **source},
            'primaryArms': tuple(RUNNERS), 'qualificationRows': 4, 'trainingProbes': 2,
            'scope': 'Keep each original seed, ordered roster, start, training, validation and holdout. '
                     'Use the first four independent qualification cases for every method. Feed the first '
                     'two training rows and one cycle to both unchanged feedback runners. Require all '
                     'nominees and deployments to agree. Compare their realized lookups to the original '
                     'split-safe native GEPA sweep or retention repriced on the same four qualification cases.'}
    return plan, data


def four_case_trials(cells, settings, group, width):
    for incumbent, roster, (training, validation, admission, held), seed in math_transfer.prior.trials(
            cells, settings, group, width):
        if len(admission) < 4 or len(training) < 2:
            raise ValueError('Use the full original four-case reserve and the two opening probes')
        yield incumbent, roster, (training, validation, admission[:4], held), seed


def episode(runner, cells, trial):
    incumbent, roster, (training, validation, qualification, held), seed = trial
    paid, observed = [], set()
    layout = dict(training=training[:2], validation=validation, qualification=qualification)

    def rows(role):
        return tuple(Row(str(case), role) for case in layout[role])

    def grade(prompt, row):
        case = int(row.id)
        key = row.family, prompt, case
        if case not in layout[row.family] or prompt not in (incumbent, *roster) or key in observed:
            raise ValueError('A paid callback left the trial geometry or repeated a reply')
        observed.add(key)
        passed = bool(cells[prompt][case][0])
        paid.append((*key, passed))
        return passed

    def qualify(prompt, row, repeat):
        if repeat != 0:
            raise ValueError('The math archive includes one qualification reply per case')
        return grade(prompt, row)

    cycle = EpisodeCycle(tuple(roster), rows('validation'), rows('qualification'), seed)
    result = runner(incumbent, rows('training'), (cycle,), lambda p, row: Observation(grade(p, row), {}),
                    probe=grade, qualify=qualify)
    grades = [cells[result.prompt][case][0] for case in held]
    if result.evaluations != len(paid):
        raise ValueError('All paid replies must reconcile to the runner result')
    cost = Counter(paidLookups=len(paid), holdoutPasses=sum(grades))
    cost.update(f'{role}Lookups' for role, *_ in paid)
    if cells[incumbent][0][1] is not None:
        cost[HISTORICAL] = sum(cells[prompt][case][1] or 0 for _, prompt, case, _ in paid)
    finalist = result.cycles[0].search.finalist
    if finalist is not None:
        gain = sum(cells[finalist][case][0] - cells[incumbent][case][0] for case in qualification)
        if result.prompt != (finalist if gain >= 1 else incumbent):
            raise ValueError('The measured disposition must match the exact paired proof')
    return result, cost, grades, paid


def measure(plan, subject, cells, group, width):
    trials = list(four_case_trials(cells, plan['datasets'][subject], group, width))
    totals = {arm: Counter() for arm in RUNNERS}
    vectors = {arm: [0] * len(next(iter(cells.values()))) for arm in RUNNERS}
    traces = {arm: sha256() for arm in RUNNERS}
    decisions, accounting = {}, Counter(lowerCost=0, higherCost=0, sameCost=0)
    for trial in trials:
        start, _, roles, seed = trial
        baseline = None
        for arm, runner in RUNNERS.items():
            result, cost, grades, paid = episode(runner, cells, trial)
            point = (result.schedule, result.cycles[0].search.finalist, result.prompt)
            if baseline is None:
                baseline = point, cost
            else:
                if point != baseline[0]:
                    raise ValueError('The opt-in runner must preserve every original decision')
                delta = cost['paidLookups'] - baseline[1]['paidLookups']
                label = 'lowerCost' if delta < 0 else 'higherCost' if delta > 0 else 'sameCost'
                accounting[label] += 1
                by_schedule = decisions.setdefault(result.schedule, Counter())
                by_schedule.update(trials=1, paidLookupDelta=delta)
                for role in ('validation', 'qualification'):
                    key = f'{role}Lookups'
                    by_schedule[f'{role}LookupDelta'] += cost[key] - baseline[1][key]
            totals[arm].update(cost)
            math_transfer.accumulate(vectors[arm], roles[-1], grades)
            traces[arm].update(bytes.fromhex(digest((seed, start, point, paid))))

    available = math_transfer.native_settings(cells, trials, plan)
    native = tuple(name for name in available if name != math_transfer.RETAIN)
    paired = math_transfer.native.frozen.paired_effects.paired_effect
    controls = {}
    for arm in RUNNERS:
        best = math_transfer.native.gepa.best_fixed(available, native, totals[arm]['paidLookups'])
        selected = math_transfer.native_attainer(cells, trials, best)
        controls[arm] = {'bestAffordableGepaOrRetain': best,
                         'paired': paired({subject: {arm: vectors[arm], 'control': selected}}, arm, 'control', plan)}
    return {'episodes': len(trials), 'totals': totals, 'pairedLookupOutcomes': accounting, 'bySchedule': decisions,
            'paidTraceSha256': {arm: trace.hexdigest() for arm, trace in traces.items()},
            'matchedControls': controls, 'nativeSettings': len(native)}


def replay(plan, data):
    result = {}
    for subject in plan['datasets']:
        cells = math.load_cells(subject, data[subject]['record'])
        result[subject] = {f'{group}/{width}': measure(plan, subject, cells, group, width)
                           for group in plan['incumbentGroups'] for width in plan['challengerCounts']}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'math': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    result = replay(plan, data)
    with args.out.open('x') as out:
        out.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
