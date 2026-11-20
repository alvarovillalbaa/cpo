"""Test early shortlist proofs and the holdout cost of validating one finalist."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import balanced_finalist_race as race
from benchmarks import finalist_bound_replay as previous
from benchmarks import finalist_score_bounds as bounds
from benchmarks.independent_mmlu_cost_frontier import expect_reference
from benchmarks.independent_mmlu_transfer import read_json
from benchmarks.prompteval_transfer import holdout
from cpo import select_pool
from cpo._contract import digest
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
PARENT_SHA256 = '2dc5c249429896ba163530894cc635f9d96212a806a75bbba95e2d15d20b7e36'
MODES = {'two-full': (2, False, False), 'two-lazy': (2, True, False), 'two-lazy-bounds': (2, True, True),
         'one-full': (1, False, False), 'one-lazy': (1, True, False), 'try-backup': (1, True, False)}
FIELDS = ('holdoutPasses', 'paidLookups', 'qualificationPaid')


def shortlist(candidates, probes, observe, *, size, lazy):
    """Rank by exact probe score and break ties in original proposal order."""
    best = []
    for prompt in candidates:
        threshold = best[-1][0] if lazy and len(best) == size else -1
        if threshold == len(probes):
            break
        passed = 0
        for i, row in enumerate(probes, 1):
            passed += observe(prompt, row).passed
            if passed + len(probes) - i <= threshold:
                break
        else:
            best.append((passed, prompt))
            best.sort(key=lambda item: item[0], reverse=True)
            best = best[:size]
    return tuple(prompt for _, prompt in best)


def screen(incumbent, candidates, rows, evaluate, *, metric_limit, width, screen_rows, mode, audit):
    max_finalists, lazy, use_bounds = MODES[mode]
    rows, candidates = tuple(rows), tuple(candidates)[:width]
    count = min(max_finalists, len(candidates))
    maximum = min(2, len(candidates)) if mode == 'try-backup' else count
    reserve = len(rows) + len(candidates) * screen_rows + maximum * (len(rows) - screen_rows)
    if (not 0 < screen_rows <= len(rows) or len({row.id for row in rows}) != len(rows)
            or len(set((incumbent, *candidates))) != 1 + len(candidates) or metric_limit < reserve):
        raise ValueError('The proof requires an affordable roster and distinct prompts and rows')
    if not candidates:
        return FinalistResult(incumbent, None, 0)
    ledger = {}

    def observe(prompt, row):
        key = (prompt, row.id)
        if key not in ledger:
            if len(ledger) >= metric_limit:
                raise ValueError('The shortlist exceeded the paid search ceiling')
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Exact screening requires boolean replies')
            ledger[key] = reply
        return ledger[key]

    baseline = {row.id: observe(incumbent, row).passed for row in rows}
    if all(baseline.values()):
        return FinalistResult(incumbent, None, len(ledger))
    ordered = race.matched_prefix(rows, baseline, screen_rows)
    probes = ordered[:screen_rows]
    finalists = shortlist(candidates, probes, observe, size=count, lazy=lazy)

    def exact(ranked):
        return select_pool((incumbent, *ranked), ordered, observe, metric_limit=metric_limit,
                           screen_rows=screen_rows, max_challenges=len(ranked), adaptive_rejection=True)

    if use_bounds:
        result = bounds.select_by_bounds(incumbent, finalists, rows, observe, metric_limit=metric_limit,
                                         width=count, screen_rows=screen_rows, defer_incumbent=False, audit=Counter())
    else:
        result = exact(finalists)
        if mode == 'try-backup' and result.prompt == incumbent and maximum == 2:
            result = exact(shortlist(candidates, probes, observe, size=maximum, lazy=True))
            audit.update(backupRaces=1)
    probe_ids = {row.id for row in probes}
    reads = sum(prompt != incumbent and case in probe_ids for prompt, case in ledger)
    audit.update(screenLookups=reads, omittedScreenLookups=len(candidates) * screen_rows - reads)
    return FinalistResult(result.prompt, result.prompt if result.prompt != incumbent else None, len(ledger))


def prepare(phase):
    parent, panels, references = previous.prepare(phase)
    raw = (ROOT / 'docs/finalist-bound-replay-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != PARENT_SHA256 or read_json(raw)[phase]['planSha256'] != digest(parent):
        raise ValueError('The source finalist race and cost report differ from their receipts')
    plan = {**{key: parent[key] for key in ('phase', 'gepaVersion', 'schedule', 'validationRows', 'searchCap')},
            'protocol': 'cpo-finalist-screen-budget-v1', 'parentPlanSha256': digest(parent), 'priorReportSha256': PARENT_SHA256,
            'policies': list(previous.POLICIES), 'modes': list(MODES),
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in (
                'benchmarks/finalist_screen_budget.py', 'benchmarks/balanced_finalist_race.py',
                'benchmarks/finalist_score_bounds.py', 'cpo/pool.py')},
            'scope': ('Compare reading the entire two-case screen with proving its shortlist early. '
                      'Preserve the original race for two finalists and measure one finalist with or without a backup. '
                      'The qualification cases, budget, rosters, and route trigger remain the same.')}
    return plan, panels, references


def run(matrix, held, seed, plan, policy, mode):
    if mode == 'two-full':
        return race.run(matrix, held, seed, plan, policy)
    audit = Counter(screenLookups=0, omittedScreenLookups=0, backupRaces=0)

    def select(incumbent, candidates, rows, evaluate, *, metric_limit, width, screen_rows):
        return screen(incumbent, candidates, rows, evaluate, metric_limit=metric_limit, width=width,
                      screen_rows=screen_rows, mode=mode, audit=audit)

    with patch.object(race, 'balanced_screen', select):
        totals, trace = race.run(matrix, held, seed, plan, policy)
    totals.update(audit)
    return totals, trace


def panel_results(matrix, held, plan, refs):
    methods = {key: {f: refs[key][f] for f in ('holdoutPasses', 'paidLookups')}
               for key in ('gepaBatched', 'gepaSequential')}
    for policy in previous.POLICIES:
        totals = {mode: Counter() for mode in MODES}
        journals = {mode: [] for mode in MODES}
        differences = Counter()
        for seed in plan['schedule']['seeds']:
            points = {mode: run(matrix, held, seed, plan, policy, mode) for mode in MODES}
            for mode, (observed, trace) in points.items():
                totals[mode].update(observed)
                journals[mode].append(trace)
                if mode in ('one-lazy', 'two-lazy', 'two-lazy-bounds'):
                    reference = 'one-full' if mode == 'one-lazy' else 'two-full'
                    original, baseline = points[reference]
                    if previous.choices(trace) != previous.choices(baseline):
                        raise ValueError('Early screening changed the funded shortlist race decision')
                    if mode != 'two-lazy-bounds' and observed['searchPaid'] > original['searchPaid']:
                        raise ValueError('Skipping dominated screen replies must never add paid search')
            delta = points['one-lazy'][0]['holdoutPasses'] - points['two-lazy'][0]['holdoutPasses']
            differences.update(gaining=int(delta > 0), losing=int(delta < 0), tied=int(delta == 0),
                               grossGain=max(0, delta), grossLoss=-min(0, delta))
        modes = {mode: dict(count, paidLookups=count['searchPaid'] + count['qualificationPaid'],
                            traceSha256=digest(journals[mode])) for mode, count in totals.items()}
        expect_reference(modes['two-full'], refs[policy])
        methods[policy] = {'modes': modes, 'oneVsTwo': differences}
    return methods


def replay(plan, panels, reference):
    results = {}
    totals = {policy: {mode: Counter() for mode in MODES} for policy in previous.POLICIES}
    totals.update({label: Counter() for label in ('gepaBatched', 'gepaSequential')})
    for row in panels:
        subject, model, matrix = (row[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = holdout(subject, len(matrix[0]))
        point = panel_results(matrix, held, plan, reference[name])
        results[name] = point
        for label in ('gepaBatched', 'gepaSequential'):
            totals[label].update(point[label])
        for policy in previous.POLICIES:
            for mode, fields in point[policy]['modes'].items():
                totals[policy][mode].update({k: fields[k] for k in (*FIELDS, 'omittedScreenLookups', 'backupRaces')
                                             if k in fields})
    return {'plan': plan, 'planSha256': digest(plan), 'panels': results, 'totals': totals}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--phase', choices=previous.PHASES, required=True)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Execution requires the current seal and a fresh report path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
