"""Test affordable proof caps while preserving the exact admission rule."""

import argparse
from collections import Counter, deque
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable
from unittest.mock import patch

from benchmarks import witness_adaptive_admission_credit as prior
from benchmarks.witness_admission_retry import outcomes as original_outcomes, try_retry
from cpo._contract import digest


shared = prior.shared
ROOT, RANKING, FULL, CAP, retry, credit = shared.ROOT, shared.RANKING, shared.FULL, shared.CAP, shared.retry, shared.credit
REFERENCE = 'docs/witness-adaptive-admission-credit-results-v1.json'
REFERENCE_SHA256 = '4e66bdfef24df01d16d44c350811e131d338f9cacea2ef51871f0519a393f8c0'
BASE_CAP, TAIL_CAP = 'base-cap', 'balance-cap'
METHODS = (FULL, shared.DIRECT_ONLY, prior.ADAPTIVE, BASE_CAP, TAIL_CAP)


@dataclass(frozen=True)
class ProofOffer:
    key: tuple[int, int]
    subject: str
    kind: str
    reserve: int
    base_cap: int
    minimum: int
    evaluate_at_cap: Callable[[int], credit.Settlement]

    def settle(self):
        return self.evaluate_at_cap(self.reserve)


def prepare():
    parent, _, unchanged, direct, funded, data = prior.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('Use the published adaptive queue and full proof offers')
    plan = {**parent, 'protocol': 'witness-short-admission-credit-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': METHODS, 'rule': 'Preserve the search, the paid candidate, and both independent panels. '
            'Use the adaptive order and either reserve at most a complete base proof on every offer or reserve '
            'at most the remaining balance. Open a proof only if its smallest possible promotion certificate '
            'can fit. A partial proof must certify exact promotion or retain the incumbent.',
            'gate': 'The policy selected by the other family needs a positive paired lower endpoint against '
                    'the full single proof on all cohorts within the existing credit.'}
    return plan, reference, unchanged, direct, funded, data


def collect(plan, phase, data):
    _, panels, _, _, _ = data
    tags = {id(panel['correctness']): (i, panel['subject']) for i, panel in enumerate(panels)}
    counts, offers = Counter(), []

    def outcomes(matrix, held, start, layouts, active, policy, nomination):
        panel, subject = tags[id(matrix)]
        key = (panel, counts[panel])
        counts[panel] += 1

        def deltas(prompt):
            return tuple(int(matrix[int(prompt)][case] == '1') - int(matrix[int(start)][case] == '1') for case in held)

        def defer(first, cap, incumbent, original, reserve, schedule, roster, local, grades, evaluate):
            if cap == CAP:
                quote = shared.admissible(first, incumbent, original, reserve, schedule, roster, local, grades,
                                          plan['retryThresholds'][phase])
                if quote:
                    rival = retry.ranked_rival(schedule, original, grades)
                    retired = set(schedule[roster[original]]['qualify'])
                    if first.used_reserve:
                        retired.update(reserve)
                    slot = retry.retry_panel(schedule, roster[rival], retired)
                    size = len(schedule[slot]['qualify'])

                    def bounded(limit):
                        decision = try_retry(first, len(first.observations) + limit, incumbent, original, reserve,
                                             schedule, roster, local, grades, evaluate)
                        return credit.Settlement(decision.retry_lookups, deltas(decision.prompt), decision.prompt != start)

                    offers.append(ProofOffer(key, subject, shared.RETRY, quote, 2 * size,
                                             size + local['minimumQualificationGain'], bounded))
            return retry.Decision(first.prompt, len(first.observations), first.status)

        with patch.object(retry, 'try_retry', defer):
            previous = original_outcomes(matrix, held, start, layouts, active, policy, nomination)
        if nomination.original is None:
            direct = credit.offer(matrix, held, start, layouts, active, nomination, key, subject)
            if direct is not None:
                enrolled = [prompt for layout in layouts for prompt in layout['alternatives']]
                winners, _ = credit.prior.prior.choose(start, enrolled, nomination.grades)
                size = next(len(layout['qualify']) for layout in layouts if winners[credit.SUPPORTED] in layout['alternatives'])
                qualify = credit.qualify_with_funded_retry

                def bounded(limit):
                    def qualify_under_cap(*args, **kwargs):
                        return qualify(*args, **{**kwargs, 'evaluation_limit': limit})

                    with patch.object(credit, 'qualify_with_funded_retry', qualify_under_cap):
                        return direct.settle()

                offers.append(ProofOffer(key, subject, shared.DIRECT, CAP, 2 * size,
                                         size + active['minimumQualificationGain'], bounded))
        return {retry.BASE: previous[retry.BASE], FULL: previous[FULL]}

    with patch.multiple(retry, METHODS=(retry.BASE, FULL), outcomes=outcomes):
        groups, traces = retry.measure(*data, plan['fallbackValidationCap'])
    if len({offer.key for offer in offers}) != len(offers):
        raise ValueError('An episode can offer at most one proof')
    return groups, traces, offers


