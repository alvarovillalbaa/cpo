"""Allow exact validation certificates from partially observed prompt pairs."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import independent_mmlu_cost_frontier as frontier
from benchmarks import minimum_proof_budget as previous
from benchmarks import starting_prompt_margin as attribution
from cpo import Row, fixed_pool_cycle
from cpo._contract import digest
from cpo.lazy_incumbent import select_with_lazy_incumbent
from cpo.paired_qualification import certify_paired_qualification
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '76561e0834d8b3a98c2d06c66326dab9c1f582409a280d4ce69e0d24b2caee40'
METHODS = ('row-order', 'row-order-fallback')


def select_partial_pair(incumbent, candidates, validation, evaluate, *, metric_limit, method, audit):
    rows, candidates = tuple(validation), tuple(candidates)
    if (not rows or len({row.id for row in rows}) != len(rows) or
            type(metric_limit) is not int or metric_limit < len(rows) or
            incumbent in candidates or len(set(candidates)) != len(candidates)):
        raise ValueError('Pair search needs distinct cases and prompts with a cap that funds incumbent validation')
    if not candidates:
        return FinalistResult(incumbent, None, 0)
    evidence = {}

    class SearchCapReached(Exception):
        pass

    def observe(prompt, row):
        key = (prompt, row.id)
        if key not in evidence:
            if len(evidence) >= metric_limit:
                raise SearchCapReached
            observation = evaluate(prompt, row)
            if type(observation.passed) is not bool:
                raise ValueError('Pair validation requires exact boolean outcomes')
            evidence[key] = observation
        return evidence[key]

    if method == 'row-order-fallback':
        initial = select_with_lazy_incumbent(incumbent, candidates, rows, observe, metric_limit=metric_limit)
        if initial.finalist is not None:
            return initial
    probed = {prompt for prompt, _ in evidence}
    candidates = tuple(p for p in candidates if p not in probed)
    if not candidates:
        return FinalistResult(incumbent, None, len(evidence))
    base = {case: result.passed for (prompt, case), result in evidence.items() if prompt == incumbent}

    def can_fit():
        # The best possible next reply moves the gain lower bound by one.
        return metric_limit - len(evidence) >= len(rows) + 1 - (len(base) - sum(base.values()))

    witness = None
    for row in rows:
        if row.id not in base:
            if not can_fit():
                break
            base[row.id] = observe(incumbent, row).passed
        if not base[row.id]:
            witness = row
            break
    if witness is None:
        return FinalistResult(incumbent, None, len(evidence))

    original = {row.id: row for row in rows}
    ordered = sorted(rows, key=lambda row: (row != witness, not row.critical, row.id not in base))
    # Validation uses an exact scalar gain. Preserve the original critical flags.
    panel = [Row(row.id, 'validation', row.critical) for row in ordered]
    for challenger in candidates:
        if not can_fit():
            break
        audit['partialPairWitnessCalls'] += 1
        if not observe(challenger, witness).passed:
            continue
        audit['partialPairAttempts'] += 1

        def qualify(prompt, row, _repeat):
            return observe(prompt, original[row.id]).passed

        try:
            outcome = certify_paired_qualification(incumbent, challenger, panel, qualify)
        except SearchCapReached:
            audit['partialPairBudgetStops'] += 1
            return FinalistResult(incumbent, challenger, len(evidence))
        if outcome.status == 'promoted':
            audit['partialPairCertificates'] += 1
            audit['certificatesWithoutFullIncumbent'] += int(sum(p == incumbent for p, _ in evidence) < len(rows))
            return FinalistResult(challenger, challenger, len(evidence))
        return FinalistResult(incumbent, challenger, len(evidence))
    return FinalistResult(incumbent, None, len(evidence))


def run_episode(matrix, held, seed, original, plan, method, cap):
    settings = {'searchCap': cap, 'validationRows': plan['validationRows']}
    counts = Counter(partialPairWitnessCalls=0, partialPairAttempts=0, partialPairBudgetStops=0,
                     partialPairCertificates=0, certificatesWithoutFullIncumbent=0)

    def screen(incumbent, candidates, validation, evaluate, *, metric_limit):
        return select_partial_pair(incumbent, candidates, validation, evaluate,
                                   metric_limit=metric_limit, method=method, audit=counts)

    def select(*args, **kwargs):
        return fixed_pool_cycle.run_fixed_pool_cycle(*args, screen=method, **kwargs)

    with patch.dict(fixed_pool_cycle._SCREENS, {method: screen}), patch.object(archive, 'run_fixed_pool_cycle', select):
        totals, trace = archive.episode(matrix, held, seed, original, settings, 'recency')
    totals.update(counts)
    return totals, trace


def prepare(phase):
    parent, original, data, _ = previous.prepare(phase)
    saved = archive.checked_report('minimum-proof-budget-results-v1.json', SOURCE_SHA256, phase)
    if saved['planSha256'] != digest(parent):
        raise ValueError('The sealed minimum-proof replay differs')
    paths = (Path(__file__), ROOT / 'cpo/paired_qualification.py')
    plan = {
        **{k: parent[k] for k in ('phase', 'gepaVersion', 'validationRows', 'gate', 'caps')},
        'protocol': 'cpo-partial-pair-budget-v1',
        'parentPlanSha256': digest(parent), 'parentReportSha256': SOURCE_SHA256,
        'sourceSha256': {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in paths},
        'methods': list(METHODS),
        'scope': ('Prove a strict scalar validation gain using only available paired observations. '
                  'Count every fresh callback and keep the archive and independent qualification unchanged.'),
    }
    return plan, original, data, saved['panels']


def replay(plan, original, data, prior):
    panels = {}
    for panel in data:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        archived = prior[name]
        cpo = {label: result for label, result in archived['cpo'].items()
               if label.startswith(('seeded-', 'minimum-proof-'))}
        for cap in plan['caps']:
            for method in METHODS:
                totals, traces = Counter(), []
                for seed in original['seeds']:
                    row, trace = run_episode(matrix, held, seed, original, plan, method, cap)
                    totals.update(row)
                    traces.append(trace)
                cpo[f'{method}-{cap}'] = dict(totals, paidLookups=totals['searchPaid'] + totals['qualificationPaid'],
                                             traceSha256=digest(traces))
        panels[name] = {'cpo': cpo, 'retainStart': archived['retainStart'], 'gepa': archived['gepa']}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels, **frontier.summarize(panels)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=attribution.PHASES, required=True)
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
