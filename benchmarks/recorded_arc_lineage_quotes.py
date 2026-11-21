"""Replay later proposals from ARC's actual archived parent links."""

import argparse
from collections import Counter, deque
from contextlib import nullcontext
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks.recorded_math_validation_ties import CORPUS, CORPUS_SHA, ROOT
from cpo._contract import digest


FIXTURE_SHA256 = '3526271453946cb262bf48634119e3def78e2518742b91a8aa20f2b322bd179d'
SEEDS = tuple(range(16141, 16901, 19))
COHORTS = (18, 8, 6, 48)
READ_LIMIT = 64
QUOTE_UNITS = (32, 60)
REFLECTION_QUOTES = (1, 4)
MODES = {'gepa-sequential': 1, 'gepa-batched': 2, 'cpo-shared-budget': 0, 'cpo-supplied-only': 0}
RESTRICTED = tuple(mode for mode in MODES if mode != 'cpo-supplied-only')


def load_archive():
    raw = CORPUS.read_bytes()
    if sha256(raw).hexdigest() != CORPUS_SHA:
        raise ValueError('The recorded ARC and AIME corpus differs from its pinned copy')
    archive = json.loads(raw)['arc']
    if archive['fixtureSha256'] != FIXTURE_SHA256:
        raise ValueError('The ARC source fingerprint differs')
    doc = archive['record']
    cases, candidates = doc['cases'], doc['candidates']
    scores, children = {}, {}
    if len(cases) != sum(COHORTS) or len(set(cases)) != len(cases):
        raise ValueError('The cohort sizes must partition the distinct ARC problems')
    for row in candidates:
        index, parent_ids = row['id'], row['parentIds']
        prompt = f'arc-{index:02d}'
        if prompt in scores or len(row['rows']) != len(cases):
            raise ValueError('The ARC score table must cover each architecture and problem once')
        scores[prompt] = {}
        children[prompt] = []
        for parent in parent_ids:
            if parent is None and index == 0:
                continue
            children[f'arc-{parent:02d}'].append(prompt)
        for case, (passed, cost, error) in zip(cases, row['rows'], strict=True):
            if (type(passed) is not int or passed not in (0, 1)
                    or type(cost) is not int or cost < 0 or type(error) is not bool):
                raise ValueError('Invalid ARC score or evaluation cost')
            scores[prompt][case] = passed, cost
        if sum(passed for passed, _ in scores[prompt].values()) != row['sourceSolved']:
            raise ValueError('ARC fixture scores disagree with the recorded solved count')
    return cases, scores, children


def native_available_parents(eligible):
    from gepa.gepa_utils import select_program_candidate_from_pareto_front
    from gepa.strategies.candidate_selector import ParetoCandidateSelector

    original = ParetoCandidateSelector.select_candidate_idx

    def select(selector, state):
        indices = tuple(index for index, candidate in enumerate(state.program_candidates)
                        if eligible(next(iter(candidate.values()))))
        if len(indices) == len(state.program_candidates):
            return original(selector, state)
        if not indices:
            raise ValueError('Stop before scheduling a GEPA round with no eligible proposal parent')
        profiles = state.prog_candidate_val_subscores
        fronts = {}
        for case in state.pareto_front_valset:
            best = max(profiles[index][case] for index in indices)
            fronts[case] = {index for index in indices if profiles[index][case] == best}
        return select_program_candidate_from_pareto_front(fronts, state.per_program_tracked_scores, selector.rng)

    return patch.object(ParetoCandidateSelector, 'select_candidate_idx', select)


