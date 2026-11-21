"""Keep the independent proof funded while shrinking fallback search at a budget boundary."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_fallback_reserve as original, witness_fallback_routing as routing
from cpo._contract import digest


ROOT = original.ROOT
REFERENCE = 'docs/witness-fallback-reserve-results-v1.json'
REFERENCE_SHA = '1762c50a47140575cc712be373a12a684622ff4dc88b8e9ab98115a25e8f7f49'


def prepare():
    prior, baseline, inputs = original.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA or reference['planSha256'] != digest(prior):
        raise ValueError('Use the published full-reservation replay and orderings')
    runner = Path(__file__).resolve()
    plan = {**prior, 'protocol': 'witness-fallback-proof-first-reserve-v1', 'parentPlanSha256': digest(prior),
            'parentReportSha256': REFERENCE_SHA, 'sourceSha256': {**prior['sourceSha256'],
                runner.relative_to(ROOT).as_posix(): sha256(runner.read_bytes()).hexdigest()},
            'fundingRule': ('Reserve maximum proof before every fallback. Give its search the lesser of 16 '
                            'and the credit left after reserving proof. Return unused credit after settlement.'),
            'fit': 'Keep the paid and blind orderings fitted in the published full-reservation replay.',
            'gate': ('At the primary budget require a positive paired subject-and-case lower endpoint '
                     'in every family against full-reservation paid ordering and against proof-first blind ordering.')}
    return plan, reference, baseline, inputs


def fund(items, issued, proof_reserve, max_search, settle):
    if any(type(value) is not int or value < 0 for value in (issued, proof_reserve, max_search)) or proof_reserve == 0:
        raise ValueError('Use whole lookup limits and a positive independent proof reservation')
    receipts, remaining = [], issued
    for item in items:
        if remaining < proof_reserve:
            break
        search = min(max_search, remaining - proof_reserve)
        reserved = proof_reserve + search
        remaining -= reserved
        paid, votes = settle(item, search)
        if type(paid) is not int or not 0 <= paid <= reserved:
            raise ValueError('Fallback exceeded its funded search and proof allowance')
        receipts.append((item.key, search, paid, votes))
        remaining += reserved - paid
    return receipts, remaining


def at_cap(cap, inputs, corpus):
    """Index deterministic counterfactuals by the cap authorized by the running ledger."""
    refs, bbh_inputs, mmlu_inputs = inputs
    settings, panels, bbh_reference = bbh_inputs
    active = bbh_reference['plan']['conditions'][routing.transfer.BASE]['searchCap']
    mmlu_design, mmlu_settings, cohorts, mmlu_reference = mmlu_inputs
    with patch.object(routing, 'CAP', cap):
        bbh = routing.archive_episodes(panels, settings, active, bbh_reference['panels'])
        mmlu = routing.archive_episodes([panel for panels in cohorts.values() for panel in panels], mmlu_settings,
                                        mmlu_design['baseSearchCap'], {key: row for report in mmlu_reference.values()
                                                                     for key, row in report['panels'].items()})
        promptolution = routing.promptolution_episodes(corpus, refs[routing.CAP_REPORT])
    groups = [*bbh.values(), *mmlu.values(), *promptolution.values()]
    all_items = [item for group in groups for item in group['opportunities']]
    by_episode = {item.key: item for item in all_items}
    if len(by_episode) != len(all_items):
        raise ValueError('Physical fallback episodes must have unique identities')
    return by_episode


def measure(groups, ordering, rate, cap, settle):
    totals, subjects, votes, allowances = Counter(), {}, {}, Counter()
    for name, group in groups.items():
        source = group['opportunities']
        issued, proof = len(source) * rate, group['quote'] - cap
        receipts, remaining = fund(original.order(source, ordering), issued, proof, cap, settle)
        changes = [0] * len(group['held'])
        for _, limit, _, deltas in receipts:
            allowances[limit] += 1
            changes = [a + b for a, b in zip(changes, deltas, strict=True)]
        point = {'issuedLookups': issued, 'addedLookups': issued - remaining, 'unusedLookups': remaining,
                 'addedPasses': sum(changes), 'activations': len(receipts), 'shortenedSearches': sum(
                     limit < cap for _, limit, _, _ in receipts)}
        totals.update(point)
        subjects[name] = {**point, 'proofReservation': proof, 'settlementSha256': digest(receipts)}
        votes[name] = {'deltas': changes, 'decisionsPerCase': group['decisionsPerCase']}
    gain = sum(Fraction(sum(row['deltas']), len(row['deltas']) * row['decisionsPerCase'])
               for row in votes.values()) / len(votes)
    return {**totals, 'macroAccuracyGain': str(gain), 'searchAllowances': allowances}, subjects, votes


def compare(plan, families, reference, settle):
    caps = plan['fallbackSearchCap']
    result = {}
    for name, groups in families.items():
        points = {}
        for rate in plan['issuedLookupsPerEligibleEpisode']:
            earlier = reference['families'][name]['points'][str(rate)]
            paid_order, blind_order = earlier['paidOrdering'], earlier['blindOrdering']
            full, detail, original_votes = original.measure(groups, paid_order, rate)
            if full != earlier['paid'] or detail != earlier['paidTasks']:
                raise ValueError('The published full-reservation paid receipts changed')
            fixed_blind, _, _ = original.measure(groups, blind_order, rate)
            if fixed_blind != earlier['blind']:
                raise ValueError('The published full-reservation blind receipts changed')
            paid, paid_tasks, paid_votes = measure(groups, paid_order, rate, caps, settle)
            blind, blind_tasks, blind_votes = measure(groups, blind_order, rate, caps, settle)
            bands = {'againstFullPaid': original.paired_ranges(plan, paid_votes, original_votes),
                     'againstProofFirstBlind': original.paired_ranges(plan, paid_votes, blind_votes)}
            points[rate] = {'paidOrdering': paid_order, 'blindOrdering': blind_order, 'fullPaid': full,
                            'fullBlind': fixed_blind, 'paid': paid, 'blind': blind, 'paidTasks': paid_tasks,
                            'blindTasks': blind_tasks, **bands, 'passed': all(
                                row['subjectsAndCases']['interval95PercentagePoints'][0] > 0 for row in bands.values())}
        result[name] = points
    return result


def execute(plan, reference, baseline, inputs, corpus):
    families = original.reconstruct(inputs, corpus, baseline)
    full_set = {item.key for groups in families.values() for group in groups.values() for item in group['opportunities']}
    shortened = {}

    def settle(item, cap):
        if cap == plan['fallbackSearchCap']:
            return item.addedLookups, item.deltas
        if cap not in shortened:
            shortened[cap] = at_cap(cap, inputs, corpus)
            if shortened[cap].keys() != full_set:
                raise ValueError('A search allowance changed which episodes were originally eligible')
        outcome = shortened[cap][item.key]
        if (outcome.incumbentPasses, outcome.incumbentReads, outcome.paidGrades, outcome.pairedWins) != (
                item.incumbentPasses, item.incumbentReads, item.paidGrades, item.pairedWins):
            raise ValueError('An allowance changed evidence observed before the fallback')
        return outcome.addedLookups, outcome.deltas

    report = compare(plan, families, reference, settle)
    return {'plan': plan, 'planSha256': digest(plan), 'families': report, 'newProviderRequests': 0,
            'qualifies': all(row[plan['primaryIssuedRate']]['passed'] for row in report.values()),
            'replayedShorterSearchCaps': sorted(shortened)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.corpus is None and args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.corpus is None or args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the pinned archive, current seal, and a fresh report path')
    result = execute(plan, *inputs, routing.episode.load_corpus(args.corpus.read_bytes()))
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
