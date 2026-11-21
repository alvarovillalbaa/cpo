"""Fund a four-anchor challenge to the original nominee from a fixed credit pool."""

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from typing import Callable
from unittest.mock import patch

from benchmarks import witness_matched_anchors as parent
from benchmarks.witness_fallback_proof_reserve import fund
from cpo._contract import digest


ROOT, RANKING, retry = parent.ROOT, parent.RANKING, parent.retry
FULL, CAP = parent.previous.FULL, parent.previous.CAP
REFERENCE = 'docs/witness-matched-anchors-results-v1.json'
REFERENCE_SHA256 = 'cdc7b51a7fad3799236cb13ab92e0a4df7a2ddd8bb3d5a5f1c33bbcd76fee5b4'
CHEAPEST, RATE = 'fewest-possible-reads', 'highest-paid-rate'
METHODS = (CHEAPEST, RATE)
PROBE = 4


@dataclass(frozen=True)
class Offer:
    key: tuple[int, int]
    subject: str
    settle: Callable[[int], tuple[int, 'Settlement']]


@dataclass(frozen=True)
class Settlement:
    changes: tuple[int, ...]
    probe: int = 0
    replacement: int = 0
    avoided: int = 0
    switched: bool = False
    promoted: bool = False
    possible: bool = True


