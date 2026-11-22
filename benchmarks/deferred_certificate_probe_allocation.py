"""Compare where to spend the fixed-roster search budget on recorded replies."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import deferred_certificate_paired_order as paired
from benchmarks import paired_order_gepa_comparison as gepa
from cpo._contract import digest
from cpo.challenger import certify_challenger
from cpo.single_finalist import FinalistResult


PAIRED_GEPA_REPORT = 'docs/paired-order-gepa-comparison-results-v1.json'
PAIRED_GEPA_SHA256 = '2b6ac95cfae9361a380aa9eb2a38858e8b03c8a7dfebd11268736ff537b63fd8'
BASE, ROTATE, RACE = 'shared-probe', 'rotating-probes', 'shared-probe-race'
METHODS = BASE, ROTATE, RACE


def prepare():
    parent, groups, policies, archived, _, _ = gepa.prepare()
    read = gepa.native_cost.prior.baseline.read_reference
    controls = read(PAIRED_GEPA_REPORT, PAIRED_GEPA_SHA256, parent)['results']
    plan = {**parent, 'protocol': 'deferred-certificate-probe-allocation-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': PAIRED_GEPA_SHA256,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': METHODS,
            'scope': 'Keep the full-roster search cap, paid incumbent precheck, matched cases, roster and '
                     'one- and two-gain independent qualification. Compare shared deferred probing with '
                     'rotating the witness in roster order and an eager shared-witness race that gives '
                     'the next paid proof reply to the challenger with fewest paid misses, then fewest '
                     'favorable replies needed, then earliest roster position. Audit how often an '
                     'independently qualifying holdout improvement was capable of exact certification '
                     'under the original probe reservation. Oracle grades cannot select a challenger.'}
    return plan, groups, policies, archived, controls


def screen(incumbent, candidates, rows, evaluate, cap, *, method):
    screened = candidates[:max(0, cap - 2 * len(rows) + 1)]
    if not screened:
        return FinalistResult(incumbent, None, 0), None
    paid = 0

    def observe(prompt, row):
        nonlocal paid
        observation = evaluate(prompt, row)
        if type(observation.passed) is not bool:
            raise ValueError('Validation requires exact boolean outcomes')
        paid += 1
        return observation

    base = {row.id: observe(incumbent, row).passed for row in rows}
    misses = [row for row in rows if not base[row.id]]
    reserved = cap - len(rows) - len(screened)
    passes = sum(base.values())
    if not misses or reserved < passes:
        return FinalistResult(incumbent, None, paid), None
    order = sorted(rows, key=lambda row: base[row.id])

    def finish(prompt, observations):
        return (FinalistResult(prompt, prompt, paid),
                ((passes, len(rows)), (sum(observations.values()), len(observations))))

    if method == ROTATE:
        failed = []
        for index, prompt in enumerate(screened):
            if reserved < passes:
                break
            witness = misses[index % len(misses)]
            evidence = {witness.id: observe(prompt, witness).passed}
            if not evidence[witness.id]:
                failed.append((prompt, evidence))
                continue
            proof = certify_challenger(order, base, lambda row: observe(prompt, row),
                                       metric_limit=reserved, observed=evidence)
            reserved -= proof.evaluations
            if proof.status == 'promote':
                return finish(prompt, proof.observations)
        for prompt, evidence in failed:
            if reserved <= passes:
                break
            proof = certify_challenger(order, base, lambda row: observe(prompt, row),
                                       metric_limit=reserved, observed=evidence)
            reserved -= proof.evaluations
            if proof.status == 'promote':
                return finish(prompt, proof.observations)
    elif method == RACE:
        witness = misses[0]
        evidence = {prompt: {witness.id: observe(prompt, witness).passed} for prompt in screened}
        proof_order = sorted(order, key=lambda row: not (row.critical and base[row.id]))
        while True:
            options = []
            for index, (prompt, seen) in enumerate(evidence.items()):
                proof = certify_challenger(order, base, None, metric_limit=0, observed=seen)
                if proof.status == 'promote':
                    return finish(prompt, seen)
                needed = proof.minimum_fresh_for_promotion
                if needed is not None and needed <= reserved:
                    options.append((len(seen) - sum(seen.values()), needed, index, prompt))
            if not options:
                break
            prompt = min(options)[-1]
            seen = evidence[prompt]
            row = next(row for row in proof_order if row.id not in seen)
            seen[row.id] = observe(prompt, row).passed
            reserved -= 1
    else:
        raise ValueError('Unknown validation probe policy')
    return FinalistResult(incumbent, None, paid), None


def check_deployment(cells, start, roles, result, gain):
    _, validation, proof, _ = roles
    nominee = result.search.prompt
    if nominee != start and sum(cells[nominee][i] - cells[start][i] for i in validation) <= 0:
        raise ValueError('A nomination needs a strict exact validation gain')
    qualified = sum(cells[nominee][i] - cells[start][i] for i in proof) >= gain
    if result.prompt != (nominee if qualified else start):
        raise ValueError('The deployed prompt must match exact independent qualification')


def audit_headroom(cells, start, roster, roles, gain, cap, result, paid):
    """Use complete archived grades only to locate the original policy's missed opportunity."""
    _, validation, proof, held = roles
    missed = [case for case in validation if not cells[start][case]]
    incumbent_validation = len(validation) - len(missed)
    candidates = [prompt for prompt in roster
                  if sum(cells[prompt][i] for i in validation) > incumbent_validation
                  and sum(cells[prompt][i] - cells[start][i] for i in proof) >= gain]
    measured = sum(cells[result.prompt][i] for i in held)
    improvements = {prompt: sum(cells[prompt][i] for i in held) - measured for prompt in candidates}
    improvements = {prompt: delta for prompt, delta in improvements.items() if delta > 0}
    if not improvements:
        return 'noBetterEligiblePrompt', 0
    # Each test candidate runs alone, with one fixed probe and the same total reserve.
    validation_rows = tuple(paired.cycle.Row(str(i), 'validation') for i in validation)
    base = {row.id: bool(cells[start][int(row.id)]) for row in validation_rows}
    order = sorted(validation_rows, key=lambda row: base[row.id])
    reserved = cap - len(validation) - len(roster)

    def fits(prompt, case):
        def observe(row):
            return paired.cycle.Observation(bool(cells[prompt][int(row.id)]), {})

        return certify_challenger(order, base, observe, metric_limit=reserved,
                                  observed={str(case): bool(cells[prompt][case])}).status == 'promote'

    shared = [prompt for prompt in improvements if fits(prompt, missed[0])]
    if any(paid.get(('validation', prompt, str(missed[0]))) is not None for prompt in shared):
        reason = 'betterSharedWitnessWasProbed'
    elif shared:
        reason = 'betterSharedWitnessWasUnprobed'
    elif any(fits(prompt, case) for prompt in improvements for case in missed[1:]):
        reason = 'betterNeedsDifferentWitness'
    else:
        reason = 'betterExceedsIsolatedProofReserve'
    return reason, max(improvements.values())


