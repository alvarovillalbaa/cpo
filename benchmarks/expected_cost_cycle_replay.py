"""Verify the packaged fixed-pool cycle against the published replay paths."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import family_qualification_order as family
from benchmarks import qualification_order_transfer as transfer
from benchmarks.case_difficulty_allocation import checked_file
from benchmarks.independent_mmlu_transfer import read_json
from cpo._contract import digest
from cpo.expected_cost_cycle import run_expected_cost_fixed_pool_cycle


ROOT = Path(__file__).resolve().parents[1]
FAMILY_REPORT = 'b8edacf20885c09bc79b4aa40841ad0cfa4dd0e527e7df1bca3677f4bce798d8'
TRANSFER_REPORT = 'e940060d1c392cb8e0233a2d9bf88165fd5a32493cd93d306a8bae0493c18dbb'
TRANSFER_SNAPSHOT = 'dae40ce166fabd49e8e3559db5a342a4047455c023d32dfe8c0efe2ea80bd326'


def prepare():
    family_plan, cohorts = family.prepare()
    archived = checked_file('docs/family-qualification-order-results-v1.json', FAMILY_REPORT)
    evaluation = checked_file('docs/qualification-order-transfer-results-v3.json', TRANSFER_REPORT)
    snapshot = checked_file('benchmarks/data/qualification-order-transfer-v3.json', TRANSFER_SNAPSHOT)
    manifest = read_json((ROOT / 'docs/qualification-order-transfer-design-v3.json').read_bytes())
    transfer_plan = manifest['design']
    transfer.check_snapshot(transfer_plan, snapshot)
    if (digest(family_plan) != archived['designSha256']
            or digest(transfer_plan) != manifest['designSha256'] or manifest['designSha256'] != evaluation['designSha256']
            or evaluation['snapshotSha256'] != TRANSFER_SNAPSHOT or evaluation['primaryGate'] != 'passed'):
        raise ValueError('The recorded qualification comparisons differ from their published designs')

    comparisons = {}
    for name, (panels, _, plan) in cohorts.items():
        reference = {label: item['strict']['ordered'] for label, item in archived['results'][name]['panels'].items()}
        comparisons[name] = (panels, plan, reference)
    comparisons['bbh-lmentry'] = (
        snapshot['panels'], transfer_plan, {label: item['expected-order'] for label, item in evaluation['panels'].items()},
    )
    paths = ('benchmarks/expected_cost_cycle_replay.py', 'cpo/expected_cost_cycle.py',
             'cpo/fixed_pool_cycle.py', 'cpo/paired_qualification.py', 'cpo/expected_qualification.py')
    design = {
        'protocol': 'cpo-expected-cost-cycle-replay-v1', 'familyReportSha256': FAMILY_REPORT,
        'transferReportSha256': TRANSFER_REPORT, 'transferSnapshotSha256': TRANSFER_SNAPSHOT,
        'transferDesignSha256': manifest['designSha256'],
        'cohorts': list(comparisons), 'scope': ('Use the public cycle in the recorded CPO route. Verify the '
                                               'complete archived path and realized lookup cost on each panel.'),
        'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
    }
    return design, comparisons


def episode(matrix, held, seed, plan, start):
    start_protection = family.route.ties.prior
    cycle = family.route.ties.split.fixed_pool_cycle

    def ordered(incumbent, candidates, validation, qualification_rows, evaluate, **kwargs):
        if incumbent == start:
            qualification_rows = start_protection.halves(qualification_rows)
        return run_expected_cost_fixed_pool_cycle(
            incumbent, candidates, validation, qualification_rows, evaluate, **kwargs,
        )

    # Substitute only the fresh cycle. The fixture still supplies the frozen
    # archive preflight policy and routes between its original search screens.
    with patch.object(cycle, 'run_fixed_pool_cycle', ordered):
        return family.route.run(matrix, held, seed, plan, start, 'strict')


def replay(panels, plan, references):
    results, totals = {}, Counter()
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = family.route.CONFIRMATION.holdout(subject, len(matrix[0]))
        starts = family.route.ties.costs.retained_prompts(matrix, held, plan['schedule'])
        combined, traces = Counter(), []
        for seed, start in zip(plan['schedule']['seeds'], starts, strict=True):
            counts, trace = episode(matrix, held, seed, plan, str(start))
            combined.update(counts)
            traces.append(trace)
        result = {key: combined[key] for key in ('holdoutPasses', 'searchPaid', 'qualificationPaid')}
        result.update(paidLookups=combined['searchPaid'] + combined['qualificationPaid'],
                      traceSha256=digest(traces))
        reference = references[name]
        family.route.ties.frontier.expect_reference(result, reference)
        if any(result[key] != reference[key] for key in ('searchPaid', 'qualificationPaid') if key in reference):
            raise ValueError(f'Lookup categories differ from the published path for {name}')
        results[name] = result
        totals.update({key: value for key, value in result.items() if type(value) is int})
    return {'panels': results, 'totals': totals}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, comparisons = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    report = {name: replay(*inputs) for name, inputs in comparisons.items()}
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': report}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
