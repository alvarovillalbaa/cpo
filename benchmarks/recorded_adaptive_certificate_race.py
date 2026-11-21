"""Switch validation challengers using estimated cost to a strict certificate."""

import argparse
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_expected_training_order as prior
from cpo._contract import digest
from cpo.expected_qualification import _pass_rate


transfer, math, core = prior.math_transfer, prior.math, prior.core
REFERENCE = 'docs/recorded-expected-training-order-results-v1.json'
REFERENCE_SHA256 = '49a761d5acc0b549855e9a51b8ee47243ab4e9ec2767a7875e65b0adc3e91329'
UNIT = 'adaptive-certificate-by-lookups'
PRICED = 'adaptive-certificate-by-price'
MODES = (UNIT, PRICED)


@lru_cache(maxsize=32_768)
def prospects(pending, needed):
    """Return modeled certificate probability and expected reads to settlement."""
    if needed > len(pending):
        return 0, 0
    if needed <= 0 and not any(protected for protected, _ in pending):
        return 1, 0
    (protected, rate), *tail = pending
    tail = tuple(tail)
    chance = Fraction(rate, 4)
    success, good_cost = prospects(tail, needed - 1)
    failure, bad_cost = (0, 0) if protected else prospects(tail, needed)
    return chance * success + (1 - chance) * failure, 1 + chance * good_cost + (1 - chance) * bad_cost


def race(incumbent, roster, rows, training, evaluate, ledger, *, cap, audit):
    """Return the first exact certificate from a race over affordable candidates."""
    if not roster or not training or not rows or len(rows) > cap:
        return None
    case_hits, case_reads = Counter(), Counter()
    prompt_hits, prompt_reads, prompt_total_price = Counter(), Counter(), Counter()

    def buy(prompt, row):
        grade, price = evaluate(prompt, row)
        if type(grade) is not bool or type(price) is not int or price < 0:
            raise ValueError('The race requires exact boolean grades and nonnegative integer prices')
        case_hits[row.id] += grade
        case_reads[row.id] += 1
        prompt_hits[prompt] += grade
        prompt_reads[prompt] += 1
        prompt_total_price[prompt] += price
        return grade

    base = {row.id: buy(incumbent, row) for row in rows}
    target = sum(base.values()) + 1
    if target > len(rows):
        return None
    protected = {row.id for row in rows if row.critical and base[row.id]}
    active = dict.fromkeys(roster)
    previous = None
    while active:
        row_order = sorted(rows, key=lambda row: (row.id not in protected,
                                                 Fraction(case_hits[row.id] + 1, case_reads[row.id] + 2)))
        choices = {}
        for prompt in tuple(active):
            unread = [row for row in row_order if (prompt, row.id) not in ledger]
            remaining_training = sum((name, row.id) not in ledger for name in (incumbent, prompt) for row in training)
            needed = target - prompt_hits[prompt]
            if needed > len(unread) or len(ledger) + len(unread) + remaining_training > cap:
                del active[prompt]
                continue
            if needed <= 0 and not any(row.id in protected for row in unread):
                return prompt, prompt_reads[prompt]

            schedule = tuple((row.id in protected, _pass_rate(case_hits[row.id] + prompt_hits[prompt],
                                                             case_reads[row.id] + prompt_reads[prompt]))
                             for row in unread)
            probability, expected_reads = prospects(schedule, needed)
            observed_prompt = prompt if prompt_reads[prompt] else incumbent
            price = max(1, Fraction(prompt_total_price[observed_prompt], prompt_reads[observed_prompt]))
            choices[prompt] = expected_reads * price / probability, unread[0]
        if not choices:
            return None
        chosen = min(choices, key=lambda prompt: choices[prompt][0])
        next_row = choices[chosen][1]
        audit.update(challengerReads=1, challengerSwitches=int(previous is not None and chosen != previous))
        previous = chosen
        if not buy(chosen, next_row) and next_row.id in protected:
            del active[chosen]
    return None


