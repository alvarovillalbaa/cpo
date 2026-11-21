"""Transfer precheck credit and expected-cost ordering to ARC-AGI and AIME."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_training_proof_order as prior
from cpo import expected_qualification as proof
from cpo._contract import digest
from cpo.paired_qualification import QualificationDecision, QualificationObservation


math, backup = prior.math, prior.backup
REFERENCE = 'docs/recorded-training-proof-order-results-v1.json'
REFERENCE_SHA256 = '980ec5af10a97a24b6bffae7d39ca6aaceed6aa59bf18c1637a649503fe9af5c'
ARMS = (prior.CANDIDATE, *prior.CONTROLS.values())
CREDIT = 'credit-precheck-in-seeded-proof-order'
EXPECTED = 'credit-precheck-and-order-by-expected-proof-cost'
ALTERNATIVES = (CREDIT, EXPECTED)
MODES = ('published', *ALTERNATIVES)


def qualify_with_prefix(incumbent, challenger, rows, observe, prefix, validation_counts, seed, mode):
    if (not rows or len({row.family for row in rows}) != 1 or any(row.critical for row in rows)
            or len({row.id for row in rows}) != len(rows)
            or tuple(prefix) != tuple(row.id for row in rows[:len(prefix)])
            or any(type(value) is not bool for value in prefix.values())):
        raise ValueError('Use a scalar qualification panel and its already-paid incumbent prefix')
    observations = [QualificationObservation(incumbent, case, 0, passed) for case, passed in prefix.items()]
    order, pending = Random(seed), []
    for row in rows:
        sides = [0, 1]
        order.shuffle(sides)
        pending.extend((side, row) for side in sides if side or row.id not in prefix)
    seeded = iter(pending)
    rates = (4 - proof._pass_rate(*validation_counts[0]), proof._pass_rate(*validation_counts[1]))
    sizes = (len(rows),)
    state = ((len(prefix), 0, sum(not value for value in prefix.values())),)
    prompts = incumbent, challenger
    while True:
        low, high = proof._bounds(sizes, state)
        status = proof._settled(low, high, 1)
        if status is not None:
            return QualificationDecision(status, challenger if status == 'promoted' else incumbent,
                                         tuple(observations), low[0], high[0])
        if mode == CREDIT:
            side, row = next(seeded)
        else:
            _, (_, side) = proof._minimum_expected_reads(sizes, rates, 1, state)
            row = rows[state[0][side]]
        passed = observe(prompts[side], row, 0)
        if type(passed) is not bool:
            raise ValueError('Qualification requires exact boolean outcomes')
        observations.append(QualificationObservation(prompts[side], row.id, 0, passed))
        state = proof._advance(state, 0, side, passed == bool(side))


def original_trial(cells, start, roster, cohorts, seed, cap, arm):
    if arm == prior.CANDIDATE:
        return prior.run_trial(cells, start, roster, cohorts, seed, cap)
    return backup.run_trial(cells, start, roster, cohorts, seed, arm, cap)


def qualification_floor(cells, incumbent, nominee, cases):
    """Price the shortest proof with hindsight after the fixed precheck and nomination."""
    prefix = []
    for case in cases:
        prefix.append(bool(cells[incumbent][case][0]))
        if not prefix[-1]:
            break
    if incumbent == nominee:
        return len(prefix)
    gain = sum(cells[nominee][case][0] - cells[incumbent][case][0] for case in cases)
    low, high = -len(cases) + prefix.count(False), len(cases) - prefix.count(True)
    return len(prefix) + (1 - low if gain > 0 else high)


def run_trial(cells, start, roster, cohorts, seed, cap, arm, mode):
    validation_ids = {str(case) for case in cohorts[1]}
    paid_validation = {}
    original_qualify = math.certify_paired_qualification
    original_select = math.select
    original_native = math.gepa.optimize_by_paid_reads

    def select(incumbent, candidates, rows, observe, ledger, **settings):
        choice = original_select(incumbent, candidates, rows, observe, ledger, **settings)
        paid_validation.update({(name, case): result.passed for (name, case), result in ledger.items()
                                if case in validation_ids})
        return choice

    def native(incumbent, candidates, training, validation, read, count, **settings):
        def observe(prompt, case):
            result = read(prompt, case)
            if str(case) in validation_ids:
                paid_validation[prompt, str(case)] = result
            return result

        return original_native(incumbent, candidates, training, validation, observe, count, **settings)

    def qualify(incumbent, challenger, rows, read, *, seed):
        if incumbent == challenger:
            return original_qualify(incumbent, challenger, rows, read, seed=seed)
        # The existing precheck has already bought this exact prefix. Its callback reuses it here.
        prefix = {}
        for row in rows:
            prefix[row.id] = read(incumbent, row, 0)
            if not prefix[row.id]:
                break
        counts = []
        for name in (incumbent, challenger):
            replies = [passed for (prompt, _), passed in paid_validation.items() if prompt == name]
            counts.append((sum(replies), len(replies)))
        return qualify_with_prefix(incumbent, challenger, rows, read, prefix, counts, seed, mode)

    with (patch.object(math, 'select', select), patch.object(math.gepa, 'optimize_by_paid_reads', native),
          patch.object(math, 'certify_paired_qualification', qualify)):
        return original_trial(cells, start, roster, cohorts, seed, cap, arm)


def prepare():
    parent, data, _ = prior.prepare()
    raw = (backup.ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('Use the exact published conditional proof ordering')
    paths = (Path(__file__), Path(proof.__file__))
    plan = {**{key: parent[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                           'gepaVersion', 'bootstrapSeed', 'bootstrapDraws',
                                           'minimumLookupSavingPercent')},
            'protocol': 'recorded-paid-qualification-order-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': REFERENCE_SHA256,
            'sourceSha256': {str(path.resolve().relative_to(backup.ROOT)): sha256(path.read_bytes()).hexdigest()
                             for path in paths},
            'arms': ARMS, 'modes': MODES,
            'scope': 'Apply the same scheduling alternatives to CPO and both native controls. Credit the paid '
                     'precheck prefix from the start. Compare the original unread order and expected remaining '
                     'cost using paid validation and qualification replies. Preserve search cost, nominee, '
                     'deployment, and every held-out grade on each path. Price the shortest exact certificate '
                     'after the same precheck with hindsight as a diagnostic.'}
    return plan, data, reference['results']


def measure(cells, settings, group, width, plan, reference):
    size = len(next(iter(cells.values())))
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    totals = {mode: {arm: Counter() for arm in ARMS} for mode in MODES}
    traces = {mode: {arm: [] for arm in ARMS} for mode in MODES}
    vectors = {arm: [0] * size for arm in ARMS}
    differences = {mode: {arm: Counter() for arm in ARMS} for mode in ALTERNATIVES}
    floors = Counter()
    for seed in settings['seeds']:
        cohorts = math.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            available = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(available, len(available))[:width]
            args = (cells, start, roster, cohorts, seed, plan['searchCap'])
            for arm in ARMS:
                baseline, trace, grades = original_trial(*args, arm)
                floor = qualification_floor(cells, start, trace[2], cohorts[2])
                floors[arm] += floor
                totals['published'][arm].update(baseline)
                traces['published'][arm].append(trace)
                for case, passed in zip(cohorts[-1], grades, strict=True):
                    vectors[arm][case] += passed
                for mode in ALTERNATIVES:
                    revised, altered, observed = run_trial(*args, arm, mode)
                    if (trace[:4] != altered[:4] or grades != observed or
                            baseline['searchLookups'] != revised['searchLookups']):
                        raise ValueError('Qualification scheduling changed the search cost, nominee, or deployment')
                    saved = baseline['qualificationLookups'] - revised['qualificationLookups']
                    if not floor <= min(baseline['qualificationLookups'], revised['qualificationLookups']):
                        raise ValueError('A paid proof cannot use fewer replies than its hindsight floor')
                    if mode == CREDIT and saved < 0:
                        raise ValueError('Crediting already-paid replies in the same order cannot add a lookup')
                    differences[mode][arm].update(saved=max(0, saved), added=max(0, -saved),
                                                  cheaper=int(saved > 0), dearer=int(saved < 0))
                    totals[mode][arm].update(revised)
                    traces[mode][arm].append(altered)
    points = {mode: {arm: {**values, 'traceSha256': digest(traces[mode][arm])} for arm, values in arms.items()}
              for mode, arms in totals.items()}
    if any(points['published'][arm] != reference['totals'][arm] for arm in ARMS):
        raise ValueError('The original CPO and GEPA points must reproduce the published replay')
    matched = {**vectors, **{name: vectors[arm] for name, arm in prior.CONTROLS.items()}}
    ranges = math.paired_ranges(matched, prior.CANDIDATE, math.GEPA, plan)
    gates = {}
    for mode, arms in totals.items():
        matched = {**arms, **{name: arms[arm] for name, arm in prior.CONTROLS.items()}}
        gates[mode] = math.comparison(prior.CANDIDATE, matched, ranges, plan)
    return {'totals': points, 'comparison': gates, 'qualificationDifferences': differences,
            'qualificationLookupsFloorWithFixedPrecheckAndNominee': floors,
            'deploymentChecksPerArmAndMode': len(traces['published'][prior.CANDIDATE])}


def replay(plan, data, reference):
    results = {}
    for name, settings in plan['datasets'].items():
        cells = math.load_cells(name, data[name]['record'])
        results[name] = {f'{group}/{width}': measure(cells, settings, group, width, plan,
                                                    reference[name][f'{group}/{width}'])
                         for group in plan['incumbentGroups'] for width in plan['challengerCounts']}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, data, reference)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
