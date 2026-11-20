"""Find cheaper certificates for the same fresh paired qualification decision."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import case_difficulty_allocation as parent
from benchmarks import gepa_paid_cap_transfer as gepa
from benchmarks import routed_score_allocation as route
from cpo._contract import digest
from cpo.expected_qualification import certify_expected_qualification


ROOT = Path(__file__).resolve().parents[1]
TRANSFER = {
    'docs/late-miss-transfer-design-v1.json': 'c7279751761c4f5d7513be2630d007d1b85b7bebe1a26cdefb1b85e5122e3287',
    'docs/late-miss-transfer-results-v1.json': 'c41ebd6e1a09e0a17c220c1a021d308b99296888665c8230235cdc6d163b6b39',
    'benchmarks/data/late-miss-transfer-v1.json': '751ba960d8c8e8ed109316724a1fb0e988d2c841b7468cd8650b30228934f953',
}
METHODS = ('strict', *route.PRIMARY)


def run(matrix, held, seed, plan, start, label, *, ordered):
    split = route.ties.split
    cycle = split.fixed_pool_cycle
    validation, audit = {}, Counter()

    def proof(incumbent, challenger, rows, evaluate, **kwargs):
        rows = tuple(rows)
        counts = tuple((sum(replies.values()), len(replies)) for replies in
                       (validation.get(incumbent, {}), validation.get(challenger, {})))
        decision = certify_expected_qualification(incumbent, challenger, rows, evaluate,
                                                  validation_counts=counts, **kwargs)
        families = len({row.family for row in rows})
        audit.update({f'freshProofs/{families}': 1, f'freshProofLookups/{families}': len(decision.observations)})
        return decision

    if label == 'strict':
        if not ordered:
            return route.run(matrix, held, seed, plan, start, label)
        routed = split.run

        def tracked(*args):
            original = cycle.run_fixed_pool_cycle

            def fresh(incumbent, candidates, rows, cohort, evaluate, **kwargs):
                validation.clear()

                def observe(prompt, row):
                    result = evaluate(prompt, row)
                    validation.setdefault(prompt, {})[row.id] = result.passed
                    return result

                return original(incumbent, candidates, rows, cohort, observe, **kwargs)

            with (patch.object(cycle, 'run_fixed_pool_cycle', fresh),
                  patch.object(route.ties.prior, 'certify_paired_qualification', proof)):
                return routed(*args)

        with patch.object(split, 'run', tracked):
            totals, trace = route.run(matrix, held, seed, plan, start, label)
    else:
        original = gepa.optimize_by_paid_reads

        def observe_gepa(incumbent, alternatives, train, cases, evaluate, spent, **kwargs):
            allowed = set(cases)
            validation.clear()

            def observe(prompt, row):
                passed = evaluate(prompt, row)
                if row in allowed:
                    validation.setdefault(prompt, {})[row] = passed
                return passed

            return original(incumbent, alternatives, train, cases, observe, spent, **kwargs)

        def run_gepa():
            _, counts, peak, trace = gepa.reinvest_episode(matrix, held, seed, plan['schedule'], plan,
                                                            batched=label.startswith('gepa-batched'))
            if peak > plan['searchCap']:
                raise ValueError('The original GEPA ceiling must be preserved')
            return counts, trace

        if ordered:
            with patch.object(gepa, 'optimize_by_paid_reads', observe_gepa), patch.object(
                    gepa, 'certify_paired_qualification', proof):
                totals, trace = run_gepa()
        else:
            totals, trace = run_gepa()
    totals.update(audit)
    return totals, trace


def decisions(trace, method):
    if method == 'strict':
        return [cycle['decision'] for cycle in trace]
    return [{key: value for key, value in step.items() if key != 'qualificationSha256'} for step in trace]


def prepare():
    prior, inputs = parent.prepare()
    frozen, references, captured = (parent.checked_file(path, value) for path, value in TRANSFER.items())
    settings = frozen['design']
    if digest(settings) != frozen['designSha256'] or any(
            item != frozen['designSha256']
            for item in (references['designSha256'], captured['designSha256BeforeCapture'])):
        raise ValueError('Transfer artifacts must refer to the same frozen design')
    inputs['mixtral-falcon'] = captured['panels'], references['panels'], settings
    sources = ('benchmarks/family_qualification_order.py', 'benchmarks/routed_start_protection.py',
               'benchmarks/routed_witness_split.py', 'benchmarks/gepa_paid_cap_transfer.py',
               'benchmarks/archive_complementarity_transfer.py', 'cpo/paired_qualification.py',
               'cpo/expected_qualification.py')
    design = {'protocol': 'cpo-family-qualification-order-v1', 'parentDesignSha256': digest(prior),
              'transferInputs': TRANSFER, 'methods': METHODS, 'cohorts': tuple(inputs),
              'scope': ('Order fresh qualification reads using expected proof work under a bounded discrete '
                        'prior from paid validation. Measure exact replay decisions and lookups. Preserve '
                        'the archive checks, independent qualification, and every search trajectory.'),
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in sources}}
    return design, inputs


def measure(panels, references, plan):
    results, totals = {}, {method: {arm: Counter() for arm in ('original', 'ordered')} for method in METHODS}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = route.CONFIRMATION.holdout(subject, len(matrix[0]))
        starts = route.ties.costs.retained_prompts(matrix, held, plan['schedule'])
        results[name] = {}
        for method in METHODS:
            counts, traces = {arm: Counter() for arm in ('original', 'ordered')}, {'original': [], 'ordered': []}
            for seed, start in zip(plan['schedule']['seeds'], starts, strict=True):
                first, original = run(matrix, held, seed, plan, str(start), method, ordered=False)
                second, ordered = run(matrix, held, seed, plan, str(start), method, ordered=True)
                if (decisions(original, method) != decisions(ordered, method)
                        or any(first[key] != second[key] for key in ('holdoutPasses', 'searchPaid', 'searchLogical'))):
                    raise ValueError(f'Qualification ordering changed a measured path for {name}/{method}')
                counts['original'].update(first)
                counts['ordered'].update(second)
                traces['original'].append(original)
                traces['ordered'].append(ordered)
            point = {arm: {**count, 'traceSha256': digest(traces[arm]),
                           'paidLookups': count['searchPaid'] + count['qualificationPaid']}
                     for arm, count in counts.items()}
            route.ties.frontier.expect_reference(point['original'], references[name][method])
            results[name][method] = point
            for arm, values in point.items():
                totals[method][arm].update({key: value for key, value in values.items() if type(value) is int})
    return {'panels': results, 'totals': totals}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, inputs = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for _, _, plan in inputs.values()):
        cli.error('Use pinned GEPA 0.1.4')
    results = {cohort: measure(*args) for cohort, args in inputs.items()}
    with args.out.open('x') as stream:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