def play(mode, initial, cohorts, scores, orders, seed, evaluate_quote, proposal_quote, ceiling, *,
         stop_on_exhaustion, available_parents=False):
    from benchmarks import gepa_disjoint_cases as native, grounded
    from benchmarks.gepa_sequential_schedule import native_with_price_guard, select_field_rewrites
    from cpo import Observation, Row
    from cpo.family_qualification import certify_family_qualification
    from cpo.sequential_field_rewrite import SequentialSearchBudget

    train, validation, admission, heldout = cohorts
    allowed = set(train + validation)
    opened = tuple(orders[initial][:2])
    queues = {parent: deque(child for child in children if child not in opened) for parent, children in orders.items()}
    groups = {name: [{'id': case, 'expected': {'solved': True}} for case in cohort]
              for name, cohort in (('train', train), ('validation', validation))}
    paid, proposals, admitted = {}, [], {}
    used_reflection = supplied = 0

    def evaluate(prompt, case):
        if case not in allowed or (prompt, case) in paid or len(paid) >= READ_LIMIT:
            raise ValueError('ARC search exceeded its paid reads or crossed a cohort boundary')
        passed, charge = scores[prompt][case]
        paid[prompt, case] = charge
        return Observation(bool(passed), {'id': case, 'observed': bool(passed)}, passed)

    def reflect(parent, _feedback):
        nonlocal used_reflection
        child = queues[parent].popleft() if queues[parent] else None
        proposals.append((parent, child))
        if child is None:
            return parent
        used_reflection += proposal_quote
        return child

    def quote(index, _parent=None):
        return 0 if index < len(opened) else proposal_quote

    def tracked_children(pool):
        return any(queues[parent] for parent in pool)

    width = MODES[mode]
    if width:
        def can_fund_round(index):
            reserved_reads = width * (2 * grounded.MINIBATCH + len(validation))
            reserved_proposals = sum(quote(slot) for slot in range(index * width, (index + 1) * width))
            return sum(paid.values()) + used_reflection + reserved_reads * evaluate_quote + reserved_proposals <= ceiling

        if stop_on_exhaustion:
            def observed_opening():
                nonlocal supplied
                for proposal in opened:
                    supplied += 1
                    yield proposal

            def exhausted(state):
                pool = (next(iter(candidate.values())) for candidate in state.program_candidates)
                return supplied == len(opened) and not tracked_children(pool)

            module = import_module('gepa.optimize_anything')
            optimize = module.optimize_anything

            def stopped(*args, config, **kwargs):
                config.stop_callbacks = [*config.stop_callbacks, exhausted]
                return optimize(*args, config=config, **kwargs)

            availability, bank = patch.object(module, 'optimize_anything', stopped), observed_opening()
        else:
            availability, bank = nullcontext(), opened
        parent_selection = (native_available_parents(lambda parent: supplied < len(opened) or bool(queues[parent]))
                            if available_parents else nullcontext())
        with availability, parent_selection:
            nominee = native_with_price_guard(native.select, can_fund_round, initial, bank, groups, evaluate,
                                              reflect, cap=READ_LIMIT, seed=seed, width=width)
    else:
        def settle(index, parent, child):
            return 0 if index < len(opened) or child == parent else proposal_quote

        budget = SequentialSearchBudget(ceiling, evaluate_quote, quote, settle,
                                        proposal_limit=0 if mode == 'cpo-supplied-only' else None)

        def exhausted(index, pool):
            return index >= len(opened) and not tracked_children(pool)

        def eligible(index, parent):
            return index < len(opened) or bool(queues[parent])

        nominee = select_field_rewrites(initial, opened, groups, evaluate, reflect, [], cap=READ_LIMIT, seed=seed,
                                        reinvest_savings=True, price_budget=budget, parent_bounds=True,
                                        certify_boundary_ties=True, skip_perfect_reflections=True,
                                        observed_charge=lambda prompt, row, _: paid[prompt, row.id],
                                        proposals_exhausted=exhausted if stop_on_exhaustion else None,
                                        parent_eligible=eligible if available_parents else None)

    def qualify(prompt, row, repeat):
        if row.id not in admission or repeat != 0 or (prompt, row.id) in admitted:
            raise ValueError('ARC admission crossed the held-out boundary')
        passed, charge = scores[prompt][row.id]
        admitted[prompt, row.id] = charge
        return bool(passed)

    rows = [Row(case, 'arc') for case in admission]
    decision = certify_family_qualification(initial, nominee, rows, qualify, seed=seed)
    if sum(paid.values()) + used_reflection > ceiling or (mode == 'cpo-supplied-only' and proposals):
        raise ValueError('ARC search exceeded its search or proposal allowance')
    observed = {case: scores[decision.prompt][case][0] for case in heldout}
    return {'nominee': nominee, 'selected': decision.prompt, 'passes': observed,
            'recordedEvaluationCostNanodollars': sum(paid.values()) + sum(admitted.values()),
            'hypotheticalProposalCostNanodollars': used_reflection,
            'searchReads': len(paid), 'admissionReads': len(admitted),
            'laterSlots': len(proposals), 'recordedChildren': sum(child is not None for _, child in proposals)}


