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
SKIP_EMPTY = 'cpo-skip-empty-slots'
NATIVE_RESERVES = ('full-round', 'available-slots')


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


class FiniteProposalSampling:
    """Draw the native schedule before pruning slots without a proposal."""

    def __init__(self, native_sampling, capacity, admit):
        self.native_sampling = native_sampling
        self.capacity = capacity
        self.admit = admit
        self.skipped = 0
        self.denied = False

    def sample_tasks(self, state, candidate_selector, batch_sampler, trainset):
        tasks = self.native_sampling.sample_tasks(state, candidate_selector, batch_sampler, trainset)
        if not tasks:
            return tasks
        parent = next(iter(tasks[0].parent_candidate.values()))
        if any(task.parent_idx != tasks[0].parent_idx for task in tasks):
            raise ValueError('Finite proposal sampling requires a single parent per round')
        funded = tasks[:self.capacity(parent)]
        self.skipped += len(tasks) - len(funded)
        if funded and self.admit is not None and not self.admit(parent, funded):
            self.denied = True
            return []
        return funded


def play(mode, initial, cohorts, scores, orders, seed, evaluate_quote, proposal_quote, ceiling, *,
         stop_on_exhaustion, available_parents=False, skip_empty_slots=False, native_reserve=None,
         frontier_bounds=False, prioritize_uncertain_cases=False, settle_validation_on_price_limit=False,
         schedule_trace=None):
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
    used_reflection = supplied = skipped = 0

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
        if native_reserve is not None and (not stop_on_exhaustion or native_reserve not in NATIVE_RESERVES):
            raise ValueError('Native finite sampling requires a known reserve and exhaustion stopping')

        def can_fund_tasks(parent, tasks):
            cached = {(parent, case) for task in tasks for case in task.minibatch_ids}
            reads = len(cached - paid.keys()) + sum(len(task.minibatch_ids) + len(validation) for task in tasks)
            later = max(0, len(tasks) - (len(opened) - supplied))
            return (len(paid) + reads <= READ_LIMIT
                    and sum(paid.values()) + used_reflection + reads * evaluate_quote + later * proposal_quote <= ceiling)

        def can_fund_round(index):
            reserved_reads = width * (2 * grounded.MINIBATCH + len(validation))
            reserved_proposals = sum(quote(slot) for slot in range(index * width, (index + 1) * width))
            return sum(paid.values()) + used_reflection + reserved_reads * evaluate_quote + reserved_proposals <= ceiling

        sampling = None
        requote = native_reserve == 'available-slots'
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
                nonlocal sampling
                config.stop_callbacks = [*config.stop_callbacks, exhausted]
                if native_reserve is not None:
                    from gepa.strategies.proposal_sampling import SingleMutationSampling

                    if config.reflection.skip_perfect_score:
                        raise ValueError('Prefix pruning requires one proposal per sampled native task')
                    base = config.engine.sampling_strategy or SingleMutationSampling()
                    sampling = FiniteProposalSampling(base, lambda p: len(opened) - supplied + len(queues[p]),
                                                      can_fund_tasks if requote else None)
                    config.engine.sampling_strategy = sampling
                    config.stop_callbacks.append(lambda _: sampling.denied)
                return optimize(*args, config=config, **kwargs)

            availability, bank = patch.object(module, 'optimize_anything', stopped), observed_opening()
        else:
            availability, bank = nullcontext(), opened
        parent_selection = (native_available_parents(lambda parent: supplied < len(opened) or bool(queues[parent]))
                            if available_parents else nullcontext())
        with availability, parent_selection:
            options = dict(cap=READ_LIMIT, seed=seed, width=width)
            if requote:
                nominee = native.select(initial, bank, groups, evaluate, reflect, **options, reserve_round_reads=False)
            else:
                nominee = native_with_price_guard(native.select, can_fund_round, initial, bank, groups, evaluate,
                                                  reflect, **options)
        if sampling is not None:
            skipped = sampling.skipped
            if any(child is None for _, child in proposals):
                raise ValueError('Native finite sampling dispatched an empty proposal slot')
    else:
        def settle(index, parent, child):
            return 0 if index < len(opened) or child == parent else proposal_quote

        budget = SequentialSearchBudget(ceiling, evaluate_quote, quote, settle,
                                        proposal_limit=0 if mode == 'cpo-supplied-only' else None)

        def exhausted(index, pool):
            return index >= len(opened) and not tracked_children(pool)

        def eligible(index, parent):
            return index < len(opened) or bool(queues[parent])

        def unavailable(index, parent):
            nonlocal skipped
            is_empty = not eligible(index, parent)
            skipped += int(is_empty)
            return is_empty

        trace = [] if schedule_trace is None else schedule_trace
        nominee = select_field_rewrites(initial, opened, groups, evaluate, reflect, trace, cap=READ_LIMIT, seed=seed,
                                        reinvest_savings=True, price_budget=budget, parent_bounds=True,
                                        certify_boundary_ties=True, skip_perfect_reflections=True,
                                        observed_charge=lambda prompt, row, _: paid[prompt, row.id],
                                        proposals_exhausted=exhausted if stop_on_exhaustion else None,
                                        parent_eligible=eligible if available_parents else None,
                                        proposal_unavailable=unavailable if skip_empty_slots else None,
                                        frontier_bounds=frontier_bounds, prioritize_uncertain_cases=prioritize_uncertain_cases,
                                        settle_validation_on_price_limit=settle_validation_on_price_limit)

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
    result = {'nominee': nominee, 'selected': decision.prompt, 'passes': observed,
              'recordedEvaluationCostNanodollars': sum(paid.values()) + sum(admitted.values()),
              'hypotheticalProposalCostNanodollars': used_reflection,
              'searchReads': len(paid), 'admissionReads': len(admitted),
              'laterSlots': len(proposals), 'recordedChildren': sum(child is not None for _, child in proposals)}
    if skip_empty_slots or native_reserve is not None:
        result['skippedEmptySlots'] = skipped
    return result


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


