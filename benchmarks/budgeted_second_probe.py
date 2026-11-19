"""Compare wider validation screens within the original fixed-pool lookup cap."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import episode_screen_adaptation as screens
from benchmarks import starting_prompt_margin as attribution
from benchmarks.prompteval_paid_witness import meets_gate
from cpo import select_certified_pool
from cpo._contract import digest
from cpo.challenger import certify_challenger
from cpo import fixed_pool_cycle
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTION_SHA256 = '170adf9251518020255bd5d8d7a272f5578bb6f997e17c1acbb33833c4440d39'
METHODS = ('seeded', 'certified-halving', 'confirm-first-passes', 'recheck-first-failures')
PUBLISHED_FIELDS = ('holdoutPasses', 'paidLookups', 'searchLogical', 'searchPaid', 'qualificationPaid', 'traceSha256')


def select_with_second_probe(incumbent, candidates, validation, evaluate, *, metric_limit, recheck, audit):
    """Read a shared miss, then fund a second probe without consuming the first proof reserve."""
    rows, candidates = tuple(validation), tuple(candidates)
    if (not rows or len({r.id for r in rows}) != len(rows) or metric_limit < len(rows) or
            incumbent in candidates or len(set(candidates)) != len(candidates)):
        raise ValueError('Search needs distinct rows and prompts with enough budget for the incumbent')
    if not candidates:
        return FinalistResult(incumbent, None, 0)
    ledger = {}

    def observe(prompt, row):
        key = (prompt, row.id)
        if key not in ledger:
            if len(ledger) >= metric_limit:
                raise ValueError('Second probe exceeded the search ceiling')
            observation = evaluate(prompt, row)
            if type(observation.passed) is not bool:
                raise ValueError('Exact search requires boolean evidence')
            ledger[key] = observation
        return ledger[key]

    base = {row.id: observe(incumbent, row).passed for row in rows}
    misses = [row for row in rows if not base[row.id]]
    if not misses:
        return FinalistResult(incumbent, None, len(ledger))
    first = misses[0]
    second = misses[1] if len(misses) > 1 else min((row for row in rows if base[row.id]),
                                                 key=lambda row: not row.critical, default=None)
    reserve = len(rows) - 1
    offered = candidates[:max(0, metric_limit - len(ledger) - reserve)]
    scores = {prompt: {first.id: observe(prompt, first).passed} for prompt in offered}
    audit['firstProbes'] += len(offered)
    if second is not None:
        depth = metric_limit - len(ledger) - reserve
        preferred_outcome = not recheck
        order = sorted(offered, key=lambda p: scores[p][first.id] != preferred_outcome)
        for prompt in order[:depth]:
            scores[prompt][second.id] = observe(prompt, second).passed
            audit['secondProbes'] += 1

    def priority(prompt):
        evidence = scores[prompt]
        return Fraction(sum(evidence.values()) + 1, len(evidence) + 2)

    eligible = (p for p in offered if any(passed and not base[case] for case, passed in scores[p].items()))
    shortlist = sorted(eligible, key=priority, reverse=True)[:2]
    order = sorted(rows, key=lambda row: base[row.id])
    attempted = None
    for prompt in shortlist:
        if metric_limit - len(ledger) < len(rows) - len(scores[prompt]):
            break
        attempted = prompt
        audit['certificateAttempts'] += 1
        decision = certify_challenger(order, base, lambda row: observe(prompt, row),
                                      metric_limit=metric_limit - len(ledger), observed=scores[prompt])
        if decision.status == 'promote':
            audit['certificates'] += 1
            return FinalistResult(prompt, prompt, len(ledger))
    return FinalistResult(incumbent, attempted, len(ledger))


def select_halving(incumbent, candidates, validation, evaluate, *, metric_limit):
    selected = select_certified_pool((incumbent, *candidates), validation, evaluate, metric_limit=metric_limit)
    return FinalistResult(selected.prompt, selected.prompt if selected.prompt != incumbent else None,
                          selected.evaluations)


def run_episode(matrix, held, seed, original, plan, method):
    if method == 'seeded':
        return archive.episode(matrix, held, seed, original, plan, 'recency')
    counts = Counter(firstProbes=0, secondProbes=0, certificateAttempts=0, certificates=0)

    def screen(incumbent, candidates, validation, evaluate, *, metric_limit):
        if method == 'certified-halving':
            return select_halving(incumbent, candidates, validation, evaluate, metric_limit=metric_limit)
        return select_with_second_probe(incumbent, candidates, validation, evaluate,
                                        metric_limit=metric_limit, recheck=method == 'recheck-first-failures',
                                        audit=counts)

    def select(*args, **kwargs):
        return fixed_pool_cycle.run_fixed_pool_cycle(*args, screen=method, **kwargs)

    with patch.dict(fixed_pool_cycle._SCREENS, {method: screen}), patch.object(archive, 'run_fixed_pool_cycle', select):
        totals, trace = archive.episode(matrix, held, seed, original, plan, 'recency')
    totals.update(counts)
    return totals, trace


def prepare(phase):
    source, original, data, controls, _ = attribution.prepare(phase)
    previous = archive.checked_report('starting-prompt-margin-results-v1.json', ATTRIBUTION_SHA256, phase)
    if previous['planSha256'] != digest(source):
        raise ValueError('The loss attribution differs from its published seal')
    plan = {
        **{key: source[key] for key in ('phase', 'searchCap', 'validationRows', 'gepaVersion', 'gate')},
        'protocol': 'cpo-budgeted-second-probe-v1', 'parentPlanSha256': digest(source),
        'measuredAttributionSha256': ATTRIBUTION_SHA256,
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'halvingSha256': sha256((ROOT / 'cpo/certified_pool.py').read_bytes()).hexdigest(),
        'methods': list(METHODS), 'secondProbeReserve': 'Complete one candidate after its first probe.',
        'certificateLimit': 2,
        'scope': ('Use the original search cap, proposal order, recency archive and qualification gate. '
                  'Measure broader screening and reuse the published strict-gain loss set for attribution only.'),
    }
    return plan, original, data, controls, previous['panels']


def replay(plan, original, data, controls, published):
    panels = {}
    for panel in data:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        audited = {row['seed']: row for row in published[name]['seededLossesToBatched']
                   if row['reason'] == 'strict-gain-winner-missed-by-screen'}
        methods, scores = {}, {}
        for method in METHODS:
            total, journals, cases = Counter(), [], []
            scores[method] = []
            for seed in original['seeds']:
                observed, trace = run_episode(matrix, held, seed, original, plan, method)
                decisions = [step['decision'] for step in trace]
                total.update(observed)
                journals.append(trace)
                scores[method].append(observed['holdoutPasses'])
                if seed in audited:
                    prior = audited[seed]
                    winner = prior['gepaWinner']
                    cases.append({'seed': seed, 'holdoutPasses': observed['holdoutPasses'],
                                  'gepaHoldoutPasses': prior['gepaHoldoutPasses'],
                                  'gepaWinnerReachedQualification': any(
                                      winner in (row['challenger'], row['archiveNominee']) for row in decisions),
                                  'matchedGepa': observed['holdoutPasses'] >= prior['gepaHoldoutPasses']})
            result = dict(total, paidLookups=total['searchPaid'] + total['qualificationPaid'],
                          traceSha256=digest(journals), strictGainLossAudit=cases,
                          pairedPassesVsSeeded=screens.paired_deltas(scores[method], scores['seeded']))
            if method == 'seeded' and any(result[k] != published[name]['methods'][method][k] for k in PUBLISHED_FIELDS):
                raise ValueError(f'{name} differs from the published seeded trace')
            methods[method] = result
        gepa = {key: {k: r[k] for k in ('holdoutPasses', 'paidLookups')} for key, r in controls[name].items()}
        gates = {method: {m: meets_gate(result, ref) for m, ref in gepa.items()} for method, result in methods.items()}
        panels[name] = {'methods': methods, 'gepa': gepa, 'gates': gates}
    qualified = {method: [name for name, panel in panels.items() if all(panel['gates'][method].values())]
                 for method in METHODS}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels, 'panelsClearingBothGates': qualified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=attribution.PHASES)
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
