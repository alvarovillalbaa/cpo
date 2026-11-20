"""Locate affordable direct challenger paths in the measured CPO search ledger."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import case_difficulty_allocation as parent
from benchmarks import paid_start_retention as retention
from benchmarks import priced_gate_reachability as audit
from benchmarks import routed_score_allocation as route
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
DEFERRED_REPORT = 'd03337b32884058a3a7c54d360dc5b1b2d19f5aa1020741ac4a4be45ce96e82d'
STAGES = ('deployed-earlier', 'fully-scored-other-nominee', 'paid-gain-witness', 'read-without-witness',
          'outside-wide-roster', 'unread', 'archive-preempted', 'blocked-against-current', 'multiple-moves')


def trace_search(matrix, held, seed, plan, start):
    split = route.ties.split
    archive = split.archive.archive
    cycle = split.fixed_pool_cycle
    run = split.run
    journal, routes = [], []

    def capture(*args):
        nominate, original, selector = archive.nominate, cycle.run_fixed_pool_cycle, split.routed_selection

        def begin(incumbent, history, attempted, policy):
            if len(history) != len(journal):
                raise ValueError('Cycle history and callback ledger disagree')
            journal.append({})
            routes.append('archive')
            return nominate(incumbent, history, attempted, policy)

        def fresh(incumbent, candidates, rows, cohort, evaluate, **kwargs):
            def observe(prompt, row):
                reply = evaluate(prompt, row)
                journal[-1][prompt, int(row.id)] = reply.passed
                return reply

            return original(incumbent, candidates, rows, cohort, observe, **kwargs)

        def select(*args, **kwargs):
            counts = kwargs['audit']
            wide, balanced = counts['wideCycles'], counts['balancedCycles']
            result = selector(*args, **kwargs)
            routes[-1] = ('balanced' if counts['balancedCycles'] > balanced else
                          'split-witness' if counts['wideCycles'] > wide else 'deferred')
            return result

        with (patch.object(archive, 'nominate', begin), patch.object(cycle, 'run_fixed_pool_cycle', fresh),
              patch.object(split, 'routed_selection', select)):
            return run(*args)

    with patch.object(split, 'run', capture):
        counts, trace = route.run(matrix, held, seed, plan, start, 'strict')
    for cycle_trace, reads in zip(trace, journal, strict=True):
        measured = digest([(p, case, passed) for (p, case), passed in reads.items()])
        if cycle_trace['decision']['searchSha256'] != measured:
            raise ValueError('The intercepted reads differ from the archived search trace')
    if (sum(map(len, journal)) != counts['searchLogical']
            or len({key for reads in journal for key in reads}) != counts['searchPaid']):
        raise ValueError('Recorded logical or paid validation lookup counts differ from the control')
    return counts, trace, journal, routes


def gain(matrix, old, new, cases):
    return sum((matrix[int(new)][case] == '1') - (matrix[int(old)][case] == '1') for case in cases)


def eligible(matrix, start, incumbent, challenger, layout):
    qualification = layout['qualify']
    half = len(qualification) // 2
    return (gain(matrix, incumbent, challenger, layout['validation']) > 0
            and gain(matrix, incumbent, challenger, qualification) > 0
            and (incumbent != start or all(gain(matrix, start, challenger, group) >= 0
                                          for group in (qualification[:half], qualification[half:]))))


def classify(matrix, start, candidate, position, layout, step, paid, prior, route_name, *, deployed=False):
    incumbent = step['incumbent']
    observed = {case: reply for (prompt, case), reply in paid.items() if prompt == candidate}
    witnessed = any(passed and paid.get((incumbent, case), prior.get((incumbent, case))) is False
                    for case, passed in observed.items())
    if deployed or step['selected'] == candidate:
        stage = STAGES[0]
    elif not eligible(matrix, start, incumbent, candidate, layout):
        stage = 'blocked-against-current'
    elif step['archivePromoted']:
        stage = 'archive-preempted'
    elif step['challenger'] == candidate:
        raise ValueError('A fresh nominee passing both recorded gates must have deployed')
    elif len(observed) == len(layout['validation']):
        stage = 'fully-scored-other-nominee'
    elif witnessed:
        stage = 'paid-gain-witness'
    elif observed:
        stage = 'read-without-witness'
    elif route_name == 'balanced' and position >= 6:
        stage = 'outside-wide-roster'
    else:
        stage = 'unread'
    return {'stage': stage, 'route': route_name, 'position': position + 1,
            'paidReads': len(observed), 'paidPasses': sum(observed.values()), 'witnessed': witnessed}


def prepare():
    design, inputs = parent.prepare()
    parent.checked_file('docs/deferred-adoption-results-v1.json', DEFERRED_REPORT)
    known = parent.checked_file('docs/priced-gate-reachability-results-v1.json', retention.AUDIT_REPORT)
    sources = ('benchmarks/affordable_challenger_attribution.py', 'benchmarks/priced_gate_reachability.py',
               'benchmarks/archive_complementarity_transfer.py', 'benchmarks/routed_start_protection.py',
               'benchmarks/routed_witness_split.py', 'benchmarks/finalist_screen_budget.py')
    manifest = {'protocol': 'cpo-affordable-challenger-attribution-v1', 'parentDesignSha256': digest(design),
                'deferredReportSha256': DEFERRED_REPORT, 'costedAuditReportSha256': retention.AUDIT_REPORT,
                'stagesInOrder': STAGES, 'controls': audit.CONTROLS,
                'scope': ('Evaluate every single-move matching prompt from the start on the earlier 85 '
                          'full-panel-price losses. Attribute the furthest reached candidate on the actual '
                          'CPO path using its paid validation evidence, its gates, and its final selection.'),
                'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in sources}}
    return manifest, {name: (*item, known['results'][name]['panels']) for name, item in inputs.items()}


def measure(panels, references, plan, expected):
    results, losses, opportunities = {}, Counter(), Counter()
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = route.CONFIRMATION.holdout(subject, len(matrix[0]))
        uncertainty = route.CONFIRMATION.uncertainty
        controls = {}
        for label in route.PRIMARY:
            mode, cap = label.split('/')
            controls[label], point = uncertainty.final_prompts(matrix, held, plan['schedule'], plan, mode, int(cap))
            route.ties.frontier.expect_reference(point, references[name][label])

        traces, examples, totals = [], [], Counter()
        for index, seed in enumerate(plan['schedule']['seeds']):
            start, layouts = audit.gepa.smaller.narrow_schedule(*audit.gepa.continuous.schedule(
                len(matrix[0]), len(matrix), held, seed, plan['schedule']), plan['validationRows'])
            used, trace, paid, modes = trace_search(matrix, held, seed, plan, start)
            budget = used['searchPaid'] + used['qualificationPaid']
            totals.update(holdoutPasses=used['holdoutPasses'], paidLookups=budget)
            traces.append(trace)
            historical = expected[name]['episodes'][index]
            if historical['seed'] != seed or historical['cpoPaidLookups'] != budget:
                raise ValueError('Replayed spend does not match the costed audit')
            for control, bound in historical['firstBound'].items():
                if bound != audit.FRESH_DIRECT:
                    continue
                target_score = sum(matrix[controls[control][index]][case] == '1' for case in held)
                direct, previous_paid = [], {}
                deployed = {row['decision']['selected'] for row in trace[:-1]}
                for i, (layout, cycle, calls, mode) in enumerate(zip(layouts, trace, paid, modes, strict=True)):
                    charge = 2 * (len(layout['qualify']) + len(layout['validation']))
                    if charge > budget:
                        continue
                    for pos, prompt in enumerate(layout['alternatives']):
                        if (eligible(matrix, start, start, prompt, layout)
                                and sum(matrix[int(prompt)][case] == '1' for case in held) >= target_score):
                            point = classify(matrix, start, prompt, pos, layout, cycle['decision'], calls,
                                             previous_paid, mode, deployed=prompt in deployed)
                            direct.append({'prompt': prompt, 'cycle': i, **point})
                    previous_paid.update(calls)
                direct_price = historical['minimumMatchingPrices'][f'{control}/{audit.FRESH_DIRECT}']
                if bool(direct) != (direct_price == 2 * (plan['validationRows']
                                                        + plan['schedule']['qualificationRowsPerCycle'])):
                    raise ValueError('Single-move targets disagree with the published full-panel price')
                stage = min((row['stage'] for row in direct), key=STAGES.index, default='multiple-moves')
                examples.append({'seed': seed, 'control': control, 'furthestStage': stage, 'targets': direct})
                losses[stage] += 1
                opportunities.update(row['stage'] for row in direct)
        point = {**totals, 'traceSha256': digest(traces)}
        route.ties.frontier.expect_reference(point, references[name]['strict'])
        results[name] = {'originalCpo': point, 'losingComparisons': examples}
    return {'lossesByFurthestStage': losses, 'allMatchingTargetsByStage': opportunities, 'panels': results}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, inputs = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for _, _, plan, _ in inputs.values()):
        cli.error('Use pinned GEPA 0.1.4')
    results = {name: measure(*item) for name, item in inputs.items()}
    with args.out.open('x') as stream:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