def summarize(paths, *, arms=tuple(MODES), comparisons=None):
    if comparisons is None:
        comparisons = {mode: arms[:2] for mode in arms[2:]}
    totals = {mode: Counter() for mode in arms}
    paired = {mode: {control: Counter(gains=0, losses=0, changedPaths=0) for control in controls}
              for mode, controls in comparisons.items()}
    blocks = {mode: {control: Counter() for control in controls} for mode, controls in comparisons.items()}
    starts = {}

    for seed, initial, outcomes in paths:
        by_start = starts.setdefault(initial, {mode: Counter() for mode in arms})
        for mode, row in outcomes.items():
            sums = {'holdoutPasses': sum(row['passes'].values()), **{name: value for name, value in row.items()
                                                                 if type(value) is int}}
            totals[mode].update(sums)
            by_start[mode].update(sums)
        for mode, controls in paired.items():
            for control, counts in controls.items():
                a, b = (outcomes[key]['passes'] for key in (mode, control))
                if a.keys() != b.keys():
                    raise ValueError('ARC comparison used different held-out cells')
                differences = {case: value - b[case] for case, value in a.items()}
                counts.update(gains=sum(delta > 0 for delta in differences.values()),
                              losses=sum(delta < 0 for delta in differences.values()),
                              changedPaths=any(differences.values()))
                blocks[mode][control].update(differences)

    for mode, controls in paired.items():
        for control, outcome in controls.items():
            diffs = tuple(blocks[mode][control].values())
            rng = Random(58613)
            draws = sorted(sum(rng.choices(diffs, k=len(diffs))) for _ in range(1999))
            for price in ('recordedEvaluationCostNanodollars', 'hypotheticalProposalCostNanodollars'):
                outcome[price + 'Saved'] = totals[control][price] - totals[mode][price]
            outcome['caseBlockRange95'] = [draws[49], draws[1948]]
    return {'pathsPerArm': len(paths), 'totals': totals, 'paired': paired, 'byStart': starts, 'traceSha256': digest(paths)}


def split(cases, seed):
    order = list(cases)
    Random(seed).shuffle(order)
    train_size, validation_size, admission_size, _ = COHORTS
    validation_end = train_size + validation_size
    admission_end = validation_end + admission_size
    return order[:train_size], order[train_size:validation_end], order[validation_end:admission_end], order[admission_end:]


def prepare(cases):
    files = ('benchmarks/recorded_arc_lineage_quotes.py', 'benchmarks/recorded_math_validation_ties.py',
             'benchmarks/gepa_disjoint_cases.py', 'benchmarks/gepa_sequential_schedule.py',
             'benchmarks/opening_screen_typed.py', 'benchmarks/grounded.py', 'cpo/__init__.py', 'cpo/_contract.py',
             'cpo/optimizer.py', 'cpo/sequential_field_rewrite.py', 'cpo/gepa_parent.py',
             'cpo/paired_field_rewrite.py', 'cpo/_paired_read_order.py', 'cpo/family_qualification.py',
             'cpo/paired_qualification.py', 'requirements-benchmark.txt')
    policy = {'data': 'published recorded ARC correctness, evaluation costs, and parent links',
              'licenseSha256': sha256((CORPUS.parent / 'LICENSE.gepa-artifact').read_bytes()).hexdigest(),
              'generation': 'follow recorded children with hypothetical proposal charges',
              'holdout': 'scores are available only after search and separate admission'}
    return {'protocol': 'cpo-recorded-arc-lineage-quotes-v1', 'gepaVersion': '0.1.4',
            'corpusSha256': CORPUS_SHA, 'fixtureSha256': FIXTURE_SHA256,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in files},
            'dataPolicy': policy, 'dataPolicyFingerprint': digest(policy),
            'sampleManifestSha256': digest([(seed, split(cases, seed)) for seed in SEEDS]),
            'arms': tuple(MODES), 'seeds': SEEDS, 'cohortSizes': COHORTS, 'readCeiling': READ_LIMIT,
            'searchQuoteUnits': QUOTE_UNITS, 'reflectionQuoteMultipliers': REFLECTION_QUOTES}


