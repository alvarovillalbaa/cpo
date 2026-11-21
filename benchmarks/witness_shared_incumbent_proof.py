"""Test a preselected backup on the first proof's cases with paid incumbent reuse."""

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_shared_admission_credit as shared
from cpo._contract import digest


ROOT, RANKING, retry, FULL, CAP = shared.ROOT, shared.RANKING, shared.retry, shared.FULL, shared.CAP
PARENT = 'docs/witness-shared-admission-credit-results-v1.json'
PARENT_SHA256 = '86cf078f89311facad891e5e3ece7516c719baf79b7b4d18951238daf47828f3'
DISJOINT, FULL_CHARGE, REUSE = shared.BOTH, 'same-panel-full-charge', 'same-panel-incumbent-reuse'
DIRECT = shared.DIRECT_ONLY
METHODS = (FULL, DIRECT, DISJOINT, FULL_CHARGE, REUSE)


@dataclass(frozen=True)
class Settlement(shared.credit.Settlement):
    reused: int = 0
    rejected: bool = False
    capped: bool = False


class LookupLimit(Exception):
    pass


def prepare():
    parent, single, _, _, data = shared.prepare()
    raw = (ROOT / PARENT).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('Use the published schedule-order admission queue')
    plan = {key: parent[key] for key in ('credits', 'retryThresholds', 'fallbackValidationCap', 'pairedCaseDraws',
                                        'resamplingSeed', 'fit', 'gate')}
    plan.update(protocol='witness-shared-incumbent-proof-v1', parentPlanSha256=digest(parent),
                parentReceiptSha256=PARENT_SHA256, sourceSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                methods=METHODS, jointProofCap=CAP,
                rule='Freeze the first proof, direct offers, backup ranked from paid search, and queue eligibility. '
                'After exact rejection, use the first proof panels for the backup. Compare charging every '
                'scheduled lookup against reusing only the incumbent grades already bought on those cases. '
                'Keep the exact promotion and tie rules and the original per-episode and cohort reservations.')
    return plan, reference, single, data


def prove(start, rival, base, reserve, evaluate, grades, minimum, remaining, incumbent):
    paid, reused = 0, 0

    def grade(prompt, case):
        nonlocal paid, reused
        if prompt == start and case in incumbent:
            reused += 1
            return incumbent[case]
        if paid == remaining:
            raise LookupLimit
        paid += 1
        return evaluate(prompt, case)

    try:
        proof = retry.scalar_proof(start, rival, base, reserve, grade, grades, minimum,
                                   2 * (len(base) + len(reserve)))
    except LookupLimit:
        return start, paid, reused, 'undecided'
    return proof.prompt, paid, reused, proof.status


def collect(plan, phase, data):
    _, panels, _, _, _ = data
    tags = {id(panel['correctness']): (index, panel['subject']) for index, panel in enumerate(panels)}
    episodes = Counter()
    offers = {method: [] for method in METHODS[1:]}

    def outcomes(matrix, held, start, layouts, active, policy, nomination):
        panel, subject = tags[id(matrix)]
        key = (panel, episodes[panel])
        episodes[panel] += 1
        forbidden = set(held) | {case for layout in layouts for role in ('train', 'validation') for case in layout[role]}

        def defer(first, cap, incumbent, nominee, reserve, schedule, roster, local, grades, evaluate):
            def offer(method, quote, run):
                def settle():
                    prompt, paid, reused, status = run()
                    deltas = tuple(int(matrix[int(prompt)][case] == '1') - int(matrix[int(start)][case] == '1')
                                   for case in held)
                    return Settlement(paid, deltas, prompt != start, reused, status == 'rejected', status == 'undecided')

                offers[method].append(shared.Offer(key, subject, shared.RETRY, quote, settle))

            if cap == CAP:
                quote = shared.admissible(first, incumbent, nominee, reserve, schedule, roster, local, grades,
                                          plan['retryThresholds'][phase])
                if quote:
                    base = schedule[roster[nominee]]['qualify']
                    if forbidden.intersection((*base, *reserve)):
                        raise ValueError('A shared proof panel cannot include search or held-out cases')
                    rival = retry.ranked_rival(schedule, nominee, grades)
                    previous = {int(row.row_id): row.passed for row in first.observations if row.prompt == incumbent}

                    def disjoint():
                        result = retry.try_retry(first, cap, incumbent, nominee, reserve, schedule, roster,
                                                 local, grades, evaluate)
                        if not result.retry or result.lookups != len(first.observations) + result.retry_lookups:
                            raise ValueError('The disjoint retry disagreed with its reservation')
                        return result.prompt, result.retry_lookups, 0, result.status

                    offer(DISJOINT, quote, disjoint)
                    for method, cached in ((FULL_CHARGE, {}), (REUSE, previous)):
                        def shared_panel(cached=cached):
                            return prove(incumbent, rival, base, reserve, evaluate, grades,
                                         local['minimumQualificationGain'], quote, cached)

                        offer(method, quote, shared_panel)
            return retry.Decision(first.prompt, len(first.observations), first.status)

        with patch.object(retry, 'try_retry', defer):
            previous = shared.original_outcomes(matrix, held, start, layouts, active, policy, nomination)
        if nomination.original is None:
            direct = shared.credit.offer(matrix, held, start, layouts, active, nomination, key, subject)
            if direct is not None:
                direct_offer = shared.Offer(key, subject, shared.DIRECT, CAP, direct.settle)
                for queue in offers.values():
                    queue.append(direct_offer)
        return {retry.BASE: previous[retry.BASE], FULL: previous[FULL]}

    with patch.multiple(retry, METHODS=(retry.BASE, FULL), outcomes=outcomes):
        groups, traces = retry.measure(*data, plan['fallbackValidationCap'])
    return groups, traces, offers