def availability_plan(cases, *, skip_empty_slots=False, matched_native=False):
    plan = prepare(cases)
    protocol = 'cpo-recorded-arc-skip-empty-slots-v1' if skip_empty_slots else 'cpo-recorded-arc-parent-availability-v1'
    plan = {**plan, 'protocol': protocol,
            'availableParentArms': RESTRICTED, 'stopOnExhaustion': True,
            'parentEligibility': 'After supplied openings, give all policies the same remaining-child predicate. '
                                 'Tracked candidates remain eligible for final selection.'}
    if skip_empty_slots:
        plan['skipEmptyArm'] = SKIP_EMPTY
        plan['skipEmptyPolicy'] = 'Keep the seeded parent draw. Charge no training read or proposal for an empty slot.'
    if matched_native:
        plan['protocol'] = 'cpo-recorded-arc-native-empty-slots-v1'
        plan['nativeReserves'] = NATIVE_RESERVES
        plan['nativeEmptyPolicy'] = (
            'Draw the native parent and all minibatches, then keep only tasks backed by supplied openings or children '
            'of that parent. Full-round keeps the published GEPA reserves. Available-slots reserves after sampling '
            'for uncached parent reads, a full child evaluation for each retained task, and remaining proposal quotes.'
        )
    return plan


def measure_availability(cases, scores, children, *, skip_empty_slots=False, matched_native=False):
    if version('gepa') != '0.1.4':
        raise ValueError('Use pinned native GEPA 0.1.4')
    quote = max(charge for rows in scores.values() for _, charge in rows.values())
    variants = {mode: mode + '-available' for mode in RESTRICTED}
    comparisons = {variant: [mode] for mode, variant in variants.items()}
    comparisons[variants['cpo-shared-budget']].extend(variants[mode] for mode in RESTRICTED[:2])
    arms = (*MODES, *variants.values())
    if skip_empty_slots:
        arms = (*arms, SKIP_EMPTY)
        comparisons[SKIP_EMPTY] = (*RESTRICTED, *variants.values())
    native_arms = {}
    if matched_native:
        native_arms = {f'{mode}-{reserve}': (mode, reserve)
                       for mode in RESTRICTED[:2] for reserve in NATIVE_RESERVES}
        arms = (*arms, *native_arms)
        comparisons.update({name: (mode,) for name, (mode, _) in native_arms.items()})
        comparisons[SKIP_EMPTY] = (*comparisons[SKIP_EMPTY], *native_arms)
    starts = tuple(parent for parent, child in children.items() if child)
    results = {}
    for units in QUOTE_UNITS:
        results[units] = {}
        for multiplier in REFLECTION_QUOTES:
            control, previous, combined = [], [], []
            for seed in SEEDS:
                cohorts = split(cases, seed)
                for start in starts:
                    rng = Random(f'{seed}/{start}')
                    orders = {parent: rng.sample(child, len(child)) for parent, child in children.items()}
                    args = start, cohorts, scores, orders, seed, quote, quote * multiplier, units * quote
                    original = {mode: play(mode, *args, stop_on_exhaustion=True) for mode in MODES}
                    variants_at_start = {arm: play(mode, *args, stop_on_exhaustion=True, available_parents=True)
                                         for mode, arm in variants.items()}
                    if skip_empty_slots:
                        variants_at_start[SKIP_EMPTY] = play('cpo-shared-budget', *args, stop_on_exhaustion=True,
                                                            skip_empty_slots=True)
                    control.append((seed, start, original))
                    outcomes = {**original, **variants_at_start}
                    if matched_native:
                        previous.append((seed, start, outcomes))
                        outcomes = {**outcomes, **{name: play(mode, *args, stop_on_exhaustion=True, native_reserve=reserve)
                                                  for name, (mode, reserve) in native_arms.items()}}
                    combined.append((seed, start, outcomes))
            results[units][multiplier] = {
                'controlTraceSha256': digest(control),
                **summarize(combined, arms=arms, comparisons=comparisons),
            }
            if skip_empty_slots:
                old_and_new = [(outcomes['cpo-shared-budget'], outcomes[SKIP_EMPTY]) for _, _, outcomes in combined]
                changes = {field: sum(old[field] != new[field] for old, new in old_and_new)
                           for field in ('nominee', 'selected', 'recordedChildren')}
                results[units][multiplier]['skipEmptyChangedPaths'] = changes
            if matched_native:
                results[units][multiplier]['previousTraceSha256'] = digest(previous)
    return {'evaluationQuoteNanodollars': quote, 'points': results, 'newProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    policies = parser.add_mutually_exclusive_group()
    policies.add_argument('--available-parents', action='store_true')
    policies.add_argument('--skip-empty-slots', action='store_true')
    policies.add_argument('--match-native-empty-slots', action='store_true')
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    cases, scores, children = load_archive()
    skip_empty_slots = args.skip_empty_slots or args.match_native_empty_slots
    compare_availability = args.available_parents or skip_empty_slots
    plan = (availability_plan(cases, skip_empty_slots=skip_empty_slots, matched_native=args.match_native_empty_slots)
            if compare_availability else prepare(cases))
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Use the current seal and a fresh output path')
    result = (measure_availability(cases, scores, children, skip_empty_slots=skip_empty_slots,
                                   matched_native=args.match_native_empty_slots)
              if compare_availability else measure(cases, scores, children))
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'comparison': result}, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