def run_trial(cells, start, roster, cohorts, seed, cap, mode):
    audit = Counter()

    def certificates(incumbent, candidates, rows, training, observe, ledger, cap):
        def evaluate(prompt, row):
            grade = observe(prompt, row).passed
            charge = cells[prompt][int(row.id)][1] if mode == PRICED else None
            return grade, 1 if charge is None else charge

        result = race(incumbent, candidates, rows, training, evaluate, ledger, cap=cap, audit=audit)
        if result is not None:
            yield result

    with patch.object(core, 'certificates', certificates):
        point, trace, grades = core.trial(cells, start, roster, cohorts, seed, cap, core.FIRST)
    if (point['searchLookups'] > cap or point['qualificationLookups'] > 2 * len(cohorts[2])
            or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']):
        raise ValueError('The adaptive race must reserve and charge both proof roles')
    return {**point, **audit}, trace, grades


def prepare():
    inherited, data, controls, _ = prior.prepare()
    reference = transfer.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, inherited)
    plan = {**{key: inherited[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                               'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-adaptive-certificate-race-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': REFERENCE_SHA256, 'methods': (*MODES, core.FIRST, prior.ORDERED),
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Keep the first-certificate exact validation, strict training, and independent '
                     'qualification gates. After each purchased validation reply, rank the unresolved '
                     'roster by modeled cost to settlement divided by probability of a certificate. '
                     'Estimate rates from paid candidate and peer case outcomes, in quarter bins. Compare '
                     'unit prices to paid per-prompt mean prices. Keep the same roster, splits, funding '
                     'reserve and matched GEPA frontiers.'}
    return plan, data, controls, reference['results']


def measure(plan, cells, settings, group, width, controls, reference, mode):
    changes = Counter()
    original = core.trial

    def trial(*args):
        before, old, old_grades = original(*args[:-1], core.FIRST)
        point, trace, grades = run_trial(*args[:-1], mode)
        delta = sum(grades) - sum(old_grades)
        if trace[3] == old[3] and grades != old_grades:
            raise ValueError('Identical deployments must reproduce all held-out grades')
        changes.update(trials=1, changedNominations=int(trace[2] != old[2]), changedDeployments=int(trace[3] != old[3]),
                       holdoutPassDelta=delta, grossPassGain=max(delta, 0), grossPassLoss=max(-delta, 0),
                       lookupDelta=point['paidLookups'] - before['paidLookups'])
        if transfer.HISTORICAL in point:
            changes['historicalCostDeltaNanodollars'] += point[transfer.HISTORICAL] - before[transfer.HISTORICAL]
        return point, trace, grades

    def existing(*args):
        return prior.run_trial(*args[:-1]) if args[-1] == prior.ORDERED else original(*args)

    anchors = {**controls, 'totals': {**controls['totals'], prior.ORDERED: reference['anchors'][prior.ORDERED]}}
    with (patch.object(transfer, 'PRIMARY', mode), patch.object(transfer, 'METHODS', (mode, core.FIRST, prior.ORDERED)),
          patch.object(core, 'trial', existing), patch.object(transfer.parity.shortlist, 'trial', trial)):
        result = transfer.measure(plan, cells, settings, group, width, anchors)
    if (any(point != reference['totals'][label] for label, point in result['totals'].items() if label != mode)
            or any(value[core.FIRST] != reference['comparisons'][key][core.FIRST]
                   for key, value in result['comparisons'].items())
            or changes['holdoutPassDelta'] != result['totals'][mode]['holdoutPasses']
            - reference['totals'][core.FIRST]['holdoutPasses']):
        raise ValueError('Original certificate decisions, comparisons and native frontiers must reproduce')
    return {'totals': result['anchors'][mode], 'pairedChangesVsFirstCertificate': changes,
            'comparisons': {key: value[mode] for key, value in result['comparisons'].items()}}


def replay(plan, data, controls, reference):
    results = {}
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        results[dataset] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                name = f'{group}/{width}'
                results[dataset][name] = {mode: measure(plan, cells, settings, group, width, controls[dataset][name],
                                                          reference[dataset][name], mode) for mode in MODES}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