def measure(plan, phase, data, reference, single):
    groups, traces, offers = collect(plan, phase, data)
    totals = {arm: sum((group['counts'][arm] for group in groups.values()), Counter()) for arm in (retry.BASE, FULL)}
    for arm, counts in totals.items():
        if any(counts[key] != single['totals'][arm].get(key, 0)
               for key in ('holdoutPasses', 'paidLookups', 'proofLookups', 'promotions')):
            raise ValueError('The original search and first-proof controls changed')
    if traces != reference['panelTraceSha256']:
        raise ValueError('The shared-credit control search and first-proof traces changed')
    votes = {subject: {'cases': {FULL: group['cases'][FULL]}, 'decisionsPerCase': group['decisionsPerCase']}
             for subject, group in groups.items()}
    limit = plan['credits'][phase]
    for method, candidates in offers.items():
        items = {offer.key: offer for offer in candidates}
        receipts, left = shared.allocate(candidates, shared.BOTH, limit, lambda item: item.settle())
        for group in votes.values():
            group['cases'][method] = group['cases'][FULL].copy()
        activity = Counter()
        for key, result in receipts.items():
            offer = items[key]
            scores = votes[offer.subject]['cases'][method]
            scores[:] = [value + change for value, change in zip(scores, result.changes, strict=True)]
            activity.update({f'{offer.kind}Attempts': 1, f'{offer.kind}Lookups': result.paid,
                             f'{offer.kind}Promotions': int(result.promoted)})
            if offer.kind == shared.RETRY:
                activity.update(reusedIncumbentLookups=result.reused, retryRejections=int(result.rejected),
                                retryCapped=int(result.capped))
        spent = limit - left
        if spent != sum(result.paid for result in receipts.values()):
            raise ValueError('The shared lookup ledger does not reconcile')
        totals[method] = {'holdoutPasses': sum(sum(group['cases'][method]) for group in votes.values()),
                          'paidLookups': totals[FULL]['paidLookups'] + spent, 'extraLookups': spent,
                          'newPromotions': sum(result.promoted for result in receipts.values()),
                          'remainingCredit': left, 'activity': activity, 'fundedTraceSha256': digest(tuple(receipts))}
    for control in (DIRECT, DISJOINT):
        if any(totals[control][key] != reference['totals'][control][key] for key in (
                'holdoutPasses', 'paidLookups', 'newPromotions', 'fundedTraceSha256')):
            raise ValueError(f'The published {control} queue changed')
    return votes, {'totals': totals, 'availableCredit': limit, 'panelTraceSha256': traces}


def execute(plan, reference, single, data):
    replayed = {phase: measure(plan, phase, data[phase], reference['cohorts'][phase], single['cohorts'][phase])
                for phase in RANKING.PHASES}
    bbh = RANKING.gap.paired.BBH
    with patch.object(shared, 'METHODS', METHODS):
        fit = {bbh: shared.select([replayed[bbh][1]]), 'mmlu': shared.select(
            [replayed[phase][1] for phase in RANKING.gap.paired.replay.PHASES])}
    for phase, (votes, report) in replayed.items():
        winner = fit['mmlu' if phase == bbh else bbh]
        paired = {}
        comparisons = ((winner, FULL), (FULL_CHARGE, DISJOINT), (REUSE, FULL_CHARGE), (REUSE, DISJOINT), (REUSE, DIRECT))
        for challenger, control in comparisons:
            with patch.object(RANKING.paired_bands, 'BASELINE', control):
                paired[f'{challenger} vs {control}'] = RANKING.paired_bands.paired_ranges(
                    votes, challenger, plan)['subjectsAndCases']
        report.update(selectedOutsideFamily=winner, paired=paired,
                      qualifies=paired[f'{winner} vs {FULL}']['interval95PercentagePoints'][0] > 0)
    cohorts = {phase: report for phase, (_, report) in replayed.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'training': fit, 'cohorts': cohorts,
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
