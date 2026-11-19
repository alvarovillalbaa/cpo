"""Keep the seeded screen and try a cached witness only if it finds no certificate."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import cached_miss_witness as cached
from benchmarks import episode_screen_adaptation as screens
from benchmarks.prompteval_paid_witness import meets_gate
from cpo._contract import digest
from cpo.challenger import certify_challenger
from cpo.fixed_pool_cycle import FixedPoolCycleResult, run_fixed_pool_cycle
from cpo.paired_qualification import certify_paired_qualification
from cpo.single_finalist import FinalistResult


POLICIES = {
    'seeded': ('seeded', 0),
    'one-pass-8': ('one-prior-pass', 8),
    'one-pass-16': ('one-prior-pass', 16),
    'two-pass-16': ('two-prior-passes', 16),
}
INCIDENT = ('lmentry-ends_with_word/flan-t5-xxl', 47690)


def try_fallback(incumbent, candidates, rows, observed, measure, witness, excluded, ceiling):
    """Use at most one alternate validation certificate within the remaining cap."""
    def remaining():
        return ceiling - len(observed)

    for prompt in candidates:
        if prompt == excluded:
            continue
        if (prompt, witness.id) not in observed and remaining() == 0:
            break
        if not measure(prompt, witness).passed:
            continue
        missing = sum((incumbent, row.id) not in observed for row in rows)
        if missing > remaining():
            break
        baseline = {row.id: measure(incumbent, row).passed for row in rows}
        evidence = {row.id: observed[prompt, row.id].passed for row in rows if (prompt, row.id) in observed}
        order = sorted(rows, key=lambda row: baseline[row.id])
        decision = certify_challenger(order, baseline, lambda row: measure(prompt, row),
                                      metric_limit=remaining(), observed=evidence)
        return prompt if decision.status == 'promote' else None
    return None


def cycle(incumbent, candidates, validation, qualification, evaluate, *, history, policy, audit,
          metric_limit, qualify, seed):
    rows, candidates = tuple(validation), tuple(candidates)
    observed = {}

    def measure(prompt, row):
        key = (prompt, row.id)
        if key not in observed:
            observed[key] = evaluate(prompt, row)
        return observed[key]

    first = run_fixed_pool_cycle(incumbent, candidates, rows, qualification, measure,
                                 metric_limit=metric_limit, qualify=qualify, seed=seed)
    if first.search.evaluations != len(observed):
        raise ValueError('The default search ledger must count distinct validation replies')
    choice, extra = POLICIES[policy]
    result = first
    if extra and first.search.prompt == incumbent:
        # The original witness is the first miss in the original seeded panel.
        initial = next((row.id for row in rows if (incumbent, row.id) in observed and
                        not observed[incumbent, row.id].passed), None)
        witness = cached.choose_witness(incumbent, (row for row in rows if row.id != initial), history, choice)
        total_cap = min(metric_limit, len(observed) + extra)
        if initial is not None and witness is not None and total_cap > len(observed):
            audit['fallbackScreens'] += 1
            candidate = try_fallback(incumbent, candidates, rows, observed, measure,
                                     witness, first.search.finalist, total_cap)
            audit['fallbackSearchLookups'] += len(observed) - first.search.evaluations
            if len(observed) > total_cap:
                raise ValueError('The alternate screen exceeded its cap')
            decision = None
            if candidate is not None:
                audit['fallbackCertificates'] += 1
                decision = certify_paired_qualification(incumbent, candidate, qualification, qualify, seed=seed)
            promoted = decision is not None and decision.status == 'promoted'
            audit['fallbackPromotions'] += int(promoted)
            # A rejected fallback produces a paid qualification receipt, but never
            # replaces the original archive candidate or enters the recency archive.
            selected = candidate if promoted else first.search.prompt
            finalist = candidate if promoted else first.search.finalist
            result = FixedPoolCycleResult(FinalistResult(selected, finalist, len(observed)), decision)
    for (prompt, case), reply in observed.items():
        if history.setdefault(case, {}).setdefault(prompt, reply.passed) is not reply.passed:
            raise ValueError('Exact cached observations must agree')
    return result


def run_episode(matrix, held, seed, original, plan, policy):
    history = {}
    counts = Counter(fallbackScreens=0, fallbackSearchLookups=0, fallbackCertificates=0, fallbackPromotions=0)

    def select(incumbent, candidates, validation, qualification, evaluate, **kwargs):
        return cycle(incumbent, candidates, validation, qualification, evaluate,
                     history=history, policy=policy, audit=counts, **kwargs)

    with patch.object(archive, 'run_fixed_pool_cycle', select):
        totals, trace = archive.episode(matrix, held, seed, original, plan, 'recency')
    totals.update(counts)
    return totals, trace


def prepare(phase):
    parent, original, data, gepa, fixed = cached.prepare(phase)
    plan = {
        **{k: parent[k] for k in ('phase', 'gepaReportSha256', 'fixedPoolReportSha256', 'gepaVersion',
                                'searchCap', 'validationRows', 'gate')},
        'protocol': 'cpo-cached-witness-fallback-v1', 'cachedWitnessPlanSha256': digest(parent),
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'policies': POLICIES,
        'diagnosticEpisode': list(INCIDENT),
        'scope': ('Run the seeded search first. After no certificate, try one earlier-paid witness under '
                  'the original search cap. A rejected fallback is ineligible for archive nomination.'),
    }
    return plan, original, data, gepa, fixed


def replay(plan, original, data, gepa, fixed):
    panels, incident = {}, {}
    for panel in data:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        methods, passes = {}, {}
        for policy in POLICIES:
            total, traces = Counter(), []
            passes[policy] = []
            for seed in original['seeds']:
                measured, trace = run_episode(matrix, held, seed, original, plan, policy)
                traces.append(trace)
                total.update(measured)
                passes[policy].append(measured['holdoutPasses'])
                if (name, seed) == INCIDENT:
                    incident[policy] = {'holdoutPasses': measured['holdoutPasses'], 'totals': dict(measured),
                                        'decisions': [step['decision'] for step in trace]}
            methods[policy] = dict(total, paidLookups=total['searchPaid'] + total['qualificationPaid'],
                                   callbackTraceSha256=digest(traces),
                                   pairedPassesVsSeeded=screens.paired_deltas(passes[policy], passes['seeded']))
        observed, reference = methods['seeded'], fixed[name][screens.DEFERRED]
        fields = {'searchLogical': 'searchLookups', 'searchPaid': 'searchAfterReuse',
                  'qualificationPaid': 'qualificationAfterStop', 'holdoutPasses': 'holdoutPasses',
                  'paidLookups': 'paidLookups'}
        if (observed['callbackTraceSha256'] != reference['callbackTraceSha256'] or
                any(observed[k] != reference['totals'][field] for k, field in fields.items())):
            raise ValueError(f'{name} differs from the published seeded path')
        controls = {method: {k: result[k] for k in ('holdoutPasses', 'paidLookups')}
                    for method, result in gepa[name]['reinvested'].items()}
        gates = {policy: {key: meets_gate(result, control) for key, control in controls.items()}
                 for policy, result in methods.items()}
        panels[name] = {'methods': methods, 'gepa': controls, 'gates': gates}
    qualified = {policy: [name for name, row in panels.items() if all(row['gates'][policy].values())]
                 for policy in POLICIES}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels,
            'panelsClearingBothGates': qualified, 'diagnosticEpisode': incident}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=archive.controls.reference.transfer.SOURCES, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current phase seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
