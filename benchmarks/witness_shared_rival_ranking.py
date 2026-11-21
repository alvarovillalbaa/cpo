"""Find the room for a better already-paid backup on the shared proof panel."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_shared_incumbent_proof as parent
from cpo._contract import digest


ROOT, RANKING, retry, FULL, CAP = parent.ROOT, parent.RANKING, parent.retry, parent.FULL, parent.CAP
shared = parent.shared
REFERENCE = 'docs/witness-shared-incumbent-proof-results-v1.json'
REFERENCE_SHA256 = 'a429dae06c2cd8a7602b34562a62321d7852df51f85fa27d8cf5c57fd208e6e8'
DIRECT, RATE = parent.DIRECT, parent.REUSE
PAIRED, ADJUSTED = 'paired-margin', 'case-adjusted'
METHODS = (FULL, DIRECT, RATE, PAIRED, ADJUSTED)


def prepare():
    previous, _, _, data = parent.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(previous):
        raise ValueError('Use the published shared-panel retry comparison')
    plan = {key: previous[key] for key in ('credits', 'retryThresholds', 'fallbackValidationCap', 'pairedCaseDraws',
                                          'resamplingSeed', 'fit', 'gate', 'jointProofCap')}
    plan.update(protocol='witness-shared-rival-ranking-v1', parentPlanSha256=digest(previous),
                parentReceiptSha256=REFERENCE_SHA256, sourceSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                methods=METHODS,
                rule='Keep the generated proposals, paid search, first proof, eligible retry slots, panels, and '
                'reserves fixed. Rank already-paid backups by smoothed pass rate, paired validation margin, or '
                'case-adjusted validation score. Run the same single shared-panel backup proof.',
                hindsight='Price the complete paid backup roster on the same panel and cap. Bound holdout gains '
                'at the funded retry slots and their realized costs, and across all eligible slots under the same '
                'chronological reserve and cohort budget with the funded direct offers fixed.')
    return plan, reference, data


def choices(start, rejected, roster, grades, reference):
    paid = {prompt for prompt, _ in grades}
    pool = tuple(prompt for prompt in roster if prompt not in (start, rejected) and prompt in paid)
    if reference not in pool:
        raise ValueError('The reference backup must be a paid rival of the rejected candidate')
    ranking = RANKING.rank(RANKING.Nomination(reference, 0, grades), start, pool)
    return pool, {RATE: reference, PAIRED: ranking[PAIRED], ADJUSTED: ranking[ADJUSTED]}


def collect(plan, phase, data):
    _, panels, _, _, _ = data
    tags = {id(panel['correctness']): (index, panel['subject']) for index, panel in enumerate(panels)}
    episodes, direct, backups, menus = Counter(), {}, {}, {}

    def outcomes(matrix, held, start, layouts, active, policy, nomination):
        panel, subject = tags[id(matrix)]
        key = panel, episodes[panel]
        episodes[panel] += 1

        def defer(first, cap, incumbent, nominee, reserve, schedule, roster, local, grades, evaluate):
            if cap != CAP:
                return retry.Decision(first.prompt, len(first.observations), first.status)
            quote = shared.admissible(first, incumbent, nominee, reserve, schedule, roster, local, grades,
                                      plan['retryThresholds'][phase])
            if quote:
                base = schedule[roster[nominee]]['qualify']
                forbidden = set(held) | {case for layout in layouts for role in ('train', 'validation') for case in layout[role]}
                if forbidden.intersection((*base, *reserve)):
                    raise ValueError('The backup left its independent proof cases')
                rival = retry.ranked_rival(schedule, nominee, grades)
                pool, selected = choices(incumbent, nominee, roster, grades, rival)
                cached = {int(row.row_id): row.passed for row in first.observations if row.prompt == incumbent}
                settled = {}

                def prove(candidate):
                    if candidate not in settled:
                        prompt, paid, reused, status = parent.prove(incumbent, candidate, base, reserve, evaluate,
                                                                   grades, local['minimumQualificationGain'], quote, cached)
                        deltas = tuple(int(matrix[int(prompt)][case] == '1') - int(matrix[int(incumbent)][case] == '1')
                                       for case in held)
                        settled[candidate] = parent.Settlement(paid, deltas, prompt != incumbent, reused,
                                                               status == 'rejected', status == 'undecided')
                    return settled[candidate]

                menus[key] = (pool, selected, prove)
                backups[key] = {method: shared.Offer(key, subject, shared.RETRY, quote,
                                                    lambda prompt=prompt: prove(prompt))
                                for method, prompt in selected.items()}
            return retry.Decision(first.prompt, len(first.observations), first.status)

        with patch.object(retry, 'try_retry', defer):
            original = shared.original_outcomes(matrix, held, start, layouts, active, policy, nomination)
        if nomination.original is None:
            suggestion = shared.credit.offer(matrix, held, start, layouts, active, nomination, key, subject)
            if suggestion is not None:
                direct[key] = shared.Offer(key, subject, shared.DIRECT, CAP, suggestion.settle)
        return {retry.BASE: original[retry.BASE], FULL: original[FULL]}

    with patch.multiple(retry, METHODS=(retry.BASE, FULL), outcomes=outcomes):
        groups, traces = retry.measure(*data, plan['fallbackValidationCap'])
    if direct.keys() & backups.keys() or backups.keys() != menus.keys():
        raise ValueError('Each opportunity must be either direct or one matched retry')
    return groups, traces, direct, backups, menus


def ceiling(events, limit):
    """Price optional positive retries around fixed direct receipts in chronological order."""
    scores = {0: 0}
    for quote, fixed, options in events:
        next_scores = {} if fixed else scores.copy()
        for spent, score in scores.items():
            if limit - spent < quote:
                continue
            for paid, gain in options:
                if not 0 <= paid <= quote:
                    raise ValueError('The hindsight choice exceeds its available reservation')
                cost = spent + paid
                next_scores[cost] = max(next_scores.get(cost, score + gain), score + gain)
        scores = next_scores
    if not scores:
        raise ValueError('The original funded direct receipts must fit the allowance')
    return max(((gain, spent) for spent, gain in scores.items()), key=lambda row: (row[0], -row[1]))


def diagnose(keys, direct, backups, menus, baseline, limit):
    counts, events = Counter(), []
    for key in keys:
        if key in direct:
            if key in baseline:
                events.append((direct[key].reserve, True, [(baseline[key].paid, 0)]))
            continue
        pool, selected, prove = menus[key]
        options = [prove(candidate) for candidate in pool]
        helpful = [item for item in options if item.promoted and sum(item.changes) > 0]
        original = prove(selected[RATE])
        counts.update(eligibleRetries=1, eligibleRivalCount=len(pool), multiplePaidRivals=int(len(pool) > 1),
                      aRivalPromotes=int(any(item.promoted for item in options)),
                      aRivalImproves=int(bool(helpful)), referencePromotes=int(original.promoted),
                      referenceImproves=int(sum(original.changes) > 0))
        events.append((backups[key][RATE].reserve, False, [(item.paid, sum(item.changes)) for item in helpful]))
        if key in baseline:
            matched = [sum(item.changes) for item in helpful if item.paid <= original.paid]
            baseline_gain = sum(original.changes)
            counts.update(fundedRetries=1, fundedRivalPromotes=int(any(item.promoted for item in options)),
                          fundedRivalImproves=int(bool(helpful)), fundedRivalImprovesAtSameCost=int(bool(matched)),
                          bestSameCostPassGain=max([0, *matched]) - baseline_gain, fundedReferencePassGain=baseline_gain)
    gain, spend = ceiling(events, limit)
    return {**counts, 'bestQueueRetryPassGain': gain, 'bestQueueExtraLookups': spend,
            'bestQueuePassGainVsReference': gain - counts['fundedReferencePassGain']}


def measure(plan, phase, data, reference):
    groups, traces, direct, backups, menus = collect(plan, phase, data)
    totals = {arm: sum((group['counts'][arm] for group in groups.values()), Counter()) for arm in (retry.BASE, FULL)}
    if traces != reference['panelTraceSha256'] or any(
            totals[arm][key] != reference['totals'][arm].get(key, 0)
            for arm in totals for key in ('holdoutPasses', 'paidLookups', 'proofLookups', 'promotions')):
        raise ValueError('The published search and first-proof controls changed')
    votes = {subject: {'cases': {FULL: group['cases'][FULL]}, 'decisionsPerCase': group['decisionsPerCase']}
             for subject, group in groups.items()}
    keys, limit = sorted(direct.keys() | backups.keys()), plan['credits'][phase]
    baseline = {}
    for method in METHODS[1:]:
        items = {key: direct[key] if key in direct else backups[key][method]
                 for key in keys if method != DIRECT or key in direct}
        receipts, left = shared.allocate(list(items.values()), shared.BOTH, limit, lambda offer: offer.settle())
        for group in votes.values():
            group['cases'][method] = group['cases'][FULL].copy()
        for key, item in receipts.items():
            scores = votes[items[key].subject]['cases'][method]
            scores[:] = [value + delta for value, delta in zip(scores, item.changes, strict=True)]
        funded = [key for key in receipts if key in backups]
        spent = limit - left
        totals[method] = {'holdoutPasses': sum(sum(group['cases'][method]) for group in votes.values()),
                          'paidLookups': totals[FULL]['paidLookups'] + spent, 'extraLookups': spent,
                          'newPromotions': sum(item.promoted for item in receipts.values()),
                          'retries': len(funded), 'retryPromotions': sum(receipts[key].promoted for key in funded),
                          'changedFundedRivals': sum(menus[key][1][method] != menus[key][1][RATE] for key in funded),
                          'fundedTraceSha256': digest(tuple(receipts))}
        if method in (DIRECT, RATE) and any(totals[method][field] != reference['totals'][method][field]
                                             for field in ('holdoutPasses', 'paidLookups', 'newPromotions', 'fundedTraceSha256')):
            raise ValueError(f'The published {method} queue changed')
        if method == RATE:
            baseline = receipts
    return votes, {'totals': totals, 'panelTraceSha256': traces, 'availableCredit': limit,
                   'headroom': diagnose(keys, direct, backups, menus, baseline, limit)}


def execute(plan, reference, data):
    replayed = {phase: measure(plan, phase, data[phase], reference['cohorts'][phase]) for phase in RANKING.PHASES}
    bbh = RANKING.gap.paired.BBH
    with patch.object(shared, 'METHODS', METHODS):
        fit = {bbh: shared.select([replayed[bbh][1]]), 'mmlu': shared.select(
            [replayed[phase][1] for phase in RANKING.gap.paired.replay.PHASES])}
    for phase, (votes, report) in replayed.items():
        winner = fit['mmlu' if phase == bbh else bbh]
        paired = {}
        for challenger, control in ((winner, FULL), (PAIRED, RATE), (ADJUSTED, RATE)):
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
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    report = execute(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