def measure(cases, scores, children):
    if version('gepa') != '0.1.4':
        raise ValueError('Use pinned native GEPA 0.1.4')
    quote = max(charge for rows in scores.values() for _, charge in rows.values())
    points, stopped = {}, {}
    for units in QUOTE_UNITS:
        points[units], stopped[units] = {}, {}
        for multiplier in REFLECTION_QUOTES:
            paths, finite = [], []
            for seed in SEEDS:
                cohorts = split(cases, seed)
                for start in (parent for parent, child in children.items() if child):
                    rnd = Random(f'{seed}/{start}')
                    orders = {parent: rnd.sample(child, len(child)) for parent, child in children.items()}
                    for entries, stop in ((paths, False), (finite, True)):
                        outcomes = {arm: play(arm, start, cohorts, scores, orders, seed, quote, quote * multiplier,
                                              units * quote, stop_on_exhaustion=stop) for arm in MODES}
                        entries.append((seed, start, outcomes))
            points[units][multiplier] = summarize(paths)
            stopped[units][multiplier] = summarize(finite)
            for before, after in zip(paths, finite, strict=True):
                for arm in MODES:
                    old, new = before[2][arm], after[2][arm]
                    if any(old[field] != new[field] for field in ('nominee', 'selected', 'passes', 'recordedChildren')):
                        raise ValueError('The exhaustion control changed a decision or an available child')
    return {'schema': 'cpo-arc-recorded-lineage-quote-v1', 'fixtureSha256': FIXTURE_SHA256, 'seeds': SEEDS,
            'cohortSizes': COHORTS, 'evaluationQuoteNanodollars': quote, 'readCeiling': READ_LIMIT,
            'quoteMultipliers': REFLECTION_QUOTES, 'points': points, 'exhaustionAware': stopped, 'newProviderRequests': 0}


def availability_plan(cases):
    plan = prepare(cases)
    return {**plan, 'protocol': 'cpo-recorded-arc-parent-availability-v1',
            'availableParentArms': RESTRICTED, 'stopOnExhaustion': True,
            'parentEligibility': 'After supplied openings, give all policies the same remaining-child predicate. '
                                 'Only parent selection uses eligibility. Tracked candidates remain in selection.'}


def measure_availability(cases, scores, children):
    if version('gepa') != '0.1.4':
        raise ValueError('Use pinned native GEPA 0.1.4')
    quote = max(charge for rows in scores.values() for _, charge in rows.values())
    variants = {mode: mode + '-available' for mode in RESTRICTED}
    comparisons = {variant: [mode] for mode, variant in variants.items()}
    comparisons[variants['cpo-shared-budget']].extend(variants[mode] for mode in RESTRICTED[:2])
    starts = tuple(parent for parent, child in children.items() if child)
    results = {}
    for units in QUOTE_UNITS:
        results[units] = {}
        for multiplier in REFLECTION_QUOTES:
            control, combined = [], []
            for seed in SEEDS:
                cohorts = split(cases, seed)
                for start in starts:
                    rng = Random(f'{seed}/{start}')
                    orders = {parent: rng.sample(child, len(child)) for parent, child in children.items()}
                    args = start, cohorts, scores, orders, seed, quote, quote * multiplier, units * quote
                    original = {mode: play(mode, *args, stop_on_exhaustion=True) for mode in MODES}
                    variants_at_start = {arm: play(mode, *args, stop_on_exhaustion=True, available_parents=True)
                                         for mode, arm in variants.items()}
                    control.append((seed, start, original))
                    combined.append((seed, start, {**original, **variants_at_start}))
            results[units][multiplier] = {
                'controlTraceSha256': digest(control),
                **summarize(combined, arms=(*MODES, *variants.values()), comparisons=comparisons),
            }
    return {'evaluationQuoteNanodollars': quote, 'points': results, 'newProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--available-parents', action='store_true')
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    cases, scores, children = load_archive()
    plan = availability_plan(cases) if args.available_parents else prepare(cases)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Use the current seal and a fresh output path')
    replay = measure_availability if args.available_parents else measure
    result = replay(cases, scores, children)
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'comparison': result}, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
