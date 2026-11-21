"""Test whether paid validation can route the bounded fallback across families."""

import argparse
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import prompteval_mmlu_witness_fallback as mmlu, prompteval_witness_fallback as transfer
from benchmarks import prompteval_witness_tie_budget as paired, promptolution_witness_episode as episode
from benchmarks import witness_fallback_caps as capped
from cpo._contract import digest
from cpo.halving import HalvingSearch


ROOT = episode.ROOT
FAMILIES = ('bbh', 'lmentry', 'mmlu', 'promptolution')
CAP = 16
NEVER, ALWAYS = 'never-fallback', 'every-eligible-fallback'
PAID_RULES = {**{f'incumbent-at-most-{x}%-pass': ('passPercent', x) for x in (30, 50, 70)},
              **{f'at-most-{x}-paid-grades': ('paidGrades', x) for x in (12, 16, 20, 24)},
              'at-least-one-paired-win': ('pairedWins', 1)}
BLIND_RULES = {f'blind-{x}%': x for x in range(10, 100, 10)}
CAP_REPORT = 'docs/witness-fallback-caps-results-v1.json'
MMLU_REPORT = 'docs/prompteval-mmlu-witness-fallback-results-v1.json'
REFERENCES = {CAP_REPORT: '49732022e1f778ca5bdf28dee1fd51f48fe9457d5b49131328527d249c27ba5c',
              MMLU_REPORT: '1643f16c3e013f96b995c0668008a114f3b35767c3e682d2cf65948ebbfb704f'}


@dataclass(frozen=True)
class Opportunity:
    key: tuple
    incumbentPasses: int
    incumbentReads: int
    paidGrades: int
    pairedWins: int
    deltas: tuple[int, ...]
    addedLookups: int


def prepare():
    refs = {}
    for name, expected in REFERENCES.items():
        raw = (ROOT / name).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError('Use the published MMLU and bounded fallback receipts')
        refs[name] = json.loads(raw)
    transfer_plan, inputs, panels, reference = transfer.prepare()
    mmlu_plan, mmlu_inputs, cohorts, mmlu_reference = mmlu.prepare()
    saved = refs[MMLU_REPORT]
    if saved['planSha256'] != digest(mmlu_plan):
        raise ValueError('The MMLU replay differs from its published source')
    paths = (Path(__file__).resolve(), Path(transfer.__file__), Path(capped.__file__), Path(episode.__file__),
             Path(mmlu.__file__), Path(paired.__file__), ROOT / 'cpo/halving/__init__.py')
    plan = {'protocol': 'witness-fallback-paid-routing-v1', 'references': REFERENCES,
            'transferPlanSha256': digest(transfer_plan), 'mmluPlanSha256': digest(mmlu_plan),
            'sourceSha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in paths},
            'promptolutionArchiveSha256': episode.CORPUS_SHA, 'families': FAMILIES,
            'paidRules': PAID_RULES, 'blindRules': BLIND_RULES, 'fallbackCap': CAP,
            'trainingLookupLimitPercent': 50, 'pairedCaseDraws': 4096, 'resamplingSeed': 20261121,
            'fit': ('Hold out an entire benchmark family. Select the rule with highest equal-task mean gain on the '
                    'other families within half their unconditional extra cost. Break ties by cost then rule name.'),
            'gate': ('Every held-out family needs a positive paired lower endpoint over no fallback, at most half '
                     'the unconditional cost, and at least the equal-task gain of every affordable blind point.')}
    return plan, refs, (inputs, panels, reference), (mmlu_plan, mmlu_inputs, cohorts, mmlu_reference)


def opportunity(key, incumbent, paid, held, base, selected, extra, score):
    own = {case: passed for (prompt, case), passed in paid.items() if prompt == incumbent}
    if not own:
        raise ValueError('An eligible episode needs observed incumbent validation grades')
    wins = sum(prompt != incumbent and passed and own.get(case) is False for (prompt, case), passed in paid.items())
    return Opportunity(key, sum(own.values()), len(own), len(paid), wins,
                       tuple(int(score(selected, case)) - int(score(base, case)) for case in held), extra)


