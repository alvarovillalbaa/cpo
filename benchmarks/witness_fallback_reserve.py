"""Compare fallback orderings under a hard budget for search and proof."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_fallback_routing as routing
from cpo._contract import digest


ROOT = routing.ROOT
REFERENCE = 'docs/witness-fallback-routing-results-v1.json'
REFERENCE_SHA = 'b61372335766755cdccd0850584d10ea17fa5f1fccd445f6e5d01454a32f1943'
RATES, PRIMARY = (4, 8, 12), 8
PAID = ('low-incumbent-pass-rate', 'fewest-paid-grades', 'most-paired-wins')
BLIND = {'blind-172': 172, 'blind-233': 233, 'blind-347': 347}


def prepare():
    parent, *inputs = routing.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA or reference['planSha256'] != digest(parent):
        raise ValueError('The published family-holdout routing must reproduce')
    path = Path(__file__).resolve()
    plan = {'protocol': 'witness-fallback-funded-ordering-v1', 'parentPlanSha256': digest(parent),
            'parentReportSha256': REFERENCE_SHA, 'sourceSha256': {**parent['sourceSha256'],
                path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()},
            'families': parent['families'], 'paidOrderings': PAID, 'blindOrderings': BLIND,
            'issuedLookupsPerEligibleEpisode': RATES, 'primaryIssuedRate': PRIMARY, 'fallbackSearchCap': routing.CAP,
            'pairedCaseDraws': parent['pairedCaseDraws'], 'resamplingSeed': parent['resamplingSeed'],
            'fundingRule': ('After the witness phase, issue per-task credit from the number of eligible episodes. '
                            'Reserve the full validation and maximum independent proof before starting one episode. '
                            'Settle only actual lookups and return unused credit before considering the next episode.'),
            'fit': ('Exclude the entire target family. At each issued rate choose the ordering with highest '
                    'equal-task mean gain. Break ties by actual lookups and name.'),
            'gate': ('At the primary rate require a positive paired subject-and-case lower endpoint over the '
                     'trained blind order and over original CPO on every held-out family.')}
    return plan, reference, inputs


def reconstruct(inputs, corpus, reference):
    refs, bbh_inputs, mmlu_inputs = inputs
    bbh_settings, bbh_panels, bbh_reference = bbh_inputs
    search_cap = bbh_reference['plan']['conditions'][routing.transfer.BASE]['searchCap']
    bbh = routing.archive_episodes(bbh_panels, bbh_settings, search_cap, bbh_reference['panels'])
    design, mmlu_settings, stages, mmlu_reference = mmlu_inputs
    mmlu = routing.archive_episodes([panel for panels in stages.values() for panel in panels], mmlu_settings,
                                    design['baseSearchCap'], {key: panel for stage in mmlu_reference.values()
                                                               for key, panel in stage['panels'].items()})
    families = {**{name: {subject: group for subject, group in bbh.items() if subject.startswith(name + '-')}
                   for name in ('bbh', 'lmentry')}, 'mmlu': mmlu,
                'promptolution': routing.promptolution_episodes(corpus, refs[routing.CAP_REPORT])}
    for name, subjects in families.items():
        if routing.measure(subjects, routing.ALWAYS)[0] != reference['families'][name]['unconditional']:
            raise ValueError('The unconditional fallback differs from its published receipt')
    proof_rows = {name: settings['schedule']['qualificationRowsPerCycle'] + settings['schedule']['maximumExtensionRows']
                  for name, settings in (('bbh', bbh_settings), ('lmentry', bbh_settings), ('mmlu', mmlu_settings))}
    proof_rows['promptolution'] = routing.episode.ADMISSION
    return {name: {subject: {**group, 'quote': routing.CAP + 2 * proof_rows[name]} for subject, group in subjects.items()}
            for name, subjects in families.items()}


def order(items, policy):
    if policy in BLIND:
        return sorted(items, key=lambda item: digest((BLIND[policy], item.key)))
    keys = {PAID[0]: lambda item: Fraction(item.incumbentPasses, item.incumbentReads),
            PAID[1]: lambda item: item.paidGrades, PAID[2]: lambda item: -item.pairedWins}
    evidence = keys[policy]
    return sorted(items, key=lambda item: (evidence(item), digest(item.key)))


def fund(items, issued, quote, settle):
    """Call the settlement callback only after its maximum cost fits the remaining credit."""
    if type(issued) is not int or issued < 0 or type(quote) is not int or quote <= 0:
        raise ValueError('Use a nonnegative whole lookup budget and a positive reservation')
    receipts = []
    remaining = issued
    for item in items:
        if remaining < quote:
            break
        remaining -= quote
        paid, votes = settle(item)
        if type(paid) is not int or not 0 <= paid <= quote:
            raise ValueError('A fallback exceeded its validation and proof reservation')
        receipts.append((item.key, paid, votes))
        remaining += quote - paid
    return receipts, remaining


def measure(groups, policy, rate):
    totals, details, votes = Counter(), {}, {}
    for name, rows in groups.items():
        items = rows['opportunities']
        budget = len(items) * rate
        receipts, remaining = fund(order(items, policy), budget, rows['quote'],
                                   lambda item: (item.addedLookups, item.deltas))
        changes = [0] * len(rows['held'])
        for _, _, realized in receipts:
            changes = [a + b for a, b in zip(changes, realized, strict=True)]
        card = {'eligibleEpisodes': len(items), 'activations': len(receipts), 'issuedLookups': budget,
                'addedLookups': budget - remaining, 'addedPasses': sum(changes), 'unusedLookups': remaining}
        totals.update(card)
        details[name] = {**card, 'reservation': rows['quote'], 'settlementSha256': digest(receipts)}
        votes[name] = {'deltas': changes, 'decisionsPerCase': rows['decisionsPerCase']}
    gain = sum(Fraction(sum(row['deltas']), len(row['deltas']) * row['decisionsPerCase'])
               for row in votes.values()) / len(votes)
    return {**totals, 'macroAccuracyGain': str(gain)}, details, votes


def fit(training, policies, rate):
    ranked = []
    for policy in policies:
        result, _, _ = measure(training, policy, rate)
        ranked.append((-Fraction(result['macroAccuracyGain']), result['addedLookups'], policy))
    return min(ranked)[-1]


def paired_ranges(plan, routed, compared=None):
    votes = {subject: {'decisionsPerCase': row['decisionsPerCase'], 'cases': {'paid': row['deltas'],
                        'control': compared[subject]['deltas'] if compared else [0] * len(row['deltas'])}}
             for subject, row in routed.items()}
    with patch.object(routing.paired, 'BASELINE', 'control'):
        return routing.paired.paired_ranges(votes, 'paid', plan)


def compare(plan, families):
    report = {}
    for target, held in families.items():
        training = {subject: rows for name, groups in families.items() if name != target for subject, rows in groups.items()}
        stages = {}
        for rate in plan['issuedLookupsPerEligibleEpisode']:
            paid, blind = (fit(training, policies, rate) for policies in (PAID, BLIND))
            winner, paid_detail, paid_votes = measure(held, paid, rate)
            control, blind_detail, blind_votes = measure(held, blind, rate)
            comparisons = {'againstBlind': paired_ranges(plan, paid_votes, blind_votes),
                           'againstOriginalCPO': paired_ranges(plan, paid_votes)}
            passed = all(item['subjectsAndCases']['interval95PercentagePoints'][0] > 0 for item in comparisons.values())
            stages[rate] = {'paidOrdering': paid, 'blindOrdering': blind, 'paid': winner, 'blind': control,
                            'paidTasks': paid_detail, 'blindTasks': blind_detail, **comparisons, 'passed': passed}
        report[target] = {'trainingSubjects': sorted(training), 'heldOutSubjects': sorted(held), 'points': stages}
    return report


def execute(plan, reference, inputs, corpus):
    families = reconstruct(inputs, corpus, reference)
    report = compare(plan, families)
    return {'plan': plan, 'planSha256': digest(plan), 'families': report,
            'qualifies': all(row['points'][PRIMARY]['passed'] for row in report.values()), 'newProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, reference, inputs = prepare()
    seal = digest(plan)
    if args.corpus is None and args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.corpus is None or args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the pinned archive, current seal, and a fresh report path')
    result = execute(plan, reference, inputs, routing.episode.load_corpus(args.corpus.read_bytes()))
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
