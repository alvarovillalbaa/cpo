"""Test a one-admission fallback after every witness cycle declined to nominate."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import promptolution_witness_episode as episode
from benchmarks import promptolution_witness_small_native as sensitivity
from cpo._contract import digest


CANDIDATE = 'witness-then-halving'
HALVING = episode.HALVING[0]
REFERENCE = 'docs/promptolution-witness-small-native-results-v1.json'
REFERENCE_SHA = 'dae0668544760478ec45b1dd64270c03f13ba6a7766e5dcb398c0a0686a0e92a'
EXTRA_HALVING = {f'successive-halving/cap-{cap}/one-admission': {'validationRows': episode.VALIDATION, 'searchCap': cap}
                 for cap in (6, 10, 12, 14, 18, 20, 24)}


def prepare():
    previous = sensitivity.prepare()
    receipt = (episode.ROOT / REFERENCE).read_bytes()
    if sha256(receipt).hexdigest() != REFERENCE_SHA or json.loads(receipt)['planSha256'] != digest(previous):
        raise ValueError('Load the published narrower-native transfer evidence')
    source = Path(__file__).resolve().relative_to(episode.ROOT).as_posix()
    return {**previous, 'protocol': 'cpo-promptolution-witness-fallback-v1', 'candidate': CANDIDATE,
            'parentPlanSha256': digest(previous), 'parentReportSha256': REFERENCE_SHA,
            'sourceSha256': {**previous['sourceSha256'], source: sha256(Path(__file__).read_bytes()).hexdigest()},
            'controlSettings': {**previous['controlSettings'], **EXTRA_HALVING},
            'fallback': HALVING, 'maxAdmissions': 1,
            'scope': ('Only if every witness cycle returns no nominee, run cap-8 Successive Halving in the same '
                      'enrolled cycle order, including its one paired proof. Attribute each distinct grade once.'),
            'decisionRule': ('Require a positive case-bootstrap lower endpoint against the strongest affordable '
                             'fixed GEPA or Halving setting, retain-start, or the prior witness arm. Require this '
                             'separately on each task and pooled. Reselect the control on each draw.')}


def combine(witness, fallback):
    """Reuse exact archived validation observations when the fallback is eligible."""
    _, initial, first = witness
    if initial['admissions']:
        return witness
    selected, reserve, second = fallback()
    prior = dict(first['search'])
    other = dict(second['search'])
    if first['admission'] or reserve['admissions'] > 1 or any(prior[key] != other[key] for key in prior.keys() & other):
        raise ValueError('The fallback must use immutable search grades and the unused admission')
    paid = {**prior, **other}
    if len(paid) - len(prior) > episode.CYCLES * episode.CONTROLS[HALVING]['searchCap']:
        raise ValueError('Fallback search exceeded its full episode cap')
    outcome = {**reserve, 'searchLookups': len(paid), 'admissionLookups': len(second['admission']),
               'paidLookups': len(paid) + len(second['admission']),
               'occupiedCycles': initial['occupiedCycles'] + reserve['occupiedCycles']}
    return selected, outcome, {**second, 'search': list(paid.items()), 'witnessDecisions': first['decisions'],
                               'reusedSearchLookups': len(prior.keys() & other)}


def execute(plan, corpus):
    control_keys = plan['controlSettings']
    reference = json.loads((episode.ROOT / REFERENCE).read_bytes())
    tasks = {id(panel['correctness']): task for task, panel in corpus.items()}
    evidence = {task: defaultdict(Counter) for task in tasks.values()}
    play, compare = episode.play, episode.compare
    extra = (*sensitivity.SMALL, *EXTRA_HALVING)
    knobs = {'CONTROLS': control_keys, 'GEPA': (*episode.GEPA, *sensitivity.SMALL),
             'HALVING': (*episode.HALVING, *EXTRA_HALVING), 'ARMS': (*episode.ARMS, *extra, CANDIDATE)}

    def compare_hybrid(current, panels, controls):
        controls = (*controls, episode.CPO) if episode.RETAIN in controls else controls
        with patch.object(episode, 'CPO', CANDIDATE):
            return compare(current, panels, controls)

    def run(matrix, layouts, seed, method, held):
        if method != CANDIDATE:
            return play(matrix, layouts, seed, method, held)
        first = play(matrix, layouts, seed, episode.CPO, held)
        control = play(matrix, layouts, seed, HALVING, held)
        selected, counts, trace = combine(first, lambda: control)
        counts['fallbacks'] = int(not first[1]['admissions'])
        counts['reusedSearchLookups'] = trace.get('reusedSearchLookups', 0)

        def holdout(prompt):
            return sum(matrix[prompt][case] == '1' for case in held)

        end = first[2]['decisions'][-1]
        evidence[tasks[id(matrix)]][end].update(
            episodes=1, originalMinusHalving=holdout(first[0]) - holdout(control[0]),
            hybridMinusOriginal=holdout(selected) - holdout(first[0]),
            extraLookups=counts['paidLookups'] - first[1]['paidLookups'],
            fallbackNominations=counts['admissions'] if not first[1]['admissions'] else 0,
            fallbackPromotions=counts['promotions'] if not first[1]['admissions'] else 0,
            reusedLookups=counts['reusedSearchLookups'])
        return selected, counts, trace

    with patch.multiple(episode, **knobs, play=run, compare=compare_hybrid):
        report = episode.execute(plan, corpus)
    for task, panel in report['tasks'].items():
        for method, expected in reference['tasks'][task]['arms'].items():
            if panel['arms'][method] != expected:
                raise ValueError('The fallback study changed a published comparison trace or score')
    return {**report, 'attributionByWitnessOutcome': evidence}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan = prepare()
    seal = digest(plan)
    if args.corpus is None and args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.corpus is None or args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the pinned archive, current seal, and a fresh report path')
    report = execute(plan, episode.load_corpus(args.corpus.read_bytes()))
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