def archive_episodes(panels, inputs, cap, reference):
    groups = {}
    schedule, policy = inputs['schedule'], inputs['qualificationBank']
    active = {**schedule, 'evaluationLookupLimit': cap}
    for panel in panels:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        held = transfer.REPLAY.transfer.holdout(subject, len(matrix[0]))
        identity = tuple(panel['caseIDs'][i] for i in held) if 'caseIDs' in panel else panel['caseOrderSha256']
        group = groups.setdefault(subject, {'held': held, 'identity': identity, 'decisionsPerCase': 0, 'opportunities': []})
        if (group['held'], group['identity']) != (held, identity):
            raise ValueError('Both model panels must use the same aligned cases')
        group['decisionsPerCase'] += len(schedule['seeds'])
        baseline = Counter()

        def score(prompt, case):
            return matrix[int(prompt)][case] == '1'

        for seed in schedule['seeds']:
            start, layouts = transfer.REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, active)
            base, paid, _, grades, proof = transfer.play(matrix, held, start, layouts, active, policy, transfer.witness)
            baseline.update(holdoutPasses=sum(score(base, case) for case in held), paidLookups=paid)
            if proof:
                continue
            search = HalvingSearch(metric_limit=CAP, paid=grades)
            result, proof = capped.transfer_trial(matrix, held, start, layouts, active, policy, search)
            group['opportunities'].append(opportunity((subject, model, seed), start, grades, held, base, result,
                                                       search.evaluations + proof, score))
        expected = reference[f'{subject}/{model}'][transfer.BASE]
        if any(baseline[field] != expected[field] for field in ('holdoutPasses', 'paidLookups')):
            raise ValueError('The original witness path differs from its published costs or scores')
    return groups


def promptolution_episodes(corpus, receipt):
    plan = episode.prepare()
    result = {}
    for task, panel in corpus.items():
        matrix = panel['correctness']
        held = sorted(Random(f"{plan['holdoutSeed']}/{task}").sample(range(300), episode.HOLDOUT))
        rows, baseline = [], Counter()

        def score(prompt, case):
            return matrix[prompt][case] == '1'

        for seed in episode.SEEDS:
            layouts = episode.schedule(plan, task, seed, held)
            base, cost, trace = episode.play(matrix, layouts, seed, episode.CPO, set(held))
            baseline.update(holdoutPasses=sum(score(base, case) for case in held), paidLookups=cost['paidLookups'])
            if cost['admissions']:
                continue
            prior = dict(trace['search'])
            search = HalvingSearch(metric_limit=CAP, paid=prior)
            selected, proof = capped.promptolution_trial(matrix, layouts, seed, search)
            rows.append(opportunity(('promptolution', task, seed), episode.START, prior, held, base, selected,
                                    search.evaluations + proof, score))
        if baseline != receipt['baseline'][task]:
            raise ValueError('The Promptolution baseline differs from the published witness path')
        result[task] = {'held': held, 'decisionsPerCase': len(episode.SEEDS), 'opportunities': rows}
    return result


def accept(rule, item):
    if rule == NEVER or rule == ALWAYS:
        return rule == ALWAYS
    if rule in BLIND_RULES:
        return int(digest(item.key)[:8], 16) % 100 < BLIND_RULES[rule]
    kind, threshold = PAID_RULES[rule]
    if kind == 'pairedWins':
        return item.pairedWins >= threshold
    if kind == 'passPercent':
        return item.incumbentPasses * 100 <= threshold * item.incumbentReads
    return item.paidGrades <= threshold


def measure(groups, rule):
    votes, totals = {}, Counter()
    for name, group in groups.items():
        zeros = [0] * len(group['held'])
        observed = zeros.copy()
        for item in group['opportunities']:
            if accept(rule, item):
                totals.update(activations=1, addedLookups=item.addedLookups)
                observed = [a + b for a, b in zip(observed, item.deltas, strict=True)]
        totals['addedPasses'] += sum(observed)
        votes[name] = {'decisionsPerCase': group['decisionsPerCase'], 'cases': {NEVER: zeros, 'route': observed}}
    macro = sum(Fraction(sum(row['cases']['route']), len(row['cases']['route']) * row['decisionsPerCase'])
                for row in votes.values()) / len(votes)
    return {'activations': totals['activations'], 'addedLookups': totals['addedLookups'],
            'addedPasses': totals['addedPasses'], 'macroAccuracyGain': str(macro)}, votes


def fit(training, candidates, percent):
    allowance = measure(training, ALWAYS)[0]['addedLookups'] * percent // 100
    ranked = []
    for rule in candidates:
        measured, _ = measure(training, rule)
        if measured['addedLookups'] <= allowance:
            ranked.append((-Fraction(measured['macroAccuracyGain']), measured['addedLookups'], rule))
    return min(ranked)[-1], allowance


