"""Bind a paired replay to GEPA's seeded Pareto selector and minibatches."""

from importlib import import_module
from importlib.metadata import version
from random import Random
from types import SimpleNamespace
from unittest.mock import patch


def select_field_rewrites(
    initial, bank, groups, evaluate, reflect, trace, *,
    cap, seed, observed_charge=None, reinvest_savings=False, price_budget=None, parent_bounds=False,
    certify_boundary_ties=False,
):
    from benchmarks import grounded
    from cpo import Row
    from cpo.sequential_field_rewrite import select_sequential_field_rewrites

    training, validation = (tuple(Row(row['id'], 'archive', fields=len(row['expected'])) for row in groups[key])
                            for key in ('train', 'validation'))
    training_ids = {row.id for row in training}

    def propose(index, parent, samples):
        if any(row.id not in training_ids or reply.feedback['id'] != row.id for row, reply in samples):
            raise ValueError('A proposer received a case outside its paid training minibatch')
        return bank[index] if index < len(bank) else reflect(parent, [reply.feedback for _, reply in samples])

    schedule = sequential_schedule(validation, seed, grounded.MINIBATCH, trace, training=training,
                                   parent_bounds=parent_bounds)
    return select_sequential_field_rewrites(
        initial, training, validation, lambda p, row: evaluate(p, row.id), schedule, propose,
        rounds=grounded.REFLECTION_LIMIT, minibatch_size=grounded.MINIBATCH, metric_limit=cap,
        observed_charge=observed_charge, reinvest_savings=reinvest_savings, price_budget=price_budget,
        certify_boundary_ties=certify_boundary_ties,
    )


def sequential_schedule(
    validation, seed, minibatch_size, trace, *, training=None, parent_bounds=False, width=1, frontier_bounds=False,
):
    from gepa.core.data_loader import ListDataLoader
    from gepa.gepa_utils import select_program_candidate_from_pareto_front
    from gepa.strategies.batch_sampler import EpochShuffledBatchSampler

    if parent_bounds:
        from cpo.gepa_parent import select_two_candidate_parent
    if frontier_bounds:
        from cpo.gepa_frontier import select_frontier_parent
    if (parent_bounds or frontier_bounds) and version('gepa') != '0.1.4':
        raise ValueError('Parent bounds require GEPA 0.1.4')

    training = validation if training is None else training
    rng = Random(seed)
    loader = ListDataLoader(training)
    sampler = EpochShuffledBatchSampler(minibatch_size, rng=rng)

    def schedule(index, pool, grades):
        parent = select_two_candidate_parent(pool, len(validation), grades, rng) if parent_bounds else None
        if parent is None and frontier_bounds:
            parent = select_frontier_parent(pool, len(validation), grades, rng)
        if len(pool) == 1:
            # The only program owns every case without needing its grades.
            parent = rng.choice(pool * len(validation))
        elif parent is None:
            profiles = [grades(prompt) for prompt in pool]
            fronts = {}
            for case, scores in enumerate(zip(*profiles, strict=True)):
                best = max(scores)
                fronts[case] = {owner for owner, score in enumerate(scores) if score == best}
            averages = [sum(profile) / len(validation) for profile in profiles]
            parent = pool[select_program_candidate_from_pareto_front(fronts, averages, rng)]
        batches = []
        for _ in range(width):
            ids = sampler.next_minibatch_ids(loader, SimpleNamespace(i=index))
            batch = tuple(training[case].id for case in ids)
            batches.append(batch)
            trace.append((pool, parent, batch))
        return parent, batches[0] if width == 1 else tuple(batches)

    return schedule


def traced_native_schedule(select, incumbent, bank, groups, evaluate, trace, **options):
    from gepa.strategies.batch_sampler import EpochShuffledBatchSampler
    from gepa.strategies.candidate_selector import ParetoCandidateSelector

    select_parent = ParetoCandidateSelector.select_candidate_idx
    sample_batch = EpochShuffledBatchSampler.next_minibatch_ids
    pool, parent_prompt = (), None

    def parent(selector, state):
        nonlocal pool, parent_prompt
        position = select_parent(selector, state)
        pool = tuple(next(iter(candidate.values())) for candidate in state.program_candidates)
        parent_prompt, = state.program_candidates[position].values()
        return position

    def batch(sampler, loader, state):
        ids = sample_batch(sampler, loader, state)
        trace.append((pool, parent_prompt, tuple(row['id'] for row in loader.fetch(ids))))
        return ids

    with (patch.object(ParetoCandidateSelector, 'select_candidate_idx', parent),
          patch.object(EpochShuffledBatchSampler, 'next_minibatch_ids', batch)):
        return select(incumbent, bank, groups, evaluate, **options)


def native_with_price_guard(select, can_fund_round, *args, **kwargs):
    module = import_module('gepa.optimize_anything')
    optimize = module.optimize_anything

    def guarded(*arguments, config, **options):
        config.stop_callbacks = [*config.stop_callbacks, lambda state: not can_fund_round(state.i + 1)]
        return optimize(*arguments, config=config, **options)

    with patch.object(module, 'optimize_anything', guarded):
        return select(*args, **kwargs)
