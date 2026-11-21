"""Price one independent proof when the original paid search found no nominee."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_unread_nominee_probe as prior
from benchmarks.witness_admission_retry import outcomes as retry_outcomes
from cpo import Row
from cpo._contract import digest
from cpo.halving.funded_admission import qualify_with_funded_retry
from cpo.rotating_witness.episode import WitnessCycle


ROOT, RANKING, retry, FULL, CAP = prior.ROOT, prior.RANKING, prior.retry, prior.FULL, prior.CAP
REFERENCE = 'docs/witness-unread-nominee-probe-results-v1.json'
REFERENCE_SHA256 = '6bc55640efc78eb16e68342c6b689cebc8e842d1a4ce5381e3abd95ba97933a1'
ANY, RATE, PAIR, TWO = 'any-paid', 'supported-rate', 'paired-gain', 'two-paired-gains'
ROUTES = (ANY, RATE, PAIR, TWO)
METHODS = (retry.BASE, FULL, *ROUTES)


def prepare():
    source, _, data = prior.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(source):
        raise ValueError('Use the published search reachability replay')
    plan = {'protocol': 'witness-no-nominee-admission-v1', 'parentPlanSha256': digest(source),
            'parentReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': METHODS, 'proofCap': CAP, 'fallbackValidationCap': source['fallbackValidationCap'],
            'pairedCaseDraws': source['pairedCaseDraws'], 'resamplingSeed': source['resamplingSeed'],
            'scope': 'Preserve paid search and every existing nomination. At a no-nominee stop, choose one already '
                     'graded candidate, charge its exact independent proof, and keep all original cases and gates.',
            'fit': 'Choose on the other family by promotions within total seeded proof spend, then lower cost.',
            'bound': 'For diagnosis, price every previously evaluated candidate and find the best heldout gains '
                     'among independently qualifying candidates at the observed seeded-to-expected proof savings. '
                     'Choose at most one proof per episode. This retrospective bound cannot choose the live route.',
            'gate': 'Require positive paired quality against the expected-read control within seeded realized spend.'}
    return plan, reference, data


def choose(start, enrolled, grades):
    replies = {}
    for (prompt, case), passed in grades.items():
        replies.setdefault(prompt, {})[case] = passed
    old = replies.get(start, {})
    old_rate = Fraction(sum(old.values()) + 1, len(old) + 2)
    features = {}
    for prompt in enrolled:
        if prompt == start or prompt not in replies:
            continue
        seen = replies[prompt]
        common = old.keys() & seen.keys()
        gain = sum(seen[case] - old[case] for case in common)
        features[prompt] = (Fraction(sum(seen.values()) + 1, len(seen) + 2), len(seen), gain,
                            Fraction(gain, len(common) + 2))

    def rate(prompt):
        return features[prompt][0]

    winners = {ANY: max(features, default=None, key=rate),
               RATE: max((prompt for prompt in features if features[prompt][1] >= 3 and rate(prompt) > old_rate),
                         default=None, key=rate)}
    for arm, minimum in ((PAIR, 1), (TWO, 2)):
        winners[arm] = max((prompt for prompt in features if features[prompt][2] >= minimum),
                           default=None, key=lambda prompt: (features[prompt][3], rate(prompt)))
    return winners, tuple(features)


def hindsight(menus, limit):
    frontier = {0: 0}
    for menu in menus:
        next_frontier = frontier.copy()
        for before, total in frontier.items():
            for cost, gain in menu.items():
                if before + cost <= limit:
                    charged = before + cost
                    next_frontier[charged] = max(next_frontier.get(charged, 0), total + gain)
        frontier, best = {}, -1
        for cost, gain in sorted(next_frontier.items()):
            if gain > best:
                frontier[cost], best = gain, gain
    cost = max(frontier, key=lambda paid: (frontier[paid], -paid))
    return {'paidLookups': cost, 'addedHoldoutPasses': frontier[cost]}


def outcomes(matrix, held, start, layouts, plan, policy, nomination, reach, menus):
    previous = retry_outcomes(matrix, held, start, layouts, plan, policy, nomination)
    result = {retry.BASE: previous[retry.BASE], FULL: previous[FULL], **dict.fromkeys(ROUTES, previous[FULL])}
    if nomination.original is not None:
        return result
    reach['noNominee'] += 1
    cycles = tuple(WitnessCycle(tuple(layout['alternatives']), tuple(Row(str(case), 'task') for case in layout['validation']),
                                tuple(Row(str(case), 'task') for case in layout['qualify']), layout['seed'])
                   for layout in layouts)
    enrolled = [prompt for cycle in cycles for prompt in cycle.candidates]
    winners, paid = choose(start, enrolled, nomination.grades)
    evidence = {(prompt, str(case)): passed for (prompt, case), passed in nomination.grades.items()}
    held_set = set(held)

    def grade(prompt, row, _repeat):
        if int(row.id) in held_set:
            raise ValueError('Admission cannot read a held-out grade')
        return matrix[int(prompt)][int(row.id)] == '1'

    proofs = {prompt: qualify_with_funded_retry(
        start, prompt, cycles, grade, evidence, minimum_retry_lookups=CAP + 1, evaluation_limit=CAP,
        maximum_extension_rows=plan['maximumExtensionRows'], minimum_gain=plan['minimumQualificationGain'])
        for prompt in paid}
    for arm, prompt in winners.items():
        if prompt is None:
            continue
        proof = proofs[prompt]
        if proof.retry is not None or proof.qualification_evaluations > CAP:
            raise ValueError('A rescued nomination has a single proof and the original cap')
        result[arm] = retry.Decision(proof.prompt, proof.qualification_evaluations, proof.first.status)
        reach[f'{arm}/attempted'] += 1

    # Proofs for the unchosen candidates are only used after freezing each route.
    def score(prompt):
        return sum(matrix[int(prompt)][case] == '1' for case in held)

    start_score = score(start)
    positive = [prompt for prompt in paid if score(prompt) > start_score]
    certified = [prompt for prompt in positive if proofs[prompt].prompt == prompt]
    reach.update(strongerPaid=int(bool(positive)), independentlyCertifiedStrongerPaid=int(bool(certified)))
    menu = {}
    for prompt in certified:
        cost = proofs[prompt].qualification_evaluations
        menu[cost] = max(menu.get(cost, 0), score(prompt) - start_score)
    if menu:
        menus.append(menu)
    return result


def execute(plan, reference, data):
    measured, activity, opportunities = {}, {}, {}
    for phase in RANKING.PHASES:
        reach, menus = Counter(), []

        def run(*args):
            return outcomes(*args, reach, menus)

        with patch.multiple(retry, METHODS=METHODS, outcomes=run):
            measured[phase] = retry.measure(*data[phase], plan['fallbackValidationCap'])
        activity[phase], opportunities[phase] = reach, menus
    bbh = RANKING.gap.paired.BBH
    with patch.object(retry, 'METHODS', METHODS):
        fit = {bbh: retry.train(list(measured[bbh][0].values())), 'mmlu': retry.train(
            [item for phase in RANKING.gap.paired.replay.PHASES for item in measured[phase][0].values()])}
    cohorts = {}
    for phase, (groups, traces) in measured.items():
        prior_row = reference['cohorts'][phase]
        counts = activity[phase]
        if (counts['noNominee'], counts['strongerPaid']) != (prior_row['activity']['noNominee'],
                                                            prior_row['activity']['noNominee/strongerPaid']):
            raise ValueError('The published no-nominee reachability counts changed')
        totals = {method: sum((group['counts'][method] for group in groups.values()), Counter()) for method in METHODS}
        for method in (retry.BASE, FULL):
            if any(totals[method][key] != prior_row['totals'][method].get(key, 0)
                   for key in ('holdoutPasses', 'paidLookups', 'proofLookups', 'promotions')):
                raise ValueError('The original nomination and single-proof controls changed')
        votes = {task: {'cases': item['cases'], 'decisionsPerCase': item['decisionsPerCase']} for task, item in groups.items()}
        selected = fit['mmlu' if phase == bbh else bbh]['selected']
        with patch.object(RANKING.paired_bands, 'BASELINE', FULL):
            paired = RANKING.paired_bands.paired_ranges(votes, selected, plan)['subjectsAndCases']
        credit = totals[retry.BASE]['paidLookups'] - totals[FULL]['paidLookups']
        cohorts[phase] = {'totals': totals, 'activity': counts, 'selectedOutsideFamily': selected,
                          'pairedSelectedAgainstSingle': paired, 'availableLookups': credit,
                          'hindsightWithinCredit': hindsight(opportunities[phase], credit), 'panelTraceSha256': traces,
                          'qualifies': totals[selected]['paidLookups'] <= totals[retry.BASE]['paidLookups']
                          and paired['interval95PercentagePoints'][0] > 0}
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