def cross_fit(plan, families):
    results = {}
    for name, holdout in families.items():
        training = {subject: unit for other, groups in families.items() if other != name for subject, unit in groups.items()}
        chosen, cost = fit(training, (NEVER, *PAID_RULES), plan['trainingLookupLimitPercent'])
        blind, _ = fit(training, (NEVER, *BLIND_RULES), plan['trainingLookupLimitPercent'])
        base, _ = measure(holdout, ALWAYS)
        routed, votes = measure(holdout, chosen)
        blind_result, _ = measure(holdout, blind)
        fair = []
        for rule in (NEVER, *BLIND_RULES):
            measured, _ = measure(holdout, rule)
            if measured['addedLookups'] <= routed['addedLookups']:
                fair.append((-Fraction(measured['macroAccuracyGain']), measured['addedLookups'], rule, measured))
        _, _, comparator, comparison = min(fair, key=lambda point: point[:3])
        with patch.object(paired, 'BASELINE', NEVER):
            ranges = paired.paired_ranges(votes, 'route', plan)
        passed = (ranges['subjectsAndCases']['interval95PercentagePoints'][0] > 0 and
                  routed['addedLookups'] * 100 <= base['addedLookups'] * plan['trainingLookupLimitPercent'] and
                  Fraction(routed['macroAccuracyGain']) >= Fraction(comparison['macroAccuracyGain']))
        results[name] = {'trainingSubjects': sorted(training), 'heldOutSubjects': sorted(holdout),
                         'trainingLookupAllowance': cost, 'paidRule': chosen, 'blindRule': blind,
                         'unconditional': base, 'routed': routed, 'trainedBlind': blind_result,
                         'hindsightAffordableBlind': {'rule': comparator, **comparison},
                         'pairedAgainstNoFallback': ranges, 'passed': passed}
    return results


def execute(plan, refs, bbh_inputs, mmlu_inputs, corpus):
    inputs, bbh_panels, bbh_reference = bbh_inputs
    cap = bbh_reference['plan']['conditions'][transfer.BASE]['searchCap']
    bbh = archive_episodes(bbh_panels, inputs, cap, bbh_reference['panels'])
    design, inputs, stages, reference = mmlu_inputs
    panels = [panel for items in stages.values() for panel in items]
    mmlu_groups = archive_episodes(panels, inputs, design['baseSearchCap'],
                                   {key: report for phase in reference.values() for key, report in phase['panels'].items()})
    cap_receipt = refs[CAP_REPORT]
    families = {**{name: {key: result for key, result in bbh.items() if key.startswith(name + '-')} for name in FAMILIES[:2]},
                'mmlu': mmlu_groups, 'promptolution': promptolution_episodes(corpus, cap_receipt)}
    audit = {subject: measure({subject: group}, ALWAYS)[0] for groups in families.values() for subject, group in groups.items()}
    if len(audit) != sum(map(len, families.values())):
        raise ValueError('Benchmark families must hold out disjoint task identities')
    for name in ('bbh', 'lmentry', 'gsm8k', 'sst5', 'mmlu'):
        groups = families['promptolution'] if name in ('gsm8k', 'sst5') else families[name]
        group = {name: groups[name]} if name in ('gsm8k', 'sst5') else groups
        stats, _ = measure(group, ALWAYS)
        if name == 'mmlu':
            mmlu_receipt = refs[MMLU_REPORT]
            old, candidate = (mmlu_receipt['pooled']['totals'][method] for method in (mmlu.BASE, mmlu.CANDIDATE))
            values = {'addedLookups': candidate['paidLookups'] - old['paidLookups'],
                      'addedPasses': candidate['holdoutPasses'] - old['holdoutPasses']}
        else:
            values = cap_receipt['fallbackDeltas'][name]['certified/16']
        if any(stats[key] != values[key] for key in ('addedLookups', 'addedPasses')):
            raise ValueError('The unconditional fallback failed to reproduce its published costs or gains')
    results = cross_fit(plan, families)
    return {'plan': plan, 'planSha256': digest(plan), 'qualifies': all(row['passed'] for row in results.values()),
            'families': results, 'unconditionalBySubject': audit, 'newProviderRequests': 0}


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
    result = execute(plan, *inputs, episode.load_corpus(args.corpus.read_bytes()))
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
