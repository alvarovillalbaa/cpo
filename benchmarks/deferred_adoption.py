"""Keep the start fixed during acquisition and defer a single deployment decision."""

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import case_difficulty_allocation as parent
from benchmarks import final_start_reconciliation as prior
from benchmarks import paid_start_retention as retention
from benchmarks import routed_score_allocation as route
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
GUARD_REPORT = '6945e73db464beb05a19dd3cdc10c054f810661d4dacdb91b99c5e1d3587175d'
METHODS = ('defer-reconfirm', 'defer-paid-proof')
CONTROLS = ('strict', *route.GEPA, 'retain-start')


@dataclass(frozen=True)
class ApprovedPrompt:
    prompt: str
    lower_gain: int
    reads: int
    cycle: int


def best_approved(approved, start):
    winner = max(approved, key=lambda row: (row.lower_gain, -row.reads, row.cycle), default=None)
    return winner.prompt if winner is not None else start


def episode(matrix, held, seed, plan, start, *, reconfirm):
    split = route.ties.split
    run = split.run
    cycle = split.fixed_pool_cycle
    archive = split.archive.archive
    terminal = plan['schedule']['cycles'] - 1
    current, approved, evidence = 0, [], []
    audit = Counter()

    def capture(*args):
        original = cycle.run_fixed_pool_cycle

        def nominate(incumbent, history, attempted, policy):
            nonlocal current
            current = len(history)
            if incumbent != start or attempted:
                raise ValueError('The trajectory must compare with the original prompt until deployment')
            if reconfirm and current == terminal and approved:
                audit.update(finalRechecks=1)
                return best_approved(approved, start)
            return None

        def fresh(incumbent, *args, **kwargs):
            result = original(incumbent, *args, **kwargs)
            if result.promoted:
                proof = result.qualification
                if proof.lower_gain < 1:
                    raise ValueError('An archived candidate needs a paid strict gain')
                approved.append(ApprovedPrompt(result.prompt, proof.lower_gain, len(proof.observations), current))
                audit.update(approvedEarly=int(current < terminal), approvedFreshFinal=int(current == terminal))
            if current == terminal and reconfirm:
                return result
            deployment = best_approved(approved, start) if current == terminal else start
            evidence.append({'cycle': current, 'qualified': result.prompt, 'deployment': deployment})
            return prior.ReconciledCycle(result.search, result.qualification, deployment)

        with patch.object(archive, 'nominate', nominate), patch.object(cycle, 'run_fixed_pool_cycle', fresh):
            return run(*args)

    with patch.object(split, 'run', capture):
        totals, trace = route.run(matrix, held, seed, plan, start, 'strict')
    if any(row['decision']['selected'] != start for row in trace[:-1]):
        raise ValueError('Early candidates must remain undeployed')
    if reconfirm:
        audit.update(finalRechecksPassed=int(trace[-1]['decision']['archivePromoted']))
    trace[-1]['deferredAdoption'] = evidence
    totals.update(audit)
    return totals, trace


def prepare():
    original, inputs = parent.prepare()
    parent.checked_file('docs/reserved-regression-guard-results-v1.json', GUARD_REPORT)
    known = parent.checked_file('docs/priced-gate-reachability-results-v1.json', retention.AUDIT_REPORT)
    paths = ('benchmarks/deferred_adoption.py', 'benchmarks/final_start_reconciliation.py',
             'benchmarks/archive_complementarity_transfer.py', 'benchmarks/routed_start_protection.py',
             'benchmarks/routed_witness_split.py', 'benchmarks/prompteval_archive_cycles.py', 'cpo/fixed_pool_cycle.py')
    design = {'protocol': 'cpo-deferred-adoption-v1', 'parentDesignSha256': digest(original),
              'guardReportSha256': GUARD_REPORT, 'costedAuditReportSha256': retention.AUDIT_REPORT,
              'methods': METHODS, 'primary': METHODS[0], 'controls': CONTROLS,
              'rank': ('certified lower gain', 'fewer qualification reads', 'later cycle'),
              'scope': ('Keep the starting prompt through the first three cycles. Bank candidates that improve '
                        'validation and qualification with neither qualification half regressing. Reconfirm '
                        'the best banked candidate in the original final archive slot, or '
                        'choose the best paid proof after the final fresh search.'),
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}}
    return design, {key: (*item, known['results'][key]['panels']) for key, item in inputs.items()}


