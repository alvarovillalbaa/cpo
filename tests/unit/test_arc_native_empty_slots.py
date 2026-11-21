from types import SimpleNamespace

from gepa.strategies.proposal_sampling import SameParentSampling
import pytest

from benchmarks.recorded_arc_lineage_quotes import FiniteProposalSampling


@pytest.mark.parametrize(
    ('capacity', 'affordable', 'expected'),
    ((0, False, []), (1, True, ['first']), (1, False, []), (2, True, ['first', 'second'])),
)
def test_native_sampler_draws_both_minibatches_before_applying_slot_and_budget_limits(capacity, affordable, expected):
    state = SimpleNamespace(program_candidates=[{'prompt': 'parent'}])
    candidate_selector = SimpleNamespace(select_candidate_idx=lambda _: 0)
    trainset = SimpleNamespace(fetch=lambda ids: list(ids))
    minibatches = iter((['first'], ['second']))
    batch_sampler = SimpleNamespace(next_minibatch_ids=lambda *_: next(minibatches))
    reservations = []

    def admit(parent, tasks):
        assert parent == 'parent'
        reservations.append([task.minibatch_ids[0] for task in tasks])
        return affordable

    sampler = FiniteProposalSampling(SameParentSampling(2), lambda _: capacity, admit)
    sampled = sampler.sample_tasks(state, candidate_selector, batch_sampler, trainset)

    assert list(minibatches) == []
    assert [task.minibatch_ids[0] for task in sampled] == expected
    assert sampler.skipped == 2 - capacity
    assert sampler.denied == (capacity > 0 and not affordable)
    assert reservations == ([['first', 'second'][:capacity]] if capacity else [])
