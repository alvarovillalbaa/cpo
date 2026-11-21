"""Allocate a fixed proof budget to stalled searches before seeing proof replies."""

import argparse
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from math import comb
from pathlib import Path
from typing import Callable
from unittest.mock import patch

from benchmarks import witness_no_nominee_miss as prior
from benchmarks.witness_admission_retry import outcomes as retry_outcomes
from benchmarks.witness_fallback_proof_reserve import fund
from cpo import Row
from cpo._contract import digest
from cpo.halving.funded_admission import qualify_with_funded_retry
from cpo.rotating_witness.episode import WitnessCycle


ROOT, RANKING, retry, FULL, CAP = prior.ROOT, prior.RANKING, prior.retry, prior.FULL, prior.CAP
REFERENCE = 'docs/witness-no-nominee-miss-results-v1.json'
REFERENCE_SHA256 = 'a788a1412822c3fd381807905afe578f781b855955a501dc8421b973d9367743'
SUPPORTED = prior.prior.RATE
SCHEDULE, MARGIN, CERTIFICATE = 'schedule-order', 'validation-margin', 'certificate-forecast'
ORDERS = (SCHEDULE, MARGIN, CERTIFICATE)
METHODS = (FULL, *ORDERS)


@dataclass(frozen=True)
class Settlement:
    paid: int
    changes: tuple[int, ...]
    promoted: bool


@dataclass(frozen=True)
class Opportunity:
    key: tuple[int, int]
    subject: str
    margin: Fraction
    probability: Fraction
    settle: Callable[[], Settlement]


def prepare():
    parent, _, data = prior.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('Use the published halted-search comparison')
    credits = {phase: row['totals'][retry.BASE]['paidLookups'] - row['totals'][FULL]['paidLookups']
               for phase, row in reference['cohorts'].items()}
    plan = {'protocol': 'witness-admission-credit-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'credits': credits, 'proofReservation': CAP, 'fallbackValidationCap': parent['fallbackValidationCap'],
            'pairedCaseDraws': parent['pairedCaseDraws'], 'resamplingSeed': parent['resamplingSeed'], 'orders': ORDERS,
            'rule': 'Preserve the paid search and every original nominee. Collect the published supported-rate '
                    'candidate at each no-nominee stop. Order the batch before seeing any new proof reply. '
                    'Reserve the full proof allowance before dispatch and return unused reads at settlement.',
            'forecast': 'Rank either by smoothed validation margin or by the independent Bernoulli probability of '
                        'certifying the base gain or a gain on the reserve after a base tie. Use only paid rates.',
            'credit': 'Set the batch budget in advance from the sealed historical seeded-to-expected proof savings.',
            'fit': 'Select by exact promotion count on the other family, then lower realized incremental cost.',
            'gate': 'Require a positive paired lower endpoint against the full single proof on each cohort.'}
    return plan, reference, data


def pass_rate(evidence, prompt):
    observed = [passed for (key, _), passed in evidence.items() if key == prompt]
    return Fraction(sum(observed) + 1, len(observed) + 2)


def forecast(size, reserve, minimum, old, new):
    def distribution(rows, rate):
        return [comb(rows, count) * rate**count * (1 - rate)**(rows - count) for count in range(rows + 1)]

    def gain(rows, threshold):
        incumbent, candidate = distribution(rows, old), distribution(rows, new)
        return sum((a * b for i, a in enumerate(incumbent)
                    for j, b in enumerate(candidate) if j - i >= threshold), Fraction())

    tie = sum(a * b for a, b in zip(distribution(size, old), distribution(size, new), strict=True))
    return gain(size, minimum) + tie * gain(reserve, minimum)


def offer(matrix, held, start, layouts, active, nomination, key, subject):
    enrolled = [prompt for layout in layouts for prompt in layout['alternatives']]
    selected, _ = prior.prior.choose(start, enrolled, nomination.grades)
    candidate = selected[SUPPORTED]
    if candidate is None:
        return None
    slot = next(i for i, layout in enumerate(layouts) if candidate in layout['alternatives'])
    old, new = (pass_rate(nomination.grades, prompt) for prompt in (start, candidate))
    reserve = min(active['maximumExtensionRows'], sum(len(layout['qualify']) for layout in layouts[:slot]))
    probability = forecast(len(layouts[slot]['qualify']), reserve, active['minimumQualificationGain'], old, new)

    def settle():
        cycles = tuple(WitnessCycle(tuple(layout['alternatives']), tuple(Row(str(i), 'task') for i in layout['validation']),
                                    tuple(Row(str(i), 'task') for i in layout['qualify']), layout['seed']) for layout in layouts)
        ledger = {(prompt, str(case)): passed for (prompt, case), passed in nomination.grades.items()}
        held_set = set(held)

        def grade(prompt, row, _repeat):
            case = int(row.id)
            if case in held_set:
                raise ValueError('An independent proof cannot read the held-out panel')
            return matrix[int(prompt)][case] == '1'

        proof = qualify_with_funded_retry(
            start, candidate, cycles, grade, ledger, minimum_retry_lookups=CAP + 1, evaluation_limit=CAP,
            minimum_gain=active['minimumQualificationGain'], maximum_extension_rows=active['maximumExtensionRows'])
        changes = tuple(int(matrix[int(proof.prompt)][case] == '1') - int(matrix[int(start)][case] == '1') for case in held)
        return Settlement(proof.qualification_evaluations, changes, proof.prompt != start)

    return Opportunity(key, subject, new - old, probability, settle)


