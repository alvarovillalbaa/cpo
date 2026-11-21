"""Share one saved-lookup budget between direct admissions and exact-rejection retries."""

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable
from unittest.mock import patch

from benchmarks import witness_admission_credit as credit, witness_retry_funding as funding
from benchmarks.witness_admission_retry import outcomes as original_outcomes, try_retry
from cpo._contract import digest


ROOT, RANKING, retry, FULL, CAP = credit.ROOT, credit.RANKING, credit.retry, credit.FULL, credit.CAP
DIRECT, RETRY = 'direct', 'retry'
DIRECT_ONLY, RETRY_ONLY = 'direct-only', 'retry-only'
DIRECT_FIRST, RETRY_FIRST, BOTH = 'direct-first', 'retry-first', 'schedule-order'
METHODS = (FULL, DIRECT_ONLY, RETRY_ONLY, DIRECT_FIRST, RETRY_FIRST, BOTH)
DIRECT_RECEIPT = 'docs/witness-admission-credit-results-v1.json'
DIRECT_SHA256 = '92f1b5e14e293a587cb0de3f383a314fee5a1b34c8f22669dc09ce5bd6cbef5d'
RETRY_RECEIPT = 'docs/witness-retry-funding-results-v1.json'
RETRY_SHA256 = 'aabc585765ed16cf0551a26a2f250cbf0ab4fdaff0be8ccd500bd5bcf9b8c2a4'


@dataclass(frozen=True)
class Offer:
    key: tuple[int, int]
    subject: str
    kind: str
    reserve: int
    settle: Callable[[], credit.Settlement]


def prepare():
    direct_plan, direct_control, data = credit.prepare()
    retry_plan, _, retry_data = funding.prepare()
    raw, raw_retry = (ROOT / DIRECT_RECEIPT).read_bytes(), (ROOT / RETRY_RECEIPT).read_bytes()
    direct, funded = json.loads(raw), json.loads(raw_retry)
    if (sha256(raw).hexdigest() != DIRECT_SHA256 or direct['planSha256'] != digest(direct_plan)
            or sha256(raw_retry).hexdigest() != RETRY_SHA256 or funded['planSha256'] != digest(retry_plan)
            or retry_data != data):
        raise ValueError('Use both published comparators on the same episodes')
    thresholds = {phase: funding.GATES[funded['cohorts'][phase]['selectedOutsideFamily']][0]
                  for phase in RANKING.PHASES}
    plan = {'protocol': 'witness-shared-admission-credit-v1', 'directPlanSha256': digest(direct_plan),
            'retryPlanSha256': digest(retry_plan), 'directReceiptSha256': DIRECT_SHA256,
            'retryReceiptSha256': RETRY_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'credits': direct_plan['credits'], 'retryThresholds': thresholds, 'methods': METHODS,
            'fallbackValidationCap': direct_plan['fallbackValidationCap'],
            'pairedCaseDraws': direct_plan['pairedCaseDraws'], 'resamplingSeed': direct_plan['resamplingSeed'],
            'rule': 'Freeze paid search and the initial proof. A stalled-search proof reserves 24 reads. A retry '
                    'after exact rejection reserves the remaining original per-episode allowance. Each episode '
                    'can offer only one. Test shared and single-route queues under the same fixed cohort credit.',
            'fit': 'Select on the other family by promotions and lower incremental spend.',
            'gate': 'Require a positive paired lower endpoint against full single proof within original seeded cost.'}
    return plan, direct_control, direct, funded, data


def admissible(first, start, nominee, reserve, layouts, roster, active, grades, threshold):
    remaining = CAP - len(first.observations)
    if first.status != 'rejected' or remaining < threshold:
        return 0
    rival = retry.ranked_rival(layouts, nominee, grades)
    if rival is None or rival == start:
        return 0
    retired = set(layouts[roster[nominee]]['qualify'])
    if first.used_reserve:
        retired.update(reserve)
    slot = retry.retry_panel(layouts, roster[rival], retired)
    return remaining if slot is not None and remaining >= len(layouts[slot]['qualify']) + active['minimumQualificationGain'] else 0


def collect(plan, phase, data):
    _, panels, _, _, _ = data
    tags = {id(panel['correctness']): (i, panel['subject']) for i, panel in enumerate(panels)}
    counts, candidates = Counter(), []

    def outcomes(matrix, held, start, layouts, active, policy, nomination):
        panel, subject = tags[id(matrix)]
        key = (panel, counts[panel])
        counts[panel] += 1

        def defer(first, cap, incumbent, original, reserve, schedule, roster, local, grades, evaluate):
            if cap == CAP:
                quote = admissible(first, incumbent, original, reserve, schedule, roster, local, grades,
                                   plan['retryThresholds'][phase])
                if quote:
                    def settle():
                        decision = try_retry(first, cap, incumbent, original, reserve, schedule, roster, local, grades, evaluate)
                        if not decision.retry:
                            raise ValueError('The deferred proof disagreed with eligibility')
                        deltas = tuple(int(matrix[int(decision.prompt)][case] == '1') - int(matrix[int(start)][case] == '1')
                                       for case in held)
                        return credit.Settlement(decision.retry_lookups, deltas, decision.prompt != start)

                    candidates.append(Offer(key, subject, RETRY, quote, settle))
            return retry.Decision(first.prompt, len(first.observations), first.status)

        with patch.object(retry, 'try_retry', defer):
            previous = original_outcomes(matrix, held, start, layouts, active, policy, nomination)
        if nomination.original is None:
            suggestion = credit.offer(matrix, held, start, layouts, active, nomination, key, subject)
            if suggestion is not None:
                candidates.append(Offer(key, subject, DIRECT, CAP, suggestion.settle))
        return {retry.BASE: previous[retry.BASE], FULL: previous[FULL]}

    with patch.multiple(retry, METHODS=(retry.BASE, FULL), outcomes=outcomes):
        groups, traces = retry.measure(*data, plan['fallbackValidationCap'])
    if len({item.key for item in candidates}) != len(candidates):
        raise ValueError('An episode can have at most one optional proof')
    return groups, traces, candidates


