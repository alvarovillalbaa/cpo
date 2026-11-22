"""Reinvest unspent validation reads in one stronger certified finalist."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import deferred_two_sided_certificate as previous
from cpo._contract import digest
from cpo.single_finalist import FinalistResult


paired, cycle = previous.paired, previous.cycle
REPORT = 'docs/deferred-two-sided-certificate-results-v1.json'
REPORT_SHA256 = 'b50173bfd6964cceb58ae34f8492fc1df00a70f7c25b1bee6ef46530a26de0c4'
FULL, MINIMUM, REPAIR = 'full-proof-reserve', 'minimum-proof-reserve', 'complementary-repair'
POLICIES = FULL, MINIMUM, REPAIR


def prepare():
    parent, panels, controls, _, native = previous.prepare()
    read = paired.frontier.cost.prior.baseline.read_reference
    earlier = read(REPORT, REPORT_SHA256, parent)['results']
    plan = {**parent, 'protocol': 'two-sided-finalist-challenge-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': REPORT_SHA256,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': POLICIES,
            'scope': 'Keep the first two-sided certificate and its paid validation journal. '
                     'If search money remains, challenge the first nominee on the same validation cases, '
                     'favoring candidates with fewest additional favorable replies needed. Certify one '
                     'strict gain over the first nominee and preserve its critical passes. Keep the first '
                     'nominee on failure. Compare a full missing-pair reserve with a best-case reserve '
                     'and send only the final nominee to the original independent proof. The exploratory '
                     'repair arm instead requires a paid pass on the first nominee\'s first observed '
                     'miss and a strict certificate against the original incumbent.'}
    return plan, panels, controls, earlier, native


def screen(incumbent, candidates, rows, evaluate, cap, *, policy):
    paid = {prompt: {} for prompt in (incumbent, *candidates)}
    used = 0

    def observe(prompt, row):
        nonlocal used
        if row.id in paid[prompt] or used >= cap:
            raise ValueError('The validation journal must pay each case once and respect the cap')
        reply = evaluate(prompt, row)
        if type(reply.passed) is not bool:
            raise ValueError('Validation requires exact boolean outcomes')
        paid[prompt][row.id] = reply.passed
        used += 1
        return reply

    initial, counts = cycle._screen(incumbent, candidates, rows, observe, cap, expected=True)
    finalist = initial.finalist
    if finalist is None or used == cap:
        return initial, counts
    witness = None
    if policy == REPAIR:
        witness = next((row for row in rows if paid[finalist].get(row.id) is False), None)
        if witness is None:
            return initial, counts
    reference = incumbent if witness is not None else finalist
    base = paid[reference]
    roster = candidates[:max(0, cap - 2 * len(rows) + 1)]
    pending = [prompt for prompt in roster if prompt != finalist]
    size = len(rows)
    protected = tuple(row.id for row in rows if row.critical)

    def estimate(prompt):
        observed = paid[prompt]
        favorable = len(base) - sum(base.values()) + sum(observed.values())
        unfavorable = len(base) + len(observed) - favorable
        if witness is not None and observed.get(witness.id) is False:
            return None
        probe = int(witness is not None and witness.id not in observed)
        covered = witness.id if probe else None
        unresolved = [case for case in protected
                      if case != covered and base.get(case) is not False and observed.get(case) is not True]
        if unfavorable >= size or any(base.get(case) is True and observed.get(case) is False for case in unresolved):
            return None
        minimum = probe + max(size + 1 - favorable - probe, len(unresolved))
        reserve = 2 * size - len(base) - len(observed) if policy == FULL and minimum else minimum
        return minimum if reserve <= cap - used else None

    while pending:
        feasible = [(cost, index) for index, prompt in enumerate(pending) if (cost := estimate(prompt)) is not None]
        if not feasible:
            break
        _, index = min(feasible)
        prompt = pending.pop(index)
        if witness is not None and witness.id not in paid[prompt] and not observe(prompt, witness).passed:
            continue
        pair = reference, prompt
        if cycle._certify(rows, base, paid[prompt], lambda side, row: observe(pair[side], row).passed,
                          cap - used, len(rows) <= 8):
            finalist = prompt
            break
    if finalist != initial.finalist:
        counts = tuple((sum(paid[prompt].values()), len(paid[prompt])) for prompt in (incumbent, finalist))
    return FinalistResult(finalist, finalist, used), counts


def run_trial(policy, args):
    runner = partial(cycle._run, screen=partial(screen, policy=policy))
    return paired.cycle.execute_path(runner, *args)


def audit_headroom(cells, incumbent, roster, roles, base, paid, gain, cap):
    """Use the sealed archive to separate insufficient gains from insufficient budget."""
    _, validation, qualification, held = roles
    nominee = base.search.finalist
    if nominee is None and base.search.evaluations == 0:
        return 'qualificationPrecheckEliminatedRoster'
    held_start = sum(cells[base.prompt][case] for case in held)
    incumbent_score = sum(cells[incumbent][case] for case in validation)
    incumbent_proof = sum(cells[incumbent][case] for case in qualification)
    better = [prompt for prompt in roster if prompt != nominee and
              sum(cells[prompt][case] for case in held) > held_start and
              sum(cells[prompt][case] for case in qualification) >= incumbent_proof + gain and
              sum(cells[prompt][case] for case in validation) > incumbent_score]
    if nominee is None:
        return 'noNomineeDespiteBetterIndependentWinner' if better else 'noNomineeWithoutBetterIndependentWinner'
    if not better:
        return 'noBetterIndependentWinner'
    nominee_score = sum(cells[nominee][case] for case in validation)
    strict = [prompt for prompt in better if sum(cells[prompt][case] for case in validation) > nominee_score]
    if not strict:
        return 'betterPromptDoesNotBeatNomineeOnValidation'
    remaining = cap - base.search.evaluations
    known_misses = sum(not grade for (role, prompt, _), grade in paid.items()
                       if role == 'validation' and prompt == nominee)
    for prompt in strict:
        known_passes = sum(grade for (role, owner, _), grade in paid.items()
                           if role == 'validation' and owner == prompt)
        if max(0, len(validation) + 1 - known_misses - known_passes) <= remaining:
            return 'betterStrictPromptFitsInHindsight'
    return 'betterStrictPromptExceedsMinimumReads'


def measure(panels, plan, controls, earlier, native):
    totals = {label: {policy: Counter() for policy in POLICIES} for label in controls.values()}
    room = {label: Counter() for label in controls.values()}
    paths = {}
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        panel = f'{subject}/{model}'
        traces = {label: {policy: [] for policy in (previous.EXPECTED, *POLICIES)} for label in controls.values()}
        for seed in plan['seeds']:
            start, roster, roles = paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            for gain, label in controls.items():
                args = cells, start, roster, roles, seed, plan['fullRosterCap'], gain
                base, previous_paid = previous.run_trial(previous.EXPECTED, args)
                anchor, _, trace = paired.reference.point(cells, roles[-1], base, previous_paid)
                traces[label][previous.EXPECTED].append(trace)
                original_search = [(key, value) for key, value in previous_paid.items() if key[0] == 'validation']
                room[label][audit_headroom(cells, start, roster, roles, base, previous_paid,
                                           gain, plan['fullRosterCap'])] += 1
                for policy in POLICIES:
                    result, paid = run_trial(policy, args)
                    previous.previous.check_deployment(cells, start, roles, result, gain)
                    old_nominee, new_nominee = base.search.prompt, result.search.prompt
                    changed = old_nominee != new_nominee
                    if changed:
                        if old_nominee == start:
                            raise ValueError('The continuation must have a fallback nominee')
                        if policy == REPAIR:
                            witness = next(str(case) for case in roles[1]
                                           if previous_paid.get(('validation', old_nominee, str(case))) is False)
                            if paid.get(('validation', new_nominee, witness)) is not True:
                                raise ValueError('A repair must pass the first nominee\'s paid miss')
                        elif sum(cells[new_nominee][case] - cells[old_nominee][case] for case in roles[1]) <= 0:
                            raise ValueError('A replacement must strictly improve the first nominee')
                    if not changed and result.qualification != base.qualification:
                        raise ValueError('The retained nominee must use the original qualification path')
                    new_search = [(key, value) for key, value in paid.items() if key[0] == 'validation']
                    if new_search[:len(original_search)] != original_search:
                        raise ValueError('The entire two-sided search prefix must reproduce')
                    point, _, trace = paired.reference.point(cells, roles[-1], result, paid)
                    totals[label][policy].update(
                        **point, continuingTrials=int(len(new_search) > len(original_search)),
                        extraSearchLookups=len(new_search) - len(original_search),
                        changedNominee=int(changed), changedDeployment=int(base.prompt != result.prompt),
                        holdoutDifference=point['holdoutPasses'] - anchor['holdoutPasses'],
                        lookupDifference=point['paidLookups'] - anchor['paidLookups'],
                    )
                    traces[label][policy].append(trace)
        paths[panel] = {label: {policy: digest(trace) for policy, trace in methods.items()}
                        for label, methods in traces.items()}
        if any(paths[panel][label][previous.EXPECTED] != earlier['panelPathHashes'][panel][label][previous.EXPECTED]
               for label in controls.values()):
            raise ValueError('The two-sided baseline paid path must reproduce')
    comparisons = tuple((row['cpo']['paidLookups'], row['expandedSubjectCeiling'])
                        for row in native['comparisons'].values())
    bounds = {}
    for label, points in totals.items():
        bounds[label] = {}
        for policy, point in points.items():
            if any(point[key] - point[delta] != earlier['totals'][label][previous.EXPECTED][key]
                   for key, delta in (('holdoutPasses', 'holdoutDifference'), ('paidLookups', 'lookupDifference'))):
                raise ValueError('Scores and paired cost changes must reconcile to the two-sided baseline')
            bounds[label][policy] = {
                'lowerPasses': max((row['holdoutPasses'] for _, row in comparisons
                                    if row['paidLookups'] <= point['paidLookups']), default=None),
                'upperPasses': min((row['holdoutPasses'] for limit, row in comparisons
                                    if limit >= point['paidLookups']), default=None),
            }
    return {'totals': totals, 'affordableHeadroom': room, 'nativeGepaBounds': bounds, 'panelPathHashes': paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels, controls, earlier, native = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    results = {name: measure(cohort, plan, controls, earlier[name], native[name]) for name, cohort in panels.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
