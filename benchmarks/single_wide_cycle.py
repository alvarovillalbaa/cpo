"""Spend the more expensive validation screen once on a fixed-pool episode."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import budgeted_second_probe as wider
from benchmarks import episode_screen_adaptation as screens
from benchmarks.prompteval_paid_witness import meets_gate
from cpo import fixed_pool_cycle
from cpo._contract import digest


SOURCE_SHA256 = '7f795f565849deeab8a5f77b6de37aea3d1efcce9827cc71a80c2f9346cafa1a'
PAID_SEARCH_CEILING = 96
METHODS = ('seeded', 'wide-all', 'wide-first', 'wide-final', 'late-at-start', 'final-with-credit')
PUBLISHED = {'seeded': 'seeded', 'wide-all': 'recheck-first-failures'}


def allow_widening(method, index, cycles, *, incumbent, start, spent, limit, used):
    """Decide from the recorded search prefix and the current cycle's nominal ceiling."""
    if method == 'wide-all':
        return True
    if used or method == 'seeded':
        return False
    if method == 'wide-first':
        return index == 1
    if method == 'wide-final':
        return index == cycles
    if method == 'late-at-start':
        return index >= cycles - 1 and incumbent == start
    if method == 'final-with-credit':
        return index == cycles and spent + limit <= PAID_SEARCH_CEILING
    raise ValueError('Unknown wide-screen policy')


def run_episode(matrix, held, seed, original, plan, method):
    start, layouts = archive.continuous.schedule(len(matrix[0]), len(matrix), held, seed, original)
    indices = {layout['seed']: index for index, layout in enumerate(layouts, 1)}
    if len(indices) != len(layouts):
        raise ValueError('The fixed schedules need distinct cycle seeds')
    history, evidence = [], set()
    audit = Counter()

    def screen(incumbent, candidates, validation, evaluate, *, metric_limit):
        return wider.select_with_second_probe(incumbent, candidates, validation, evaluate,
                                              metric_limit=metric_limit, recheck=True, audit=audit)

    def select(incumbent, candidates, validation, qualification, evaluate, *, metric_limit, seed, **kwargs):
        index = indices[seed]
        wide = allow_widening(method, index, len(layouts), incumbent=incumbent, start=start,
                              spent=len(evidence), limit=metric_limit, used=bool(history))
        if wide:
            history.append(index)

        def record(prompt, row):
            observation = evaluate(prompt, row)
            evidence.add((prompt, row.id))
            return observation

        return fixed_pool_cycle.run_fixed_pool_cycle(
            incumbent, candidates, validation, qualification, record, metric_limit=metric_limit,
            seed=seed, screen='two-probe' if wide else screens.DEFERRED, **kwargs)

    with patch.dict(fixed_pool_cycle._SCREENS, {'two-probe': screen}), patch.object(archive, 'run_fixed_pool_cycle', select):
        total, trace = archive.episode(matrix, held, seed, original, plan, 'recency')
    if len(evidence) != total['searchPaid'] or (method != 'wide-all' and len(history) > 1):
        raise ValueError('The selector disagrees with the measured search ledger or one-cycle limit')
    if method == 'final-with-credit' and history and len(evidence) > PAID_SEARCH_CEILING:
        raise ValueError('The final wide search overspent its episode search credit')
    total.update(wideCycles=len(history), wideEpisodes=int(bool(history)), extraProbes=audit['secondProbes'])
    return total, trace, history


def prepare(phase):
    source, original, data, controls, _ = wider.prepare(phase)
    previous = archive.checked_report('budgeted-second-probe-results-v1.json', SOURCE_SHA256, phase)
    if previous['planSha256'] != digest(source):
        raise ValueError('The full-width replay differs from the published source')
    plan = {
        **{key: source[key] for key in ('phase', 'searchCap', 'validationRows', 'gepaVersion', 'gate')},
        'protocol': 'cpo-single-wide-cycle-v1', 'parentPlanSha256': digest(source),
        'sourceReportSha256': SOURCE_SHA256, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'methods': list(METHODS), 'paidSearchCeilingForFinalCredit': PAID_SEARCH_CEILING,
        'scope': ('Choose the wider screen once from cycle position, current incumbent, or prior paid validation '
                  'lookups. Preserve the qualification gate, archives and original per-cycle cap.'),
    }
    return plan, original, data, controls, previous['panels']


def replay(plan, original, panels, controls, published):
    results = {}
    for panel in panels:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        saved = published[name]['methods']
        audit = {row['seed']: row['gepaHoldoutPasses'] for row in saved['seeded']['strictGainLossAudit']}
        methods, scores = {}, {}
        for method in METHODS:
            total, traces, positions = Counter(), [], Counter()
            scores[method] = []
            for seed in original['seeds']:
                measured, trace, history = run_episode(matrix, held, seed, original, plan, method)
                total.update(measured)
                total['matchedGepaOnAuditedLoss'] += int(seed in audit and measured['holdoutPasses'] >= audit[seed])
                traces.append(trace)
                positions.update(str(index) for index in history)
                scores[method].append(measured['holdoutPasses'])
            result = dict(total, traceSha256=digest(traces), wideCyclePositions=dict(positions),
                          paidLookups=total['searchPaid'] + total['qualificationPaid'],
                          pairedPassesVsSeeded=screens.paired_deltas(scores[method], scores['seeded']))
            if method in PUBLISHED and any(result[k] != saved[PUBLISHED[method]][k] for k in wider.PUBLISHED_FIELDS):
                raise ValueError(f'{name} {method} differs from the published callback trace, costs or score')
            methods[method] = result
        gepa = {m: {k: row[k] for k in ('holdoutPasses', 'paidLookups')} for m, row in controls[name].items()}
        gates = {method: {m: meets_gate(result, ref) for m, ref in gepa.items()} for method, result in methods.items()}
        results[name] = {'methods': methods, 'gepa': gepa, 'gates': gates}
    qualified = {method: [name for name, row in results.items() if all(row['gates'][method].values())]
                 for method in METHODS}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': results, 'panelsClearingBothGates': qualified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=wider.attribution.PHASES)
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
    result = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
