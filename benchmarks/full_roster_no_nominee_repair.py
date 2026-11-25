"""Locate the missing math nominees and test one paid validation probe."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import full_roster_precheck_math as transfer
from cpo import Row
from cpo._contract import digest
from cpo.paired_qualification import certify_paired_qualification
from cpo.settled_episode import _MAX_VALIDATION_READS


PARENT_SHA = '1d9c66cbe25b27f7fa7f5c6267fa8b58f48054f37d52a153ef91fa4ee5c68b31'
REPAIR = 'one-miss-probe'


def prepare():
    original, data = transfer.prepare()
    root = transfer.math.ROOT
    packed = (root / 'docs/full-roster-precheck-math-v1.json').read_bytes()
    if sha256(packed).hexdigest() != PARENT_SHA:
        raise ValueError('Verify the original math replay before testing an added probe')
    parent = json.loads(packed)
    if digest(original) != parent['planSha256'] or digest(parent['plan']) != parent['planSha256']:
        raise ValueError('The original math plan must reproduce')
    plan = {**original, 'protocol': 'cpo-full-roster-no-nominee-repair-v1', 'parentReceiptSha256': PARENT_SHA,
            'parentPlanSha256': parent['planSha256'],
            'sourceSha256': {**original['sourceSha256'], str(Path(__file__).resolve().relative_to(root)):
                             sha256(Path(__file__).read_bytes()).hexdigest()},
            'scope': 'Separate harmful promotions from better proof-eligible candidates in hindsight. '
                     'On no-nominee trials, retain when the observed admission precheck rules out a gain. '
                     'Otherwise offer one challenger with a paid repair and no observed paired loss. If there '
                     'is none, use at most one new challenger reply on an already paid incumbent miss. '
                     'Keep the original 19-read validation ceiling, disjoint admission and four-case proof. '
                     'Choose by paid facts only. Compare at actual lookups with the original GEPA sweep.'}
    return plan, data, parent


def witness_options(start, roster, rows, paid):
    seen = {(prompt, case): passed for role, prompt, case, passed in paid if role == 'validation'}
    available = []
    for prompt in roster:
        gains = [seen[prompt, row] - seen[start, row] for row in rows
                 if (prompt, row) in seen and (start, row) in seen]
        if -1 not in gains:
            available.append((sum(gains), prompt))
    ready = max((item for item in available if item[0] > 0), key=lambda item: item[0], default=None)
    probe = next(((prompt, row) for row in rows if seen.get((start, row)) is False
                  for _, prompt in available if (prompt, row) not in seen), None)
    return ready[1] if ready else None, probe


def rescue(cells, trial, original, paid):
    start, roster, (_, rows, admission, _), seed = trial
    stats, additional = Counter(), []
    if original.cycles[0].search.finalist is not None:
        return original.prompt, additional, stats
    nominee, probe = witness_options(start, roster, rows, paid)
    stats['paidWitnesses'] += int(nominee is not None)
    previous = {(prompt, case): passed for role, prompt, case, passed in paid if role == 'qualification'}
    if all(previous.get((start, case)) is True for case in admission):
        stats['paidWitnessWithClosedAdmission'] += int(nominee is not None)
        return start, additional, stats

    if nominee is None and probe is not None and original.cycles[0].search.evaluations < _MAX_VALIDATION_READS:
        challenger, case = probe
        passed = bool(cells[challenger][case][0])
        additional.append(('validation', challenger, case, passed))
        stats['newValidationProbes'] += 1
        if passed:
            nominee = challenger
            stats['newWitnesses'] += 1
    if nominee is None:
        return start, additional, stats

    def read(prompt, row, repeat):
        case = int(row.id)
        key = prompt, case
        if key not in previous:
            previous[key] = bool(cells[prompt][case][0])
            additional.append(('qualification', prompt, case, previous[key]))
        return previous[key]

    proof = certify_paired_qualification(start, nominee, [Row(str(case), 'qualification') for case in admission],
                                         read, seed=seed)
    full_gain = sum(cells[nominee][case][0] - cells[start][case][0] for case in admission)
    if proof.prompt != (nominee if full_gain > 0 else start):
        raise ValueError('The additional admission must settle under the original independent gate')
    stats.update(qualificationAttempts=1, additionalDeployments=int(proof.status == 'promoted'))
    return proof.prompt, additional, stats


def attribute(cells, trial, original, grades):
    start, roster, (_, _, admission, held), _ = trial
    before = sum(cells[start][case][0] for case in held)
    gain = sum(grades) - before
    eligible = [prompt for prompt in roster if sum(cells[prompt][case][0] - cells[start][case][0]
                                                  for case in admission) > 0]
    best = max((sum(cells[prompt][case][0] for case in held) for prompt in (start, *eligible)), default=before)
    step = original.cycles[0]
    status = 'promoted' if step.promoted else 'rejected-nominee' if step.search.finalist else 'no-nominee'
    return status, {'trials': 1, 'grossHarmfulPromotionPasses': max(0, -gain),
                    'grossBeneficialPromotionPasses': max(0, gain),
                    'betterEligibleNomineeCeiling': best - before - max(0, gain)}


def measure(plan, task, cells, group, width, original):
    trials = list(transfer.four_case_trials(cells, plan['datasets'][task], group, width))
    labels = (transfer.FULL_ROSTER, REPAIR)
    totals = {name: Counter() for name in labels}
    vectors = {name: [0] * len(next(iter(cells.values()))) for name in labels}
    audit, activity = {}, Counter()
    trace = sha256()
    for trial in trials:
        start, _, roles, seed = trial
        baseline, costs, grades, paid = transfer.episode(transfer.RUNNERS[transfer.FULL_ROSTER], cells, trial)
        step = baseline.cycles[0]
        choice = baseline.schedule, step.search.finalist, baseline.prompt
        trace.update(bytes.fromhex(digest((seed, start, choice, paid))))
        status, counts = attribute(cells, trial, baseline, grades)
        audit.setdefault(status, Counter()).update(counts)
        prompt, extra, stats = rescue(cells, trial, baseline, paid)
        revised = [cells[prompt][case][0] for case in roles[-1]]
        if len({row[:3] for row in (*paid, *extra)}) != len(paid) + len(extra):
            raise ValueError('Charge every new reply once and credit all reused replies')
        new_cost = Counter(costs)
        new_cost['holdoutPasses'] = sum(revised)
        new_cost['paidLookups'] += len(extra)
        new_cost.update(f'{role}Lookups' for role, *_ in extra)
        if transfer.HISTORICAL in new_cost:
            new_cost[transfer.HISTORICAL] += sum(cells[p][case][1] or 0 for _, p, case, _ in extra)
        activity.update(stats)
        for name, point, outcome in ((transfer.FULL_ROSTER, costs, grades), (REPAIR, new_cost, revised)):
            totals[name].update(point)
            transfer.math_transfer.accumulate(vectors[name], roles[-1], outcome)
    if (totals[transfer.FULL_ROSTER] != original['totals'][transfer.FULL_ROSTER]
            or trace.hexdigest() != original['paidTraceSha256'][transfer.FULL_ROSTER]):
        raise ValueError('The published full-roster trace must reproduce')
    native = transfer.math_transfer
    available = native.native_settings(cells, trials, plan)
    modes = tuple(name for name in available if name != native.RETAIN)
    best = native.native.gepa.best_fixed(available, modes, totals[REPAIR]['paidLookups'])
    vectors['control'] = native.native_attainer(cells, trials, best)
    effect = native.native.frozen.paired_effects.paired_effect
    return {'episodes': len(trials), 'diagnosticsByOriginalOutcome': audit, 'probesAndQualification': activity,
            'totals': totals, 'bestAffordableGepaOrRetain': best,
            'paired': {peer: effect({task: vectors}, REPAIR, peer, plan) for peer in (transfer.FULL_ROSTER, 'control')}}


def replay(plan, data, parent):
    outcomes = {}
    for task in plan['datasets']:
        cells = transfer.math.load_cells(task, data[task]['record'])
        outcomes[task] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                name = f'{group}/{width}'
                outcomes[task][name] = measure(plan, task, cells, group, width, parent['math'][task][name])
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': outcomes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, parent = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    result = replay(plan, data, parent)
    with args.out.open('x') as out:
        out.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