def collect(plan, data):
    _, panels, _, _, _ = data
    tags = {id(panel['correctness']): (i, panel['subject']) for i, panel in enumerate(panels)}
    serial = Counter()
    candidates = []

    def outcomes(matrix, held, start, layouts, active, policy, nomination):
        previous = retry_outcomes(matrix, held, start, layouts, active, policy, nomination)
        panel, subject = tags[id(matrix)]
        key = (panel, serial[panel])
        serial[panel] += 1
        if nomination.original is None:
            candidate = offer(matrix, held, start, layouts, active, nomination, key, subject)
            if candidate is not None:
                candidates.append(candidate)
        return {retry.BASE: previous[retry.BASE], FULL: previous[FULL]}

    with patch.multiple(retry, METHODS=(retry.BASE, FULL), outcomes=outcomes):
        groups, traces = retry.measure(*data, plan['fallbackValidationCap'])
    return groups, traces, candidates


def allocate(candidates, method, credit, settle):
    if method == MARGIN:
        candidates = sorted(candidates, key=lambda item: (-item.margin, item.key))
    elif method == CERTIFICATE:
        candidates = sorted(candidates, key=lambda item: (-item.probability, item.key))

    def charged(candidate, _search_cap):
        result = settle(candidate)
        return result.paid, result

    receipts, remaining = fund(candidates, credit, CAP, 0, charged)
    return {key: result for key, _, _, result in receipts}, remaining


def measure(plan, phase, data, reference):
    groups, traces, candidates = collect(plan, data)
    totals = {arm: sum((group['counts'][arm] for group in groups.values()), Counter()) for arm in (retry.BASE, FULL)}
    for arm, counts in totals.items():
        if any(counts[key] != reference['totals'][arm].get(key, 0) for key in ('holdoutPasses', 'paidLookups', 'promotions')):
            raise ValueError('The original full-proof or seeded total changed')
    if len(candidates) != reference['activity']['supportedRateNominees']:
        raise ValueError('The supported-rate queue changed')
    labels = {item.key: item.subject for item in candidates}
    credit, cache = plan['credits'][phase], {}

    def settle(candidate):
        if candidate.key not in cache:
            cache[candidate.key] = candidate.settle()
        return cache[candidate.key]

    votes = {subject: {'cases': {FULL: group['cases'][FULL]}, 'decisionsPerCase': group['decisionsPerCase']}
             for subject, group in groups.items()}
    for method in ORDERS:
        receipts, left = allocate(candidates, method, credit, settle)
        for group in votes.values():
            group['cases'][method] = group['cases'][FULL].copy()
        for key, receipt in receipts.items():
            scores = votes[labels[key]]['cases'][method]
            scores[:] = [value + change for value, change in zip(scores, receipt.changes, strict=True)]
        spent = credit - left
        if spent != sum(receipt.paid for receipt in receipts.values()) or spent > credit:
            raise ValueError('The exact proof receipts must reconcile to the credit ledger')
        totals[method] = {'holdoutPasses': sum(sum(group['cases'][method]) for group in votes.values()),
                          'paidLookups': totals[FULL]['paidLookups'] + spent, 'extraLookups': spent,
                          'proofs': len(receipts), 'newPromotions': sum(receipt.promoted for receipt in receipts.values()),
                          'remainingCredit': left, 'fundedTraceSha256': digest(tuple(receipts))}

    unbounded = [settle(candidate) for candidate in candidates]
    supported = reference['totals'][SUPPORTED]
    if (totals[FULL]['paidLookups'] + sum(item.paid for item in unbounded),
            totals[FULL]['holdoutPasses'] + sum(sum(item.changes) for item in unbounded),
            totals[FULL]['promotions'] + sum(item.promoted for item in unbounded)) != (
                supported['paidLookups'], supported['holdoutPasses'], supported['promotions']):
        raise ValueError('The queue did not reproduce the published supported-rate control')
    return votes, {'totals': totals, 'credit': credit, 'eligible': len(candidates), 'panelTraceSha256': traces}


def select(reports):
    return min(METHODS, key=lambda arm: (-sum(report['totals'][arm].get('newPromotions', 0) for report in reports),
                                        sum(report['totals'][arm].get('extraLookups', 0) for report in reports),
                                        METHODS.index(arm)))


def execute(plan, reference, data):
    replayed = {phase: measure(plan, phase, data[phase], reference['cohorts'][phase]) for phase in RANKING.PHASES}
    bbh = RANKING.gap.paired.BBH
    trained = {bbh: select([replayed[bbh][1]]), 'mmlu': select(
        [replayed[phase][1] for phase in RANKING.gap.paired.replay.PHASES])}
    for phase, (votes, report) in replayed.items():
        winner = trained['mmlu' if phase == bbh else bbh]
        with patch.object(RANKING.paired_bands, 'BASELINE', FULL):
            paired = RANKING.paired_bands.paired_ranges(votes, winner, plan)['subjectsAndCases']
        report.update(selectedOutsideFamily=winner, pairedSelectedVsSingle=paired,
                      qualifies=paired['interval95PercentagePoints'][0] > 0)
    cohorts = {phase: report for phase, (_, report) in replayed.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'training': trained, 'cohorts': cohorts,
            'newProviderRequests': 0, 'qualifies': all(report['qualifies'] for report in cohorts.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    report = execute(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
