"""Test whether a paid second witness improves deferred challenger priority."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import deferred_certificate_probe_allocation as previous
from cpo._contract import digest
from cpo.challenger import certify_challenger
from cpo.single_finalist import FinalistResult


REPORT = 'docs/deferred-certificate-probe-allocation-results-v1.json'
REPORT_SHA256 = '476e3eb08541a1dd4a078794d5aab90fa5a8a844d7d5124fb283382fdc9f44e1'
RETAIN_FIRST = 'retention-first'
RETAIN_DEFER = 'retention-defer'
GAIN_DEFER = 'gain-defer'
POLICIES = RETAIN_FIRST, RETAIN_DEFER, GAIN_DEFER
paired = previous.paired


def prepare():
    parent, groups, controls, _, native = previous.prepare()
    read = paired.frontier.cost.prior.baseline.read_reference
    receipt = read(REPORT, REPORT_SHA256, parent)['results']
    plan = {**parent, 'protocol': 'deferred-certificate-second-witness-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': REPORT_SHA256,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': POLICIES,
            'scope': 'Use the shared first probe and full nominal reservation. On each positive probe, '
                     'spend the next proof read on the first incumbent pass or the next incumbent miss. '
                     'For the defer arms, move a challenger that fails this second case behind later '
                     'positive probes but ahead of shared-probe misses. Reuse the measured rows. '
                     'The retention-first control buys the same type of second case and keeps nominee '
                     'priority. Keep the exact validation and independent qualification gates.'}
    return plan, groups, controls, receipt, native


def screen(incumbent, candidates, rows, evaluate, cap, *, policy):
    candidates = candidates[:max(0, cap - 2 * len(rows) + 1)]
    if not candidates:
        return FinalistResult(incumbent, None, 0), None
    paid = 0

    def observe(prompt, row):
        nonlocal paid
        reply = evaluate(prompt, row)
        if type(reply.passed) is not bool:
            raise ValueError('Validation requires exact boolean outcomes')
        paid += 1
        return reply

    base = {row.id: observe(incumbent, row).passed for row in rows}
    passed = [row for row in rows if base[row.id]]
    missed = [row for row in rows if not base[row.id]]
    if not missed:
        return FinalistResult(incumbent, None, paid), None
    witness = missed[0]
    alternate = missed[1:] if policy == GAIN_DEFER else passed
    second = next(iter(alternate), None)
    order = (*missed, *passed)
    remaining = cap - len(rows) - len(candidates)

    def certificate(prompt, evidence):
        nonlocal remaining
        proof = certify_challenger(order, base, lambda row: observe(prompt, row), metric_limit=remaining,
                                   observed=evidence)
        remaining -= proof.evaluations
        if proof.status == 'promote':
            votes = proof.observations.values()
            return FinalistResult(prompt, prompt, paid), ((len(passed), len(rows)), (sum(votes), len(votes)))
        return None

    delayed, probe_misses = [], []
    for prompt in candidates:
        if remaining < len(passed):
            break
        hit = observe(prompt, witness).passed
        evidence = {witness.id: hit}
        if not hit:
            probe_misses.append((prompt, evidence))
            continue
        if passed and second is not None:
            second_hit = observe(prompt, second).passed
            remaining -= 1
            evidence[second.id] = second_hit
            if not second_hit and policy != RETAIN_FIRST:
                delayed.append((prompt, evidence))
                continue
        result = certificate(prompt, evidence)
        if result is not None:
            return result
    for prompt, evidence in (*delayed, *probe_misses):
        if remaining < len(passed) + 1 - sum(evidence.values()):
            continue
        result = certificate(prompt, evidence)
        if result is not None:
            return result
    return FinalistResult(incumbent, None, paid), None


def run_trial(policy, args):
    def select(*values):
        return screen(*values, policy=policy)

    with patch.object(paired.ordered, '_screen', select):
        return paired.cycle.execute_path(paired.ordered.run_paired_order_certificate_cycle, *args)


def measure(panels, plan, controls, earlier, native):
    paths = {}
    amounts = {label: {policy: Counter() for policy in POLICIES} for label in controls.values()}
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        panel = f'{subject}/{model}'
        traces = {label: {policy: [] for policy in (previous.BASE, *POLICIES)} for label in controls.values()}
        for seed in plan['seeds']:
            start, roster, roles = paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            for gain, label in controls.items():
                args = cells, start, roster, roles, seed, plan['fullRosterCap'], gain
                shared, shared_paid = paired.cycle.execute_path(paired.ordered.run_paired_order_certificate_cycle, *args)
                shared_point, _, trace = paired.reference.point(cells, roles[-1], shared, shared_paid)
                traces[label][previous.BASE].append(trace)
                for policy in POLICIES:
                    result, paid = run_trial(policy, args)
                    previous.check_deployment(cells, start, roles, result, gain)
                    point, _, trace = paired.reference.point(cells, roles[-1], result, paid)
                    amounts[label][policy].update(
                        **point, nominations=int(result.search.finalist is not None),
                        promotions=int(result.promoted), changedNominee=int(result.search.prompt != shared.search.prompt),
                        changedDeployment=int(result.prompt != shared.prompt),
                        holdoutDifference=point['holdoutPasses'] - shared_point['holdoutPasses'],
                        lookupDifference=point['paidLookups'] - shared_point['paidLookups'],
                    )
                    traces[label][policy].append(trace)
        paths[panel] = {label: {policy: digest(trace) for policy, trace in methods.items()}
                        for label, methods in traces.items()}
        for label in controls.values():
            if paths[panel][label][previous.BASE] != earlier['panelPathHashes'][panel][label][previous.BASE]:
                raise ValueError('The original shared probe trace must reproduce')
    feasible = tuple(row['expandedSubjectCeiling'] for row in native['comparisons'].values())
    for label, results in amounts.items():
        for policy, point in results.items():
            if any(point[key] - point[delta] != earlier['totals'][label][previous.BASE][key]
                   for key, delta in (('holdoutPasses', 'holdoutDifference'), ('paidLookups', 'lookupDifference'))):
                raise ValueError('Every total and paired difference must reconcile to the previous replay')
            results[policy] = {
                **point, 'affordableKnownGepaPasses': max(
                    (row['holdoutPasses'] for row in feasible if row['paidLookups'] <= point['paidLookups']),
                    default=None,
                ),
            }
    return {'totals': amounts, 'anchorTotals': earlier['totals'], 'panelPathHashes': paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, controls, earlier, native = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    results = {name: measure(panels, plan, controls, earlier[name], native[name]) for name, panels in groups.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
