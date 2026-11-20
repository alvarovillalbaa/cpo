"""Test a paid-prefix continuation when narrow validation finds no gain."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import finalist_screen_budget as prior
from benchmarks import routed_finalist_model_transfer as transfer
from benchmarks.prompteval_transfer import holdout
from cpo import fixed_pool_cycle
from cpo._contract import digest
from cpo.challenger import certify_challenger
from cpo.lazy_incumbent import select_with_lazy_incumbent
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs/finalist-screen-budget-results-v1.json'
PARENT_SHA256 = '53e59a42802a935e859ae4ce417c28e7972b3364c2c3b5f9a87aa873e94ea8c2'
CONTROL = 'routed-backup'
METHODS = (CONTROL, 'late-empty', 'late-rejected', 'late-stalled', 'narrow-with-rescue',
           'late-first-witness', 'late-two-probes')
SCORE = ('holdoutPasses', 'paidLookups')


def rescue(incumbent, candidates, rows, evaluate, *, metric_limit, triggers, audit,
           stop_at_witness=False, probe_limit=None):
    """Start with the ordinary narrow proof. Buy at most one new witness per alternative."""
    rows, candidates = tuple(rows), tuple(candidates)
    evidence = {prompt: {} for prompt in (incumbent, *candidates)}
    spent = 0

    def observe(prompt, row):
        nonlocal spent
        known = evidence[prompt]
        if row.id not in known:
            if spent == metric_limit:
                raise ValueError('Rescue exceeded its original search allowance')
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Rescue requires exact boolean outcomes')
            known[row.id] = reply
            spent += 1
        return known[row.id]

    opening = select_with_lazy_incumbent(incumbent, candidates, rows, observe, metric_limit=metric_limit)
    status = 'empty' if opening.finalist is None else 'rejected'
    if opening.prompt != incumbent or status not in triggers or not candidates:
        return opening
    audit.update(rescueAttempts=1)
    base = evidence[incumbent]

    def can_complete(prompt):
        return spent + 2 * len(rows) - len(base) - len(evidence[prompt]) <= metric_limit

    if not any(can_complete(prompt) for prompt in candidates):
        return opening
    misses = []
    for row in rows:
        if not observe(incumbent, row).passed:
            misses.append(row)
            if len(misses) == 2:
                break
    if not misses:
        return FinalistResult(incumbent, opening.finalist, spent)

    def witnessed(prompt):
        return any(row.id in evidence[prompt] and evidence[prompt][row.id].passed for row in misses)

    probes = 0
    for prompt in candidates:
        if prompt == opening.finalist or not can_complete(prompt):
            continue
        if not witnessed(prompt) and (probe_limit is None or probes < probe_limit):
            probe = next((row for row in reversed(misses) if row.id not in evidence[prompt]), None)
            if probe is not None:
                observe(prompt, probe)
                probes += 1
        if stop_at_witness and witnessed(prompt):
            break
    audit.update(rescueProbes=probes)
    admitted = [p for p in candidates if p != opening.finalist and witnessed(p) and can_complete(p)]
    if not admitted:
        return FinalistResult(incumbent, opening.finalist, spent)

    baseline = {row.id: observe(incumbent, row).passed for row in rows}
    ordered = sorted(rows, key=lambda row: baseline[row.id])

    def priority(prompt):
        known = evidence[prompt]
        return Fraction(1 + sum(reply.passed for reply in known.values()), len(known) + 2)

    for prompt in sorted(admitted, key=priority, reverse=True)[:2]:
        if not can_complete(prompt):
            continue
        audit.update(rescueProofs=1)
        decision = certify_challenger(
            ordered, baseline, lambda row: observe(prompt, row), metric_limit=metric_limit - spent,
            observed={case: reply.passed for case, reply in evidence[prompt].items()},
        )
        if decision.status == 'promote':
            audit.update(rescuedNominees=1)
            return FinalistResult(prompt, prompt, spent)
    return FinalistResult(incumbent, opening.finalist, spent)


def run(matrix, held, seed, plan, method):
    if method == CONTROL:
        return prior.run(matrix, held, seed, plan, 'wide-after-two-misses', 'try-backup')
    _, layouts = archive.continuous.schedule(len(matrix[0]), len(matrix), held, seed, plan['schedule'])
    first = tuple(layouts[0]['alternatives'])
    triggers = ('empty', 'rejected')
    if method in ('late-empty', 'late-first-witness', 'late-two-probes'):
        triggers = ('empty',)
    elif method == 'late-rejected':
        triggers = ('rejected',)
    audit = Counter()

    def screen(incumbent, candidates, rows, evaluate, *, metric_limit):
        rows, candidates = tuple(rows), tuple(candidates)
        known = {}

        def observe(prompt, row):
            key = (prompt, row.id)
            if key not in known:
                if len(known) == metric_limit:
                    raise ValueError('The route exceeded the fresh search allowance')
                known[key] = evaluate(prompt, row)
            return known[key]

        if method != 'narrow-with-rescue' and all(not observe(incumbent, row).passed for row in rows[:2]):
            audit.update(wideCycles=1)
            result = prior.screen(incumbent, candidates, rows, observe, metric_limit=metric_limit,
                                  width=6, screen_rows=2, mode='try-backup', audit=audit)
        else:
            enabled = triggers if method == 'narrow-with-rescue' or candidates != first else ()
            result = rescue(incumbent, candidates, rows, observe, metric_limit=metric_limit, triggers=enabled,
                            audit=audit, stop_at_witness=method in ('late-first-witness', 'late-two-probes'),
                            probe_limit=2 if method == 'late-two-probes' else None)
        return FinalistResult(result.prompt, result.finalist, len(known))

    def cycle(*args, **kwargs):
        return fixed_pool_cycle.run_fixed_pool_cycle(*args, screen=method, **kwargs)

    with patch.dict(fixed_pool_cycle._SCREENS, {method: screen}), patch.object(archive, 'run_fixed_pool_cycle', cycle):
        totals, trace = archive.episode(matrix, held, seed, plan['schedule'], plan, 'recency')
    totals.update(audit)
    return totals, trace


def prepare(phase):
    parent, panels, references = prior.prepare(phase)
    raw = REPORT.read_bytes()
    stored = prior.read_json(raw)[phase]
    if sha256(raw).hexdigest() != PARENT_SHA256 or stored['planSha256'] != digest(parent):
        raise ValueError('The original backup measurements differ from their published seal')
    plan = {**{k: parent[k] for k in ('phase', 'schedule', 'validationRows', 'searchCap', 'gepaVersion')},
            'protocol': 'cpo-finalist-witness-rescue-v1', 'parentPlanSha256': digest(parent),
            'parentReportSha256': PARENT_SHA256, 'methods': list(METHODS),
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in (
                'benchmarks/finalist_witness_rescue.py', 'benchmarks/finalist_screen_budget.py',
                'benchmarks/archive_complementarity_transfer.py', 'cpo/lazy_incumbent.py', 'cpo/challenger.py')},
            'scope': ('Reuse the narrow search journal to test fresh evidence on the first two incumbent misses. '
                      'Retain the original combined ceilings, fresh qualification, and recency archive.')}
    return plan, panels, references, stored['panels']


def replay(plan, panels, references, stored):
    results, totals = {}, {method: Counter() for method in (*METHODS, 'gepaBatched', 'gepaSequential')}
    loss_audit = Counter()
    for row in panels:
        subject, model, matrix = (row[key] for key in ('subject', 'model', 'correctness'))
        name, held = f'{subject}/{model}', holdout(subject, len(matrix[0]))
        sums = {method: Counter() for method in METHODS}
        journals = {method: [] for method in METHODS}
        paired = {method: Counter() for method in METHODS if method != CONTROL}
        sequential_trace = []
        panel_losses = Counter()
        for seed in plan['schedule']['seeds']:
            base, baseline = run(matrix, held, seed, plan, CONTROL)
            sums[CONTROL].update(base)
            journals[CONTROL].append(baseline)
            for method in paired:
                count, trace = run(matrix, held, seed, plan, method)
                sums[method].update(count)
                journals[method].append(trace)
                delta = count['holdoutPasses'] - base['holdoutPasses']
                paired[method].update(episodesGaining=int(delta > 0), episodesLosing=int(delta < 0),
                                      grossGain=max(0, delta), grossLoss=max(0, -delta))
            if plan['phase'] == 'model-transfer':
                winner, count, peak, trace = transfer.gepa.reinvest_episode(
                    matrix, held, seed, plan['schedule'], plan, batched=False)
                if peak > plan['searchCap']:
                    raise ValueError('The sequential control exceeded its original search allowance')
                sequential_trace.append(trace)
                deficit = count['holdoutPasses'] - base['holdoutPasses']
                if deficit > 0:
                    reached = any(winner in (step['decision']['challenger'], step['decision']['archiveNominee'])
                                  for step in baseline)
                    label = 'reached' if reached else 'unseen'
                    panel_losses.update({label + 'Episodes': 1, label + 'PassDeficit': deficit})
        points = {m: dict(count, paidLookups=count['searchPaid'] + count['qualificationPaid'],
                          traceSha256=digest(journals[m])) for m, count in sums.items()}
        expected = stored[name]['wide-after-two-misses']['modes']['try-backup']
        if any(points[CONTROL][key] != expected[key] for key in (*SCORE, 'traceSha256')):
            raise ValueError('The original routed backup trace did not reproduce')
        if sequential_trace and digest(sequential_trace) != references[name]['gepaSequential']['traceSha256']:
            raise ValueError('The sequential control trace did not reproduce')
        for label in ('gepaBatched', 'gepaSequential'):
            points[label] = {key: references[name][label][key] for key in SCORE}
        for method, point in points.items():
            counts = ('rescueAttempts', 'rescueProbes', 'rescueProofs', 'rescuedNominees')
            totals[method].update({key: point[key] for key in (*SCORE, *counts) if key in point})
            if method in paired:
                totals[method].update(paired[method])
        results[name] = {'methods': points, 'pairedVsRoutedBackup': paired, 'sequentialLossAudit': panel_losses}
        loss_audit.update(panel_losses)
    return {'plan': plan, 'planSha256': digest(plan), 'totals': totals, 'panels': results,
            'modelTransferSequentialLossAudit': loss_audit}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--phase', required=True, choices=prior.previous.PHASES)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Execution requires the current phase seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