def prepare():
    previous, _, _, native, data = parent.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(previous):
        raise ValueError('Use the published four-anchor comparison')
    credits = {phase: row['totals'][retry.BASE]['paidLookups'] - row['totals'][FULL]['paidLookups']
               for phase, row in reference['cohorts'].items()}
    plan = {key: previous[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed', 'proofCap')}
    plan.update(protocol='witness-funded-anchor-challenge-v1', parentPlanSha256=digest(previous),
                parentReceiptSha256=REFERENCE_SHA256, sourceSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                fundingSha256=sha256((ROOT / 'benchmarks/witness_fallback_proof_reserve.py').read_bytes()).hexdigest(),
                methods=METHODS, primary=CHEAPEST, anchors=parent.WIDTH, maxNewReads=PROBE, credits=credits,
                rule='At the original first nomination, challenge with one previously evaluated rival on '
                'the original nominee’s four seeded validation anchors. Require a strict exact advantage '
                'before switching. Keep the same independent proof cap and the challenger’s original panel.',
                budget='Fund the entire replacement proof and every fresh probe read from a fixed cohort '
                'credit. Return unused credit. The original proof remains on an unsuccessful challenge. '
                'A switch avoids the original proof without crediting its cost back into the queue.',
                gate='Require a positive paired lower endpoint against the original single proof on all cohorts '
                'within the seeded lookup total.')
    return plan, reference, native, data


def bounds(nominee, rival, anchors, paid):
    old = [paid.get((nominee, case)) for case in anchors]
    new = [paid.get((rival, case)) for case in anchors]
    return old.count(False) + new.count(True) - len(anchors), len(anchors) - old.count(True) - new.count(False)


def order_rivals(nominee, pool, anchors, grades):
    counts = {}
    for (prompt, _), passed in grades.items():
        counts.setdefault(prompt, Counter()).update(passes=passed, reads=1)
    rates = {prompt: Fraction(item['passes'] + 1, item['reads'] + 2) for prompt, item in counts.items()}
    feasible = {}
    for prompt in pool:
        low, high = bounds(nominee, prompt, anchors, grades)
        if prompt in rates and high > 0 and low + PROBE > 0:
            feasible[prompt] = max(0, 1 - low)
    winners = {CHEAPEST: min(feasible, default=None, key=lambda prompt: (feasible[prompt], -rates[prompt])),
               RATE: max(feasible, default=None, key=lambda prompt: (rates[prompt], -feasible[prompt]))}
    return winners, rates


def challenge(nominee, rival, anchors, grades, rates, evaluate, cap):
    paid = grades.copy()
    preferred = (rival, nominee) if rates[rival] >= 1 - rates[nominee] else (nominee, rival)
    order = [(prompt, case) for prompt in preferred for case in anchors if (prompt, case) not in paid]
    spent = 0
    low, high = bounds(nominee, rival, anchors, paid)
    possible = high > 0 and low + cap > 0
    while high > 0 and low <= 0 and low + cap - spent > 0 and spent < len(order):
        prompt, case = order[spent]
        passed = evaluate(prompt, case)
        if type(passed) is not bool:
            raise ValueError('A new validation grade must be an exact boolean')
        paid[prompt, case] = passed
        spent += 1
        low, high = bounds(nominee, rival, anchors, paid)
    return low > 0, spent, paid, possible


def collect(plan, data, reference):
    _, panels, _, _, _ = data
    tags = {id(panel['correctness']): (index, panel['subject']) for index, panel in enumerate(panels)}
    counts = Counter()
    offers = {method: [] for method in METHODS}

    def outcomes(matrix, held, start, layouts, active, policy, nomination):
        original = retry_outcomes(matrix, held, start, layouts, active, policy, nomination)
        result = {retry.BASE: original[retry.BASE], FULL: original[FULL]}
        panel, subject = tags[id(matrix)]
        key = panel, counts[panel]
        counts[panel] += 1
        nominee = nomination.original
        if nominee is None:
            return result
        roster = {prompt: layout for layout in layouts for prompt in layout['alternatives']}
        layout = roster[nominee]
        anchors = list(layout['validation'])
        Random(layout['seed']).shuffle(anchors)
        anchors = tuple(anchors[:plan['anchors']])
        forbidden = set(held) | {case for item in layouts for role in ('train', 'qualify') for case in item[role]}
        if forbidden.intersection(anchors) or len(set(anchors)) != plan['anchors']:
            raise ValueError('The matched challenge needs validation cases disjoint from training, proof, and holdout')
        pool = [prompt for prompt, enrolled in roster.items()
                if prompt != nominee and set(anchors).issubset(enrolled['validation'])]
        choices, rates = order_rivals(nominee, pool, anchors, nomination.grades)

        def grade(prompt, case):
            return matrix[int(prompt)][case] == '1'

        def settle(cap, rival):
            switched, probe, paid, possible = challenge(nominee, rival, anchors, nomination.grades, rates, grade, cap)
            if not switched:
                return probe, Settlement((0,) * len(held), probe=probe, possible=possible)
            alternate = RANKING.Nomination(rival, nomination.paid_search + probe, paid)
            proof = parent.previous.qualify(matrix, held, start, layouts, active, alternate)
            old = original[FULL]
            changes = tuple(int(grade(proof.prompt, case)) - int(grade(old.prompt, case)) for case in held)
            return probe + proof.lookups, Settlement(changes, probe, proof.lookups, old.lookups,
                                                     switched=True, promoted=proof.prompt != start)

        for method, rival in choices.items():
            if rival is not None:
                offers[method].append(Offer(key, subject, lambda cap, rival=rival: settle(cap, rival)))
        return result

    retry_outcomes = retry.outcomes
    with patch.multiple(retry, METHODS=(retry.BASE, FULL), outcomes=outcomes):
        groups, traces = retry.measure(*data, plan['fallbackValidationCap'])
    totals = {method: sum((group['counts'][method] for group in groups.values()), Counter()) for method in (retry.BASE, FULL)}
    if traces != reference['panelTraceSha256'] or any(
            totals[method][key] != reference['totals'][method][key]
            for method in totals for key in ('holdoutPasses', 'paidLookups', 'proofLookups', 'promotions')):
        raise ValueError('The published search and proof controls changed')
    return totals, groups, traces, offers


def measure(plan, phase, data, reference, native):
    totals, groups, traces, offers = collect(plan, data, reference)
    votes = {subject: {'decisionsPerCase': group['decisionsPerCase'],
                       'cases': {method: group['cases'][FULL].copy() for method in (FULL, *METHODS)}}
             for subject, group in groups.items()}
    issued = plan['credits'][phase]
    paired = {}
    for method, queue in offers.items():
        receipts, left = fund(queue, issued, CAP, PROBE, lambda offer, cap: offer.settle(cap))
        labels = {offer.key: offer.subject for offer in queue}
        activity = Counter()
        for key, _, paid, item in receipts:
            vector = votes[labels[key]]['cases'][method]
            vector[:] = [score + delta for score, delta in zip(vector, item.changes, strict=True)]
            if paid != item.probe + item.replacement:
                raise ValueError('The optional proof did not reconcile to its credit charge')
            activity.update(probeLookups=item.probe, replacementProofLookups=item.replacement,
                            avoidedOriginalProofLookups=item.avoided, switchedNominees=int(item.switched),
                            replacementPromotions=int(item.promoted), offersWithinResolvedCap=int(item.possible))
        spent = issued - left
        observed = totals[FULL]['paidLookups'] + spent - activity['avoidedOriginalProofLookups']
        if observed > totals[retry.BASE]['paidLookups'] or spent != sum(row[2] for row in receipts):
            raise ValueError('The budget must fit seeded spend using paid receipts alone')
        eligible = [(key, row) for key, row in native['totals'].items()
                    if key.startswith('gepa-') and row['paidLookups'] <= observed]
        setting, best = min(eligible, key=lambda item: (-Fraction(item[1]['macroAccuracy']), item[1]['paidLookups'], item[0]))
        totals[method] = {'holdoutPasses': sum(sum(group['cases'][method]) for group in votes.values()),
                          'paidLookups': observed, 'issuedCredit': issued, 'usedCredit': spent, 'offers': len(queue),
                          'funded': len(receipts), 'activity': activity,
                          'fundedTraceSha256': digest([(key, cap, paid, asdict(item)) for key, cap, paid, item in receipts]),
                          'bestAffordableNativeGEPA': {'setting': setting, **best}}
        with patch.object(RANKING.paired_bands, 'BASELINE', FULL):
            paired[method] = RANKING.paired_bands.paired_ranges(votes, method, plan)['subjectsAndCases']
    return {'totals': totals, 'pairedVsOriginal': paired, 'panelTraceSha256': traces,
            'qualifies': paired[CHEAPEST]['interval95PercentagePoints'][0] > 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, reference, native, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    cohorts = {phase: measure(plan, phase, data[phase], reference['cohorts'][phase], native['cohorts'][phase])
               for phase in RANKING.PHASES}
    report = {'plan': plan, 'planSha256': seal, 'newProviderRequests': 0, 'cohorts': cohorts,
              'qualifies': all(row['qualifies'] for row in cohorts.values())}
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
