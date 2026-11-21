"""Test a one-read probe of a previously unopened candidate before admission."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_funded_admission_api as parent
from benchmarks.witness_admission_retry import outcomes as retry_outcomes
from cpo._contract import digest


ROOT, RANKING, retry = parent.ROOT, parent.RANKING, parent.retry
REFERENCE = 'docs/witness-funded-admission-api-results-v1.json'
REFERENCE_SHA256 = '7c0e6f87d35738571ac64df89c7fba25692382f9777aca683e8eb6592fc2c832'
FULL = parent.funding.FULL
UNREAD, PAID = 'unread-probe', 'paid-probe'
METHODS = (retry.BASE, FULL, UNREAD, PAID)
CAP = parent.funding.CAP


def prepare():
    previous, baseline, data = parent.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or json.loads(raw)['planSha256'] != digest(previous):
        raise ValueError('Use the published admission callback verification')
    plan = {'protocol': 'witness-unread-nominee-probe-v1', 'parentPlanSha256': digest(previous),
            'parentReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': METHODS, 'jointProofAndProbeCap': CAP, 'fallbackValidationCap': previous['fallbackValidationCap'],
            'pairedCaseDraws': baseline['plan']['pairedCaseDraws'], 'resamplingSeed': baseline['plan']['resamplingSeed'],
            'rule': 'On the original nominee’s cycle, find a paid nominee miss, preferring a shared incumbent miss. '
                    'Buy at most one alternative grade on that case. Try the first unread candidate, or the '
                    'strongest already-paid candidate with no grade on that case. A pass redirects the single '
                    'independent proof. The probe uses one lookup from its original allowance.',
            'fit': 'Select on the other family by exact promotions within seeded realized spend, then lower spend.',
            'gate': 'Require a positive paired lower endpoint against the full single proof and no higher spend '
                    'than the seeded CPO proof on each held-out cohort.'}
    return plan, baseline, data


def offer(start, nominee, layout, evidence, *, unread):
    by_prompt = {}
    for (prompt, case), grade in evidence.items():
        by_prompt.setdefault(prompt, {})[case] = grade
    own = by_prompt.get(nominee, {})
    misses = [case for case in layout['validation'] if own.get(case) is False]
    misses.sort(key=lambda case: evidence.get((start, case)) is not False)
    pool = [prompt for prompt in layout['alternatives'] if prompt != nominee and prompt != start]
    if unread:
        pool = [prompt for prompt in pool if prompt not in by_prompt]
    else:
        pool = [prompt for prompt in pool if prompt in by_prompt]
        pool.sort(key=lambda prompt: Fraction(sum(by_prompt[prompt].values()) + 1, len(by_prompt[prompt]) + 2), reverse=True)
    return next(((rival, case) for case in misses for rival in pool if (rival, case) not in evidence), None)


def probe(nominee, offered, evaluate, evidence):
    rival, case = offered
    if evidence.get((nominee, case)) is not False or (rival, case) in evidence:
        raise ValueError('A nomination probe requires a paid nominee miss and an unread rival grade')
    passed = evaluate(rival, case)
    if type(passed) is not bool:
        raise ValueError('A nomination probe requires an exact boolean grade')
    return rival if passed else nominee, {**evidence, (rival, case): passed}


def audit_reach(matrix, held, start, nominee, layouts, same_cycle, evidence):
    def score(prompt):
        return sum(matrix[int(prompt)][case] == '1' for case in held)

    floor = max(score(start), score(nominee)) if nominee is not None else score(start)
    paid = {prompt for prompt, _ in evidence}
    stronger = {prompt for cycle in layouts for prompt in cycle['alternatives']
                if prompt != nominee and score(prompt) > floor}
    return {'strongerPaid': int(bool(stronger & paid)), 'strongerUnread': int(bool(stronger - paid)),
            'strongerUnreadSameCycle': int(bool((stronger - paid) & set(same_cycle)))}


def outcomes(matrix, held, start, layouts, plan, policy, nomination, diagnostics):
    prior = retry_outcomes(matrix, held, start, layouts, plan, policy, nomination)
    result = {retry.BASE: prior[retry.BASE], FULL: prior[FULL], UNREAD: prior[FULL], PAID: prior[FULL]}
    nominee = nomination.original
    if nominee is None:
        diagnostics['noNominee'] += 1
        reach = audit_reach(matrix, held, start, None, layouts, (), nomination.grades)
        diagnostics.update({f'noNominee/{name}': count for name, count in reach.items()})
        return result
    diagnostics['nominations'] += 1
    slot = next(i for i, layout in enumerate(layouts) if nominee in layout['alternatives'])
    layout = layouts[slot]
    current = layout['qualify']
    reserve = [case for previous in layouts[:slot] for case in previous['qualify']][:plan['maximumExtensionRows']]
    all_proof = {case for cycle in layouts for case in cycle['qualify']}
    validation = set(layout['validation'])
    if validation & (all_proof | set(held)):
        raise ValueError('A discovery probe cannot use an admission or held-out case')

    def grade(prompt, case):
        return matrix[int(prompt)][case] == '1'

    for method in (UNREAD, PAID):
        offered = offer(start, nominee, layout, nomination.grades, unread=method == UNREAD)
        if offered is None:
            continue
        chosen, evidence = probe(nominee, offered, grade, nomination.grades)
        exact = retry.scalar_proof(start, chosen, current, reserve, grade, evidence,
                                   plan['minimumQualificationGain'], CAP - 1)
        result[method] = retry.Decision(exact.prompt, 1 + len(exact.observations), exact.status)
        diagnostics.update({f'{method}Lookups': 1, f'{method}Switches': int(chosen != nominee)})

    # Inspect outcome coverage only after both policies have finished their decisions.
    diagnostics.update(audit_reach(matrix, held, start, nominee, layouts, layout['alternatives'], nomination.grades))
    return result


def execute(plan, baseline, data):
    measured, activity = {}, {}
    for phase in RANKING.PHASES:
        counts = Counter()

        def run(*args):
            return outcomes(*args, counts)

        with patch.multiple(retry, METHODS=METHODS, outcomes=run):
            measured[phase] = retry.measure(*data[phase], plan['fallbackValidationCap'])
        activity[phase] = counts
    bbh = RANKING.gap.paired.BBH
    with patch.object(retry, 'METHODS', METHODS):
        trained = {bbh: retry.train(list(measured[bbh][0].values())), 'mmlu': retry.train(
            [group for phase in RANKING.gap.paired.replay.PHASES for group in measured[phase][0].values()])}
    cohorts = {}
    for phase, (groups, traces) in measured.items():
        totals = {method: sum((group['counts'][method] for group in groups.values()), Counter()) for method in METHODS}
        for method in (retry.BASE, FULL):
            if any(totals[method][key] != baseline['cohorts'][phase]['totals'][method][key]
                   for key in ('holdoutPasses', 'paidLookups', 'promotions', 'proofLookups')):
                raise ValueError('The published single-proof controls changed')
        votes = {subject: {'cases': unit['cases'], 'decisionsPerCase': unit['decisionsPerCase']}
                 for subject, unit in groups.items()}
        winner = trained['mmlu' if phase == bbh else bbh]['selected']
        pairs = {}
        for method, control in dict.fromkeys(((UNREAD, PAID), (UNREAD, FULL), (winner, FULL))):
            with patch.object(RANKING.paired_bands, 'BASELINE', control):
                pairs[f'{method} vs {control}'] = RANKING.paired_bands.paired_ranges(votes, method, plan)['subjectsAndCases']
        cohorts[phase] = {'totals': totals, 'activity': activity[phase], 'selectedOutsideFamily': winner,
                          'paired': pairs, 'panelTraceSha256': traces,
                          'qualifies': totals[winner]['paidLookups'] <= totals[retry.BASE]['paidLookups']
                          and pairs[f'{winner} vs {FULL}']['interval95PercentagePoints'][0] > 0}
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'training': trained, 'cohorts': cohorts,
            'qualifies': all(group['qualifies'] for group in cohorts.values())}


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