def quote(offer, method, balance):
    return min(offer.reserve, offer.base_cap) if method == BASE_CAP else min(offer.reserve, balance)


def allocate(candidates, method, limit, settle):
    if method not in (BASE_CAP, TAIL_CAP):
        return prior.allocate(candidates, method, limit, settle)
    queues = {name: deque() for name in (shared.DIRECT, shared.RETRY)}
    for offer in candidates:
        queues[offer.kind].append(offer)
    attempts, promotions, spent = Counter(), Counter(), Counter()
    receipts, balance = {}, limit
    while True:
        for queue in queues.values():
            while queue and not queue[0].minimum <= quote(queue[0], method, balance) <= balance:
                queue.popleft()
        eligible = [kind for kind, queue in queues.items() if queue]
        if not eligible:
            return receipts, balance

        def order(kind):
            return attempts[kind], queues[kind][0].key

        if all(attempts[kind] for kind in eligible):
            selected = min(eligible, key=lambda kind: (-Fraction(promotions[kind] + 1, spent[kind] + CAP), *order(kind)))
        else:
            selected = min(eligible, key=order)
        offer = queues[selected].popleft()
        reserved = quote(offer, method, balance)
        balance -= reserved
        receipt = settle(offer) if reserved == offer.reserve else offer.evaluate_at_cap(reserved)
        if type(receipt.paid) is not int or not 0 <= receipt.paid <= reserved:
            raise ValueError('The proof exceeded its shortened reservation')
        receipts[offer.key] = receipt
        attempts[selected] += 1
        promotions[selected] += receipt.promoted
        spent[selected] += receipt.paid
        balance += reserved - receipt.paid


def execute(plan, reference, unchanged, direct, funded, data):
    with patch.multiple(shared, METHODS=METHODS, collect=collect, allocate=allocate):
        replayed = {phase: shared.measure(plan, phase, data[phase], unchanged['cohorts'][phase], direct['cohorts'][phase],
                                          funded['cohorts'][phase]) for phase in RANKING.PHASES}
        bbh = RANKING.gap.paired.BBH
        fit = {bbh: shared.select([replayed[bbh][1]]), 'mmlu': shared.select(
            [replayed[phase][1] for phase in RANKING.gap.paired.replay.PHASES])}
    cohorts = {}
    for phase, (votes, report) in replayed.items():
        old = reference['cohorts'][phase]
        if (any(report[key] != old[key] for key in ('availableCredit', 'offers', 'panelTraceSha256'))
                or any(report['totals'][arm] != old['totals'][arm] for arm in (FULL, shared.DIRECT_ONLY, prior.ADAPTIVE))):
            raise ValueError('The original control offers, costs, or traces changed')
        selected = fit['mmlu' if phase == bbh else bbh]
        comparisons = {}
        for method, control in ((selected, FULL), (BASE_CAP, prior.ADAPTIVE), (TAIL_CAP, prior.ADAPTIVE)):
            with patch.object(RANKING.paired_bands, 'BASELINE', control):
                comparisons[f'{method} vs {control}'] = RANKING.paired_bands.paired_ranges(votes, method, plan)['subjectsAndCases']
        report.update(selectedOutsideFamily=selected, paired=comparisons,
                      qualifies=comparisons[f'{selected} vs {FULL}']['interval95PercentagePoints'][0] > 0)
        cohorts[phase] = report
    return {'plan': plan, 'planSha256': digest(plan), 'training': fit, 'cohorts': cohorts,
            'newProviderRequests': 0, 'qualifies': all(row['qualifies'] for row in cohorts.values())}


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
