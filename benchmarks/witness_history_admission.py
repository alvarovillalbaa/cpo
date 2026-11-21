"""Rank stalled-search candidates from earlier paid, case-disjoint validation."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_short_admission_credit as prior
from benchmarks.witness_admission_retry import outcomes as original_outcomes
from cpo import Row
from cpo._contract import digest
from cpo.halving.funded_admission import qualify_with_funded_retry
from cpo.rotating_witness.episode import WitnessCycle


shared, credit = prior.shared, prior.credit
ROOT, RANKING, FULL, CAP, retry = prior.ROOT, prior.RANKING, prior.FULL, prior.CAP, prior.retry
REFERENCE = 'docs/witness-short-admission-credit-results-v1.json'
REFERENCE_SHA256 = '6ff502ba85bc00d3a2f4f830266ac5c478617b0019787257dc5d941de2fe1232'
DIRECT, HISTORY, CONFIRM = shared.DIRECT_ONLY, 'history-margin', 'history-confirmed'
METHODS = (FULL, DIRECT, HISTORY, CONFIRM)
MINIMUM_PAIRS = 3


def prepare():
    parent, _, unchanged, _, _, data = prior.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('Use the published single-proof and direct queue controls')
    plan = {'protocol': 'witness-history-admission-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': METHODS, 'minimumMatchedHistory': MINIMUM_PAIRS, 'credits': parent['credits'],
            'fallbackValidationCap': parent['fallbackValidationCap'], 'pairedCaseDraws': parent['pairedCaseDraws'],
            'resamplingSeed': parent['resamplingSeed'], 'rule': 'At a no-nominee stop, consider previously graded '
            'candidates. Compare positive paired margins on earlier paid grades from the same subject and model, '
            'excluding every current training, validation, proof, and holdout case. Rerank using that evidence '
            'or require it to confirm the existing supported-rate choice. Fund the original exact proof in '
            'schedule order using the same shared cohort credit and full reservation.',
            'fit': 'Select on the other family by promotions and then charged lookups.',
            'gate': 'Require a positive paired lower endpoint against the single proof within seeded spend.'}
    return plan, reference, unchanged, data


def excluded_cases(held, layouts):
    return set(held) | {case for layout in layouts for role in ('train', 'validation', 'qualify') for case in layout[role]}


def rank(start, candidates, history, excluded):
    incumbent = history.get(start, {})
    support, scores = {}, {}
    for prompt in candidates:
        replies = history.get(prompt, {})
        common = (incumbent.keys() & replies.keys()) - excluded
        margin = sum(replies[case] - incumbent[case] for case in common)
        support[prompt] = len(common)
        if len(common) >= MINIMUM_PAIRS and margin > 0:
            scores[prompt] = Fraction(margin, len(common) + 2)
    return max(scores, default=None, key=scores.__getitem__), support, scores


def add_paid(history, grades):
    for (prompt, case), passed in grades.items():
        seen = history.setdefault(prompt, {})
        if seen.setdefault(case, passed) != passed:
            raise ValueError('Recorded history changed the grade of a previously evaluated pair')


def proof_offer(key, subject, start, candidate, held, layouts, matrix, active, grades):
    def settle():
        held_set = set(held)
        cycles = tuple(WitnessCycle(tuple(layout['alternatives']), tuple(Row(str(case), 'task') for case in layout['validation']),
                                    tuple(Row(str(case), 'task') for case in layout['qualify']), layout['seed'])
                       for layout in layouts)
        ledger = {(prompt, str(case)): passed for (prompt, case), passed in grades.items()}

        def evaluate(prompt, row, _repeat):
            if int(row.id) in held_set:
                raise ValueError('An independent proof cannot read holdout')
            return matrix[int(prompt)][int(row.id)] == '1'

        checked = qualify_with_funded_retry(
            start, candidate, cycles, evaluate, ledger, minimum_retry_lookups=CAP + 1, evaluation_limit=CAP,
            minimum_gain=active['minimumQualificationGain'], maximum_extension_rows=active['maximumExtensionRows'])
        changes = tuple(int(matrix[int(checked.prompt)][case] == '1') - int(matrix[int(start)][case] == '1') for case in held)
        return credit.Settlement(checked.qualification_evaluations, changes, checked.prompt != start)

    return shared.Offer(key, subject, shared.DIRECT, CAP, settle)


def collect(plan, data):
    _, panels, _, _, _ = data
    tags = {id(panel['correctness']): (i, panel['subject']) for i, panel in enumerate(panels)}
    histories, serial, activity = {}, Counter(), Counter()
    offers = {method: [] for method in METHODS[1:]}

    def outcomes(matrix, held, start, layouts, active, policy, nomination):
        previous = original_outcomes(matrix, held, start, layouts, active, policy, nomination)
        panel, subject = tags[id(matrix)]
        key = (panel, serial[panel])
        serial[panel] += 1
        history = histories.setdefault(panel, {})
        if nomination.original is None:
            enrolled = [prompt for layout in layouts for prompt in layout['alternatives']]
            selected, paid = credit.prior.prior.choose(start, enrolled, nomination.grades)
            supported = selected[credit.SUPPORTED]
            candidate, count, scores = rank(start, paid, history, excluded_cases(held, layouts))
            activity.update(noNominee=1, anyHistoricalPairs=int(any(count.values())),
                            anySupportedHistory=int(any(size >= MINIMUM_PAIRS for size in count.values())),
                            positiveSupportedHistory=int(bool(scores)))
            winners = {DIRECT: supported, HISTORY: candidate, CONFIRM: supported if supported in scores else None}
            for method, prompt in winners.items():
                if prompt is not None:
                    offers[method].append(proof_offer(key, subject, start, prompt, held, layouts, matrix, active, nomination.grades))
        if any(case in held for _, case in nomination.grades):
            raise ValueError('Held-out grades cannot enter the history ledger')
        add_paid(history, nomination.grades)
        return {retry.BASE: previous[retry.BASE], FULL: previous[FULL]}

    with patch.multiple(retry, METHODS=(retry.BASE, FULL), outcomes=outcomes):
        groups, traces = retry.measure(*data, plan['fallbackValidationCap'])
    return groups, traces, offers, activity


def measure(plan, phase, data, original, expected):
    groups, traces, offers, activity = collect(plan, data)
    totals = {arm: sum((group['counts'][arm] for group in groups.values()), Counter()) for arm in (retry.BASE, FULL)}
    for arm in (retry.BASE, FULL):
        if any(totals[arm][key] != original['totals'][arm].get(key, 0)
               for key in ('holdoutPasses', 'paidLookups', 'proofLookups', 'promotions')):
            raise ValueError('The original search and proof controls changed')
    if activity['noNominee'] != original['activity']['noNominee']:
        raise ValueError('The no-nominee slot count changed')

    votes = {subject: {'cases': {FULL: group['cases'][FULL]}, 'decisionsPerCase': group['decisionsPerCase']}
             for subject, group in groups.items()}
    limit = plan['credits'][phase]
    for method, candidates in offers.items():
        receipts, left = shared.allocate(candidates, shared.DIRECT_ONLY, limit, lambda candidate: candidate.settle())
        labels = {offer.key: offer.subject for offer in candidates}
        for group in votes.values():
            group['cases'][method] = group['cases'][FULL].copy()
        for key, receipt in receipts.items():
            scores = votes[labels[key]]['cases'][method]
            scores[:] = [a + b for a, b in zip(scores, receipt.changes, strict=True)]
        totals[method] = {'holdoutPasses': sum(sum(group['cases'][method]) for group in votes.values()),
                          'paidLookups': totals[FULL]['paidLookups'] + limit - left, 'extraLookups': limit - left,
                          'newPromotions': sum(receipt.promoted for receipt in receipts.values()),
                          'offers': len(candidates), 'proofs': len(receipts), 'fundedTraceSha256': digest(tuple(receipts))}
    if any(totals[DIRECT][key] != expected['totals'][DIRECT][key]
           for key in ('holdoutPasses', 'paidLookups', 'newPromotions', 'fundedTraceSha256')):
        raise ValueError('The original direct queue changed')
    return votes, {'totals': totals, 'activity': activity, 'allocatedCredit': limit, 'panelTraceSha256': traces}


def execute(plan, reference, unchanged, data):
    replayed = {phase: measure(plan, phase, data[phase], unchanged['cohorts'][phase], reference['cohorts'][phase])
                for phase in RANKING.PHASES}
    bbh = RANKING.gap.paired.BBH
    with patch.object(shared, 'METHODS', METHODS):
        fit = {bbh: shared.select([replayed[bbh][1]]), 'mmlu': shared.select(
            [replayed[phase][1] for phase in RANKING.gap.paired.replay.PHASES])}
    for phase, (votes, report) in replayed.items():
        selected = fit['mmlu' if phase == bbh else bbh]
        pairs = {}
        for method, control in ((selected, FULL), (HISTORY, DIRECT), (CONFIRM, DIRECT)):
            with patch.object(RANKING.paired_bands, 'BASELINE', control):
                pairs[f'{method} vs {control}'] = RANKING.paired_bands.paired_ranges(votes, method, plan)['subjectsAndCases']
        report.update(selectedOutsideFamily=selected, paired=pairs, qualifies=pairs[f'{selected} vs {FULL}']['interval95PercentagePoints'][0] > 0)
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
