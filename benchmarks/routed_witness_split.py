"""Screen different challengers on two already observed incumbent misses."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import finalist_screen_budget as balanced
from benchmarks import finalist_witness_rescue as prior
from benchmarks.finalist_bound_replay import PHASES
from benchmarks.independent_mmlu_transfer import read_json
from benchmarks.prompteval_transfer import holdout
from cpo import fixed_pool_cycle, select_pool
from cpo._contract import digest
from cpo.bounded_discovery import select_with_bounded_discovery
from cpo.challenger import certify_challenger
from cpo.lazy_incumbent import select_with_lazy_incumbent
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
PARENT_SHA256 = '38c45a8bc77aaa77deec7d53701ef0e5aa5886aa243efaad6a9a3f0d5d5e7413'
SETTINGS = {
    'shared-first': ('first', False, False, None),
    'split-first': ('first', True, False, None),
    'split-retry': ('retry', True, False, None),
    'split-dual': ('dual', True, False, None),
    'split-retry-with-discovery': ('retry', True, True, None),
    'wide-on-third-miss': ('retry', True, False, False),
    'wide-on-third-pass': ('retry', True, False, True),
}
METHODS = (prior.CONTROL, *SETTINGS)
CONTROLS = ('gepaBatched', 'gepaSequential')
METRICS = ('wideCycles', 'balancedCycles', 'screenProbes', 'secondMissProbes', 'proofAttempts', 'twoWitnessCycles')


def routed_selection(incumbent, candidates, validation, evaluate, *, metric_limit, mode, split, discovery, audit,
                     widen_on=None):
    rows, candidates = tuple(validation), tuple(candidates)
    count = len(rows)
    if (not rows or count != len({r.id for r in rows}) or metric_limit < count
            or len(set((incumbent, *candidates))) != 1 + len(candidates)):
        raise ValueError('Screening requires a distinct roster and a funded validation panel')
    ledger = {}

    def observe(prompt, row):
        key = (prompt, row.id)
        if key not in ledger:
            if len(ledger) >= metric_limit:
                raise ValueError('The screen exceeded the search ceiling')
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('The screen requires exact boolean outcomes')
            ledger[key] = reply
        return ledger[key]

    if len(rows) < 2 or any(observe(incumbent, row).passed for row in rows[:2]):
        narrow = select_with_bounded_discovery if discovery else select_with_lazy_incumbent
        selection = narrow(incumbent, candidates, rows, observe, metric_limit=metric_limit)
        return FinalistResult(selection.prompt, selection.finalist, len(ledger))

    audit.update(wideCycles=1)
    width = min(6, len(candidates))
    wide_reserve = count + 2 * width + min(2, width) * (count - 2)
    if (widen_on is not None and count >= 3 and metric_limit >= wide_reserve
            and observe(incumbent, rows[2]).passed == widen_on):
        audit.update(balancedCycles=1)
        selection = balanced.screen(incumbent, candidates, rows, observe, metric_limit=metric_limit,
                                    width=width, screen_rows=2, mode='try-backup', audit=audit)
        return FinalistResult(selection.prompt, selection.finalist, len(ledger))

    baseline = {}
    incumbent_reads = len(ledger)
    finalists = []
    attempted = 0
    for index, prompt in enumerate(candidates):
        lane = index % 2 if split else 0
        if mode == 'dual' and any(lane == previous for _, previous in finalists):
            continue
        pending_base = 0 if baseline else count - incumbent_reads
        pending_finalists = len(finalists) * (count - 1) if mode == 'dual' else 0
        if len(ledger) + pending_base + pending_finalists + count > metric_limit:
            break
        audit.update(screenProbes=1, secondMissProbes=lane)
        witness = rows[lane]
        if not observe(prompt, witness).passed:
            continue
        if mode == 'dual':
            finalists.append((prompt, lane))
            if len(finalists) == 2:
                break
            continue

        if not baseline:
            baseline = {row.id: observe(incumbent, row).passed for row in rows}
        ordered = sorted(rows, key=lambda row: baseline[row.id])
        attempted += 1
        audit.update(proofAttempts=1)
        proof = certify_challenger(ordered, baseline, lambda row: observe(prompt, row),
                                   metric_limit=metric_limit - len(ledger), observed={witness.id: True})
        if proof.status == 'promote':
            return FinalistResult(prompt, prompt, len(ledger))
        if mode == 'first' or attempted == 2:
            break

    if finalists:
        audit.update(proofAttempts=len(finalists), twoWitnessCycles=int(len(finalists) == 2))
        result = select_pool((incumbent, *(prompt for prompt, _ in finalists)), rows, observe,
                             metric_limit=metric_limit, adaptive_rejection=True)
        winner = result.prompt
        return FinalistResult(winner, winner if winner != incumbent else None, len(ledger))
    return FinalistResult(incumbent, None, len(ledger))


def run(matrix, held, seed, plan, method):
    if method == prior.CONTROL:
        return prior.run(matrix, held, seed, plan, method)
    mode, split, discovery, widen_on = SETTINGS[method]
    audit = Counter()

    def screen(incumbent, candidates, rows, evaluate, *, metric_limit):
        return routed_selection(incumbent, candidates, rows, evaluate, metric_limit=metric_limit,
                                mode=mode, split=split, discovery=discovery, audit=audit, widen_on=widen_on)

    def cycle(*args, **kwargs):
        return fixed_pool_cycle.run_fixed_pool_cycle(*args, screen=method, **kwargs)

    with patch.dict(fixed_pool_cycle._SCREENS, {method: screen}), patch.object(archive, 'run_fixed_pool_cycle', cycle):
        result, trace = archive.episode(matrix, held, seed, plan['schedule'], plan, 'recency')
    result.update(audit)
    return result, trace


def prepare(phase):
    parent, panels, refs, _ = prior.prepare(phase)
    raw = (ROOT / 'docs/finalist-witness-rescue-results-v1.json').read_bytes()
    archive_report = read_json(raw)[phase]
    if sha256(raw).hexdigest() != PARENT_SHA256 or archive_report['planSha256'] != digest(parent):
        raise ValueError('The routed backup report differs from its published seal')
    paths = ('benchmarks/routed_witness_split.py', 'benchmarks/finalist_witness_rescue.py',
             'benchmarks/finalist_screen_budget.py',
             'cpo/bounded_discovery.py', 'cpo/challenger.py', 'cpo/pool.py')
    plan = {**{key: parent[key] for key in ('phase', 'schedule', 'searchCap', 'gepaVersion', 'validationRows')},
            'protocol': 'cpo-routed-witness-split-v1', 'parentPlanSha256': digest(parent),
            'parentReportSha256': PARENT_SHA256, 'settings': SETTINGS,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'scope': ('Reuse the two-miss route observations for a single probe per offered challenger. '
                      'Compare different uses of the two witnesses and a third incumbent observation '
                      'that decides whether to use the balanced backup race. Keep the original caps and qualification.')}
    return plan, panels, refs, archive_report['panels']


def replay(plan, panels, refs, archive_panels):
    results = {}
    totals = {m: Counter() for m in (*METHODS, *CONTROLS)}
    for panel in panels:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        name, held = f'{subject}/{model}', holdout(subject, len(matrix[0]))
        counts = {m: Counter() for m in METHODS}
        paths = {m: [] for m in METHODS}
        per_seed = {m: [] for m in METHODS}
        for seed in plan['schedule']['seeds']:
            for method in METHODS:
                cost, trace = run(matrix, held, seed, plan, method)
                counts[method].update(cost)
                paths[method].append(trace)
                per_seed[method].append(cost['holdoutPasses'])
        points = {m: dict(values, paidLookups=values['searchPaid'] + values['qualificationPaid'],
                          traceSha256=digest(paths[m])) for m, values in counts.items()}
        baseline = archive_panels[name]['methods'][prior.CONTROL]
        if any(points[prior.CONTROL][key] != baseline[key] for key in (*prior.SCORE, 'traceSha256')):
            raise ValueError('The published routed backup changed on replay')
        for m in CONTROLS:
            points[m] = {key: refs[name][m][key] for key in prior.SCORE}
        for m, values in points.items():
            if m in SETTINGS:
                deltas = [x-y for x, y in zip(per_seed[m], per_seed[prior.CONTROL], strict=True)]
                values.update(episodesGaining=sum(d > 0 for d in deltas), episodesLosing=sum(d < 0 for d in deltas))
            totals[m].update({key: values[key] for key in (*prior.SCORE, *METRICS, 'episodesGaining', 'episodesLosing')
                              if key in values})
        results[name] = points
    return {'plan': plan, 'planSha256': digest(plan), 'totals': totals, 'panels': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=PHASES)
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
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
