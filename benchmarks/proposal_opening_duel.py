"""Use paid validation witnesses to order CPO's precomputed opening pair."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import expected_cost_proposal_replay as source
from benchmarks.case_difficulty_allocation import checked_file
from cpo import ProposalPair
from cpo import expected_cost_proposal_cycle as cycle
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
PARENT = 'a340fc3fc1ea6757a691ad594a54a13f500adf2d22328db65707e48b9c1289e5'
CAP = 72
POLICIES = ('reverse', 'miss', 'paired', 'matched')
CAPS = (CAP, *POLICIES, 171)


def opening_order(initial, validation, evaluate, pair, *, policy):
    if policy == 'reverse':
        return ProposalPair(pair.repair, pair.rewrite), 0

    groups = {False: [], True: []}
    for row in validation:
        groups[evaluate(initial, row).passed].append(row)
    if not groups[False]:
        return pair, 0
    strata = [groups[False]]
    if policy != 'miss' and groups[True]:
        strata.append(groups[True])

    def score(prompt):
        return sum(len(rows) * evaluate(prompt, rows[0]).passed for rows in strata)

    first, second = score(pair.rewrite), score(pair.repair)
    if second > first and policy != 'matched':
        pair = ProposalPair(pair.repair, pair.rewrite)
    return pair, 2 * len(strata)


def engine(policy, counters):
    core = cycle.search

    def run(initial, train, validation, evaluate, propose, *, opening_pair, metric_limit, **options):
        maximum_probes = {'reverse': 0, 'miss': 2, 'paired': 4, 'matched': 4}[policy]
        if maximum_probes and metric_limit < 2 * len(validation) + maximum_probes:
            raise ValueError('The opening screen requires room for a complete validation challenge')
        ledger = {}
        search_reads = set()

        def observe(prompt, row):
            key = prompt, row.id
            if key not in ledger:
                if len(ledger) >= metric_limit:
                    raise ValueError('The opening search exceeded the hard lookup ceiling')
                ledger[key] = evaluate(prompt, row)
            return ledger[key]

        def search_observe(prompt, row):
            search_reads.add((prompt, row.id))
            return observe(prompt, row)

        chosen, reserve = opening_order(initial, validation, observe, opening_pair, policy=policy)
        result = core(initial, train, validation, search_observe, propose, opening_pair=chosen,
                      metric_limit=metric_limit - reserve, **options)
        if len(search_reads) != result.evaluations:
            raise ValueError('The engine lookup accounting drifted')
        counters.update(openingSwaps=int(chosen != opening_pair), openingProbeLookups=reserve,
                        probesReused=reserve - len(ledger.keys() - search_reads))
        return replace(result, evaluations=len(ledger))

    return run


def prepare():
    parent, phases = source.prepare()
    previous = checked_file('docs/expected-cost-proposal-replay-results-v1.json', PARENT)
    if digest(parent) != previous['designSha256']:
        raise ValueError('The previous proposal comparison differs from its seal')
    paths = ('benchmarks/proposal_opening_duel.py', 'benchmarks/expected_cost_proposal_replay.py',
             'cpo/expected_cost_proposal_cycle.py', 'cpo/optimizer.py')
    design = {'protocol': 'cpo-proposal-opening-duel-v1', 'baselineDesignSha256': digest(parent),
              'baselineReportSha256': PARENT, 'searchCap': CAP, 'primary': 'paired', 'policies': POLICIES,
              'scope': ('Choose a first opening from paid incumbent-relative validation probes. Reserve the cost '
                        'of every opening probe, run the existing search, and qualify only its final nominee.'),
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}}
    return design, phases, previous['results']


def replay(plan, panels, references, previous):
    original = source.proposal_episode

    def episode(matrix, start, layouts, settings):
        policy = settings['evaluationLookupLimit']
        if policy not in POLICIES:
            return original(matrix, start, layouts, settings)
        total, trace = Counter(), []
        incumbent = start
        settings = {**settings, 'evaluationLookupLimit': CAP}
        with patch.object(cycle, 'search', engine(policy, total)):
            for layout in layouts:
                result, _, search_hash = source.archive_step(matrix, incumbent, layout, settings)
                replies = () if result.qualification is None else result.qualification.observations
                total.update(searchLookups=result.search.evaluations, expected=len(replies),
                             promotions=int(result.promoted), reflections=result.search.reflections)
                trace.append((incumbent, result.search.prompt, result.prompt, search_hash,
                              [(item.prompt, item.row_id, item.repeat, item.passed) for item in replies]))
                incumbent = result.prompt
        return int(incumbent), total, trace

    with patch.multiple(source, CAPS=CAPS, proposal_episode=episode):
        report = source.measure_phase(plan, panels, references)
    for name, points in report['panels'].items():
        if any(points[label] != previous[name][label] for label in (*source.continuous.GEPA, 'cpo-72', 'cpo-171')):
            raise ValueError(f'The unchanged budget controls differ from their published receipts for {name}')
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, phases, previous = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for plan, *_ in phases.values()):
        cli.error('Use pinned GEPA 0.1.4')
    report = {'design': design, 'designSha256': seal, 'results': {
        phase: replay(*inputs, previous[phase]['panels']) for phase, inputs in phases.items()}}
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
