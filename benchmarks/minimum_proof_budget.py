"""Spend a tight CPO search cap on a provable gain without reserving a full finalist panel."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import independent_mmlu_cost_frontier as independent
from benchmarks import paid_budget_frontier as frontier
from benchmarks import starting_prompt_margin as attribution
from cpo import fixed_pool_cycle
from cpo._contract import digest, unique_object
from cpo.challenger import certify_challenger
from cpo.lazy_incumbent import select_with_lazy_incumbent
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
INDEPENDENT_SHA256 = '1038005684d3475e4cf05f593423f6e4e7e3c71058b006c16a0c82ba04938efa'
TRANSFER_SHA256 = '1ba8cc12dd25bd11b050ad28b006621af1cc871825d2ea7536a6b9a250935f5b'
CAPS = (24, 28, 32)
POLICIES = ('seeded', 'minimum-proof', 'fallback-minimum-proof')


def select_with_minimum_proof(incumbent, candidates, validation, evaluate, *, metric_limit, fallback, audit):
    rows, candidates = tuple(validation), tuple(candidates)
    if (not rows or len({row.id for row in rows}) != len(rows) or
            type(metric_limit) is not int or metric_limit < len(rows) or
            incumbent in candidates or len(set(candidates)) != len(candidates)):
        raise ValueError('Proof search needs a distinct roster and a cap that funds the incumbent')
    evidence = {}

    def observe(prompt, row):
        key = (prompt, row.id)
        if key not in evidence:
            if len(evidence) >= metric_limit:
                raise ValueError('Proof search exceeded its lookup cap')
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Proof search requires exact boolean outcomes')
            evidence[key] = reply
        return evidence[key]

    first = (select_with_lazy_incumbent(incumbent, candidates, rows, observe, metric_limit=metric_limit)
             if fallback else FinalistResult(incumbent, None, 0))
    if first.finalist is not None:
        return first
    seen = {prompt for prompt, _ in evidence}
    challengers = [p for p in candidates if p not in seen]
    if not challengers:
        return first
    remaining = metric_limit - len(evidence)
    base = {case: reply.passed for (prompt, case), reply in evidence.items() if prompt == incumbent}
    needed = sum(base.values()) + 1
    for row in rows:
        if row.id not in base:
            missing = len(rows) - len(base)
            if remaining < missing + needed:
                return FinalistResult(incumbent, None, len(evidence))
            passed = observe(incumbent, row).passed
            base[row.id] = passed
            needed += passed
            remaining -= 1
    miss = next((row for row in rows if not base[row.id]), None)
    if miss is None:
        return FinalistResult(incumbent, None, len(evidence))
    ordered = sorted(rows, key=lambda row: base[row.id])
    for prompt in challengers:
        if remaining < needed:
            break
        audit['minimumProofWitnessCalls'] += 1
        passed = observe(prompt, miss).passed
        remaining -= 1
        if passed:
            audit['minimumProofAttempts'] += 1
            proof = certify_challenger(ordered, base, lambda row: observe(prompt, row),
                                       metric_limit=remaining, observed={miss.id: True})
            audit['minimumProofCertificates'] += int(proof.status == 'promote')
            selected = prompt if proof.status == 'promote' else incumbent
            return FinalistResult(selected, prompt, len(evidence))
    return FinalistResult(incumbent, None, len(evidence))


def run_episode(matrix, held, seed, original, plan, policy, cap):
    settings = {'validationRows': plan['validationRows'], 'searchCap': cap}
    if policy == 'seeded':
        return archive.episode(matrix, held, seed, original, settings, 'recency')
    counts = Counter(minimumProofWitnessCalls=0, minimumProofAttempts=0, minimumProofCertificates=0)

    def screen(incumbent, candidates, validation, evaluate, *, metric_limit):
        return select_with_minimum_proof(incumbent, candidates, validation, evaluate,
                                         metric_limit=metric_limit, fallback=policy == 'fallback-minimum-proof',
                                         audit=counts)

    def select(*args, **kwargs):
        return fixed_pool_cycle.run_fixed_pool_cycle(*args, screen=policy, **kwargs)

    with patch.dict(fixed_pool_cycle._SCREENS, {policy: screen}), patch.object(archive, 'run_fixed_pool_cycle', select):
        totals, trace = archive.episode(matrix, held, seed, original, settings, 'recency')
    totals.update(counts)
    return totals, trace


def prepare(phase):
    parent, original, data, _, _ = attribution.prepare(phase)
    if phase == 'independent':
        past, *_ = independent.prepare()
        source_path = ROOT / 'docs/independent-mmlu-cost-frontier-results-v1.json'
        expected = INDEPENDENT_SHA256
    else:
        past, _ = frontier.prepare()
        source_path = ROOT / 'docs/paid-budget-frontier-results-v1.json'
        expected = TRANSFER_SHA256
    raw = source_path.read_bytes()
    published = json.loads(raw, object_pairs_hook=unique_object)
    if sha256(raw).hexdigest() != expected or digest(past) != published['planSha256']:
        raise ValueError('The measured cost frontier differs from its sealed report')
    if min(CAPS) < parent['validationRows'] + original['qualificationRowsPerCycle']:
        raise ValueError('The lowest cap must still fund incumbent validation after archive charges')
    plan = {
        **{k: parent[k] for k in ('phase', 'gepaVersion', 'validationRows', 'gate')},
        'protocol': 'cpo-minimum-proof-budget-v1',
        'parentPlanSha256': digest(parent), 'costFrontierPlanSha256': digest(past),
        'costFrontierReportSha256': expected, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'caps': list(CAPS), 'policies': list(POLICIES),
        'scope': ('Offer a strict certificate when its mathematical minimum fits. Keep the archive, '
                  'independent qualification and per-cycle search ceilings fixed.'),
    }
    return plan, original, data, published['panels']


def replay(plan, original, data, published):
    panels = {}
    for panel in data:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        prior = published[name]
        fixed = prior['cpo']['seeded-28'] if plan['phase'] == 'independent' else prior[frontier.gepa.CPO]['28']
        controls = prior['gepa'] if plan['phase'] == 'independent' else {m: prior[m] for m in frontier.gepa.METHODS}
        retained = 0
        for seed in original['seeds']:
            start, _ = archive.continuous.schedule(len(matrix[0]), len(matrix), held, seed, original)
            retained += sum(matrix[int(start)][case] == '1' for case in held)
        cpo = {}
        for cap in CAPS:
            for policy in POLICIES:
                costs, traces = Counter(), []
                for seed in original['seeds']:
                    total, trace = run_episode(matrix, held, seed, original, plan, policy, cap)
                    costs.update(total)
                    traces.append(trace)
                row = dict(costs, paidLookups=costs['searchPaid'] + costs['qualificationPaid'], traceSha256=digest(traces))
                if policy == 'seeded' and cap == 28:
                    independent.expect_reference(row, fixed)
                cpo[f'{policy}-{cap}'] = row
        panels[name] = {'cpo': cpo, 'gepa': controls, 'retainStart': retained}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels, **independent.summarize(panels)}


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
    report = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