def run_variant(method, args):
    def select(*values):
        return screen(*values, method=method)

    with patch.object(paired.ordered, '_screen', select):
        return paired.cycle.execute_path(paired.ordered.run_paired_order_certificate_cycle, *args)


def measure(panels, plan, controls, archived, native):
    totals = {label: {method: Counter() for method in METHODS} for label in controls.values()}
    paths, headroom = {}, {label: Counter() for label in controls.values()}
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        panel = f'{subject}/{model}'
        traces = {label: {method: [] for method in METHODS} for label in controls.values()}
        for seed in plan['seeds']:
            start, roster, roles = paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            for gain, label in controls.items():
                args = cells, start, roster, roles, seed, plan['fullRosterCap'], gain
                baseline, paid = paired.cycle.execute_path(paired.ordered.run_paired_order_certificate_cycle, *args)
                reason, upside = audit_headroom(cells, start, roster, roles, gain, plan['fullRosterCap'], baseline, paid)
                headroom[label].update({reason: 1, 'maximumHoldoutUpside': upside})
                outcomes = [(baseline, paid), *(run_variant(method, args) for method in (ROTATE, RACE))]
                for method, (result, ledger) in zip(METHODS, outcomes, strict=True):
                    check_deployment(cells, start, roles, result, gain)
                    point, _, trace = paired.reference.point(cells, roles[-1], result, ledger)
                    totals[label][method].update(
                        **point, searchLookups=result.search.evaluations,
                        nominations=int(result.search.finalist is not None),
                        promotions=int(result.promoted), changedNominee=int(result.search.prompt != baseline.search.prompt),
                    )
                    traces[label][method].append(trace)
        paths[panel] = {label: {method: digest(trace) for method, trace in by_method.items()}
                        for label, by_method in traces.items()}
        if any(paths[panel][label][BASE] != archived['panelPathHashes'][panel][label] for label in controls.values()):
            raise ValueError('Every baseline callback must match the published paired-order screen')
    budget_points = [(row['cpo']['paidLookups'], row['expandedSubjectCeiling'])
                     for row in native['comparisons'].values()]
    bounds = {}
    for label, outcomes in totals.items():
        expected = native['comparisons'][label]['cpo']
        if any(outcomes[BASE][key] != value for key, value in expected.items()):
            raise ValueError('The original paired search must reproduce the published totals')
        bounds[label] = {}
        for method, point in outcomes.items():
            budget = point['paidLookups']
            low = max((row['holdoutPasses'] for _, row in budget_points if row['paidLookups'] <= budget), default=None)
            high = min((row['holdoutPasses'] for limit, row in budget_points if limit >= budget), default=None)
            if low is not None and high is not None and low > high:
                raise ValueError('Affordable GEPA bounds must be monotone')
            bounds[label][method] = {'lowerPasses': low, 'upperPasses': high}
    return {'totals': totals, 'headroom': headroom, 'panelPathHashes': paths, 'nativeGepaBounds': bounds}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, controls, archived, native = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    results = {name: measure(panels, plan, controls, archived[name], native[name])
               for name, panels in groups.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