def measure(panels, references, plan, known):
    labels = (*CONTROLS, *METHODS)
    totals = {key: Counter() for key in labels}
    results, vectors, holdouts = {}, {key: {} for key in METHODS}, {}
    for panel in panels:
        subject, model, matrix = (panel[field] for field in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        uncertainty = route.CONFIRMATION.uncertainty
        held = route.CONFIRMATION.holdout(subject, len(matrix[0]))
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('Both model splits must share the holdout cases')
        starts = route.ties.costs.retained_prompts(matrix, held, plan['schedule'])
        finals, points = {label: [] for label in labels}, {}
        for label in route.GEPA:
            mode, cap = label.split('/')
            finals[label], points[label] = uncertainty.final_prompts(matrix, held, plan['schedule'], plan, mode, int(cap))
        finals['retain-start'] = starts
        points['retain-start'] = {'holdoutPasses': sum(uncertainty.case_totals(matrix, held, starts).values()),
                                  'paidLookups': 0}

        counts, traces = ({arm: factory() for arm in ('strict', *METHODS)} for factory in (Counter, list))
        for index, (seed, start) in enumerate(zip(plan['schedule']['seeds'], starts, strict=True)):
            baseline, historical = route.run(matrix, held, seed, plan, str(start), 'strict')
            expected = known[name]['episodes'][index]
            if seed != expected['seed'] or baseline['searchPaid'] + baseline['qualificationPaid'] != expected['cpoPaidLookups']:
                raise ValueError('The measured baseline must match the costed audit')
            actual = historical[-1]['decision']['selected']
            counts['strict'].update(baseline)
            traces['strict'].append(historical)
            finals['strict'].append(int(actual))
            controls = {label: sum(matrix[finals[label][index]][case] == '1' for case in held) for label in route.PRIMARY}
            for label in METHODS:
                costs, trace = episode(matrix, held, seed, plan, str(start), reconfirm=label == METHODS[0])
                counts[label].update(costs)
                selected = trace[-1]['decision']['selected']
                recovery = Counter(f'recovered/{category}' for arm, category in expected['firstBound'].items()
                                   if costs['holdoutPasses'] >= controls[arm])
                counts[label].update(recovery)
                counts[label].update(changedFinal=int(selected != actual),
                                     improved=int(costs['holdoutPasses'] > baseline['holdoutPasses']),
                                     regressed=int(costs['holdoutPasses'] < baseline['holdoutPasses']))
                traces[label].append(trace)
                finals[label].append(int(selected))
        for label, count in counts.items():
            points[label] = {**count, 'paidLookups': count['searchPaid'] + count['qualificationPaid'],
                             'traceSha256': digest(traces[label])}
        outcomes = {label: uncertainty.case_totals(matrix, held, choices) for label, choices in finals.items()}
        for label, point in points.items():
            if label in CONTROLS and any(key in references[name][label] and point[key] != references[name][label][key]
                                         for key in parent.FIELDS):
                raise ValueError(f'Published baseline differs: {name}/{label}')
            if sum(outcomes[label].values()) != point['holdoutPasses']:
                raise ValueError('Holdout totals differ from the selected prompts')
            totals[label].update({key: value for key, value in point.items() if type(value) is int})
        for label, groups in vectors.items():
            margins = groups.setdefault(subject, {control: [0] * len(held) for control in CONTROLS})
            for control, values in margins.items():
                for i, case in enumerate(held):
                    values[i] += outcomes[label][case] - outcomes[control][case]
        results[name] = points

    comparisons = {}
    for label, groups in vectors.items():
        ranges = route.transfer.ranges(groups, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
        cost = totals[label]['paidLookups']
        savings = {control: 1 - cost / totals[control]['paidLookups'] for control in route.GEPA}
        threshold = 100 - plan['minimumLookupSavingPercent']
        enough = all(100 * cost <= threshold * totals[control]['paidLookups'] for control in route.PRIMARY)
        low, high = ranges['joint']
        gate = 'failed' if not enough or high < 0 else 'passed' if low >= 0 else 'inconclusive'
        comparisons[label] = {'gate': gate, 'lookupSavings': savings, 'caseRanges': ranges}
    return {'totals': totals, 'comparisons': comparisons, 'panels': results}


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
