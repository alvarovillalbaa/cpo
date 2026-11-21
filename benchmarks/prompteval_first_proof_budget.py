"""Compare early CPO challenger certificates to the split-safe GEPA cost frontier."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import prompteval_qualification_case_reuse as prior
from cpo import Observation, Row, select_certified_pool
from cpo._contract import digest
from cpo.challenger import certify_challenger
from cpo.lazy_incumbent import select_with_lazy_incumbent


REFERENCE = prior.ROOT / 'docs/prompteval-qualification-case-reuse-results-v1.json'
REFERENCE_SHA = '8b4f131ab07cf6df635240b8158437e326fd9282c16a41861b84a0c023459308'
CAPS = (56, 72, 88, 136)
RELEASED = 'cpo-cycle'
FIRST = 'first-proof'
SCREENED = 'rank-opening-pair'
HALVING = 'screen-then-prove'
LAZY = 'lazy-incumbent'
PAIRED = 'paired-lazy-incumbent'
WITNESS = 'paired-witness-screen'
ROTATE = 'rotating-witness-screen'
TWO = 'paired-witness-two-finalists'
ROTATE_TWO = 'rotating-witness-two-finalists'
FOLLOWUP = (LAZY, PAIRED, WITNESS, ROTATE, TWO, ROTATE_TWO)
METHODS = (RELEASED, FIRST, SCREENED, HALVING, *FOLLOWUP)
PRIMARY = (72, SCREENED)


def prepare():
    raw = REFERENCE.read_bytes()
    if sha256(raw).hexdigest() != REFERENCE_SHA:
        raise ValueError('The split-safe reference evidence changed')
    reference = json.loads(raw)
    frozen, phases = prior.prepare()
    if frozen != reference['plan'] or digest(frozen) != reference['planSha256']:
        raise ValueError('The sealed reference case schedule and source must reproduce')
    files = ('benchmarks/prompteval_first_proof_budget.py', 'cpo/challenger.py', 'cpo/certified_pool.py',
             'cpo/lazy_incumbent.py', 'cpo/single_finalist.py')
    plan = {'protocol': 'prompteval-first-proof-budget-v1', 'gepaVersion': frozen['gepaVersion'],
            'referenceResultSha256': REFERENCE_SHA, 'referencePlanSha256': reference['planSha256'],
            'sourceSha256': {path: sha256((prior.ROOT / path).read_bytes()).hexdigest() for path in files},
            'primary': {'searchCap': PRIMARY[0], 'method': PRIMARY[1]}, 'cpoCaps': CAPS,
            'methods': METHODS, 'gepaCaps': list(prior.CAPS), 'qualificationPolicy': 'retire-assigned',
            'followUpMethods': FOLLOWUP,
            'scope': 'Keep the full candidate roster, shared validation anchors and independent qualification gate.'}
    return plan, phases, reference


def first_challenger(incumbent, layout, observe, plan, *, rank_opening):
    """Nominate the first strict certificate under the supplied ordered proposal stream."""
    rows = [Row(str(case), 'task') for case in layout['validation']]
    exact = {row.id: observe(incumbent, int(row.id)) for row in rows}
    required = sum(exact.values()) + 1
    remaining = plan['evaluationLookupLimit'] - len(rows)
    if required > min(len(rows), remaining):
        return incumbent
    candidates = layout['alternatives']
    if rank_opening:
        probes = layout['train'][:plan['probeSize']]
        opening = candidates[:2]
        cost = len(probes) * len(opening)
        if required + cost <= remaining:
            def rank(prompt):
                return sum(observe(prompt, case) for case in probes)

            candidates = sorted(opening, key=rank, reverse=True) + candidates[2:]
            remaining -= cost
    for candidate in candidates:
        if required > remaining:
            break
        proof = certify_challenger(rows, exact, lambda row: Observation(observe(candidate, int(row.id)), {}),
                                   metric_limit=remaining)
        if proof.status == 'promote':
            return candidate
        remaining -= proof.evaluations
    return incumbent


def halving_challenger(incumbent, layout, observe, plan):
    rows = [Row(str(case), 'task') for case in layout['validation']]
    return select_certified_pool(
        (incumbent, *layout['alternatives']), rows, lambda p, row: Observation(observe(p, int(row.id)), {}),
        metric_limit=plan['evaluationLookupLimit'],
    ).prompt


def lazy_challenger(incumbent, layout, observe, plan, *, paired_proof):
    rows = [Row(str(case), 'task') for case in layout['validation']]
    return select_with_lazy_incumbent(
        incumbent, layout['alternatives'], rows, lambda p, row: Observation(observe(p, int(row.id)), {}),
        metric_limit=plan['evaluationLookupLimit'], paired_proof=paired_proof,
    ).prompt


def witness_challenger(incumbent, layout, observe, plan, *, rotate=False, finalists=1):
    """Offer a challenger from paired witnesses, leaving promotion to qualification."""
    first_pass, first_miss = None, None
    remaining = plan['evaluationLookupLimit']
    validation = list(layout['validation'])
    if rotate:
        Random(layout['seed']).shuffle(validation)
    for case in validation:
        if not remaining:
            return incumbent
        passed = observe(incumbent, case)
        remaining -= 1
        if passed and first_pass is None:
            first_pass = case
        elif not passed and first_miss is None:
            first_miss = case
        if first_pass is not None and first_miss is not None:
            break
    if first_miss is None:
        return incumbent
    worst_case = 1 + int(first_pass is not None)
    eligible = []
    for prompt in layout['alternatives']:
        if remaining < worst_case:
            break
        passed = observe(prompt, first_miss)
        remaining -= 1
        if passed:
            safe = first_pass is None or observe(prompt, first_pass)
            remaining -= int(first_pass is not None)
            if safe:
                eligible.append(prompt)
                if len(eligible) == finalists:
                    break
    if not eligible:
        return incumbent
    tie_case = next((case for case in validation if case not in (first_miss, first_pass)), None)
    if len(eligible) > 1 and remaining >= len(eligible) and tie_case is not None:
        return max(eligible, key=lambda prompt: observe(prompt, tie_case))
    return eligible[0]


def measure_panel(matrix, holdout, plan, reference):
    episodes = []
    selectors = {FIRST: partial(first_challenger, rank_opening=False),
                 SCREENED: partial(first_challenger, rank_opening=True), HALVING: halving_challenger,
                 LAZY: partial(lazy_challenger, paired_proof=False),
                 PAIRED: partial(lazy_challenger, paired_proof=True), WITNESS: witness_challenger,
                 ROTATE: partial(witness_challenger, rotate=True), TWO: partial(witness_challenger, finalists=2),
                 ROTATE_TWO: partial(witness_challenger, rotate=True, finalists=2)}
    controls = {(cap, method): reference['caps'][str(cap)]['totals']['retire-assigned'][method]
                for cap in prior.CAPS for method in prior.continuous.GEPA}
    run = prior.search

    def choose(method, incumbent, layout, observe, active):
        selector = selectors.get(method)
        if selector is None:
            return run(method, incumbent, layout, observe, active)
        return selector(incumbent, layout, observe, active)

    with patch.object(prior, 'search', choose):
        for seed in plan['seeds']:
            initial, layouts = prior.schedule(len(matrix[0]), len(matrix), holdout, seed, plan)
            receipts = {}
            for cap in CAPS:
                active = {**plan, 'evaluationLookupLimit': cap}
                for arm in METHODS:
                    receipts[cap, arm] = prior.run_arm(matrix, holdout, initial, layouts, active, arm, 'retire-assigned')
            episodes.append(receipts)

    totals, trace = {}, {}
    for cap in CAPS:
        totals[cap], trace[cap] = {}, {}
        for method in METHODS:
            runs = [episode[cap, method] for episode in episodes]
            counts = Counter()
            for _, receipt, _ in runs:
                counts.update(receipt)
            totals[cap][method] = counts
            trace[cap][method] = digest([(candidate, fingerprint) for candidate, _, fingerprint in runs])
        if cap in prior.CAPS and totals[cap][RELEASED] != reference['caps'][str(cap)]['totals']['retire-assigned'][RELEASED]:
            raise ValueError('The released CPO receipts did not reproduce at a reference budget')
    return {'cpoByCap': totals, 'nativeControls': {cap: {method: controls[cap, method] for method in prior.continuous.GEPA}
                                              for cap in prior.CAPS}, 'cpoTraceSha256': trace}


def targets_by_panel(reference):
    panels = {}
    for cap, cohorts in reference['caps'].items():
        for phase, cases in cohorts.items():
            for name, row in cases.items():
                panels.setdefault((phase, name), {'caps': {}})['caps'][cap] = row
    return panels


def measure(phases, reference):
    expected = targets_by_panel(reference)
    results = {}
    for phase, (plan, data) in phases.items():
        panels = {}
        for panel in data['panels']:
            subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
            key = f'{subject}/{model}'
            panels[key] = measure_panel(matrix, plan['holdoutCaseIDs'][subject], plan, expected[phase, key])
        results[phase] = panels
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, phases, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != '0.1.4':
        parser.error('Use the current seal, pinned GEPA 0.1.4, and a fresh receipt path')
    result = {'plan': plan, 'planSha256': seal, 'phases': measure(phases, reference), 'newProviderRequests': 0}
    with args.out.open('x') as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write('\n')


if __name__ == '__main__':
    main()