def allocate(candidates, method, limit, settle):
    if method in (DIRECT_ONLY, RETRY_ONLY):
        kind = DIRECT if method == DIRECT_ONLY else RETRY
        candidates = [item for item in candidates if item.kind == kind]
    elif method in (DIRECT_FIRST, RETRY_FIRST):
        first = DIRECT if method == DIRECT_FIRST else RETRY
        candidates = sorted(candidates, key=lambda item: (item.kind != first, item.key))
    receipts, left = {}, limit
    for item in candidates:
        if not 1 <= item.reserve <= CAP:
            raise ValueError('Each optional proof needs a positive reservation within the episode cap')
        if item.reserve > left:
            continue
        left -= item.reserve
        result = settle(item)
        if type(result.paid) is not int or not 0 <= result.paid <= item.reserve:
            raise ValueError('A proof exceeded the reservation charged before dispatch')
        receipts[item.key] = result
        left += item.reserve - result.paid
    return receipts, left


def measure(plan, phase, data, unchanged, old_direct, old_retry):
    groups, traces, candidates = collect(plan, phase, data)
    totals = {arm: sum((group['counts'][arm] for group in groups.values()), Counter()) for arm in (retry.BASE, FULL)}
    for arm, counts in totals.items():
        if any(counts[key] != unchanged['totals'][arm].get(key, 0)
               for key in ('holdoutPasses', 'paidLookups', 'proofLookups', 'promotions')):
            raise ValueError('The paid search or original qualification changed')
    items = {item.key: item for item in candidates}
    lookup_credit, cache = plan['credits'][phase], {}

    def settle(item):
        if item.key not in cache:
            cache[item.key] = item.settle()
        return cache[item.key]

    votes = {subject: {'cases': {FULL: group['cases'][FULL]}, 'decisionsPerCase': group['decisionsPerCase']}
             for subject, group in groups.items()}
    for method in METHODS[1:]:
        receipts, left = allocate(candidates, method, lookup_credit, settle)
        for group in votes.values():
            group['cases'][method] = group['cases'][FULL].copy()
        activity = Counter()
        for key, receipt in receipts.items():
            item = items[key]
            scores = votes[item.subject]['cases'][method]
            scores[:] = [value + change for value, change in zip(scores, receipt.changes, strict=True)]
            activity.update({f'{item.kind}Attempts': 1, f'{item.kind}Lookups': receipt.paid,
                             f'{item.kind}Promotions': int(receipt.promoted)})
        spent = lookup_credit - left
        if spent != sum(receipt.paid for receipt in receipts.values()) or spent > lookup_credit:
            raise ValueError('The shared lookup ledger does not reconcile')
        totals[method] = {'holdoutPasses': sum(sum(group['cases'][method]) for group in votes.values()),
                          'paidLookups': totals[FULL]['paidLookups'] + spent, 'extraLookups': spent,
                          'newPromotions': sum(receipt.promoted for receipt in receipts.values()),
                          'remainingCredit': left, 'activity': activity, 'fundedTraceSha256': digest(tuple(receipts))}
    if any(totals[DIRECT_ONLY][key] != old_direct['totals'][credit.SCHEDULE][key]
           for key in ('holdoutPasses', 'paidLookups', 'extraLookups', 'newPromotions')):
        raise ValueError('The standalone budgeted direct queue changed')
    retry_offers = [settle(item) for item in candidates if item.kind == RETRY]
    expected = old_retry['totals'][old_retry['selectedOutsideFamily']]
    if (len(retry_offers), sum(item.paid for item in retry_offers), sum(sum(item.changes) for item in retry_offers),
            sum(item.promoted for item in retry_offers)) != (
                expected['retries'], expected['retryLookups'], expected['holdoutPasses'] - totals[FULL]['holdoutPasses'],
                expected['retryPromotions']):
        raise ValueError('The deferred retry queue did not reproduce the original unbudgeted arm')
    return votes, {'totals': totals, 'availableCredit': lookup_credit, 'offers': Counter(item.kind for item in candidates),
                   'panelTraceSha256': traces}


def select(reports):
    return min(METHODS, key=lambda arm: (-sum(report['totals'][arm].get('newPromotions', 0) for report in reports),
                                        sum(report['totals'][arm].get('extraLookups', 0) for report in reports),
                                        METHODS.index(arm)))


def execute(plan, standalone, direct, funded, data):
    replayed = {phase: measure(plan, phase, data[phase], standalone['cohorts'][phase], direct['cohorts'][phase],
                               funded['cohorts'][phase]) for phase in RANKING.PHASES}
    bbh = RANKING.gap.paired.BBH
    fit = {bbh: select([replayed[bbh][1]]), 'mmlu': select(
        [replayed[phase][1] for phase in RANKING.gap.paired.replay.PHASES])}
    for phase, (votes, report) in replayed.items():
        winner = fit['mmlu' if phase == bbh else bbh]
        with patch.object(RANKING.paired_bands, 'BASELINE', FULL):
            paired = RANKING.paired_bands.paired_ranges(votes, winner, plan)['subjectsAndCases']
        report.update(selectedOutsideFamily=winner, pairedSelectedVsSingle=paired,
                      qualifies=paired['interval95PercentagePoints'][0] > 0)
    cohorts = {phase: report for phase, (_, report) in replayed.items()}
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
