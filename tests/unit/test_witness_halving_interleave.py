from collections import Counter
from types import SimpleNamespace

from benchmarks import witness_halving_interleave as replay


def layout(first, second, cases):
    return {'alternatives': [first, second], 'validation': cases}


def test_shared_cap_never_reopens_when_the_interleaved_policy_changes_cycles():
    observations = []

    def evaluate(prompt, case):
        observations.append((prompt, case))
        return prompt == 'start'

    layouts = [layout('a', 'b', [0, 1, 2]), layout('c', 'd', [3, 4, 5])]
    counts = Counter()
    result = replay.fallback('start', layouts, {}, evaluate, 2, counts)

    assert result.original is None
    assert result.paid_search == len(set(observations)) == len(observations) == 2
    assert counts['cycleSteps'] == 2
    assert counts['cycleSwitches'] == 1


def test_cache_settles_a_challenger_at_zero_budget():
    layouts = [layout('a', 'b', [0, 1, 2]), layout('c', 'd', [3, 4, 5])]
    paid = {(prompt, case): prompt == 'c' for prompt in ('start', 'c', 'd') for case in range(3, 6)}

    def evaluate(prompt, case):
        raise AssertionError(f'Unexpected lookup for {prompt} on {case}')

    result = replay.fallback('start', layouts, paid, evaluate, 0, Counter())

    assert result.original == 'c'
    assert result.paid_search == len(paid)


def test_direct_cycle_menu_keeps_one_proof_per_choice_and_the_retention_option():
    layouts = [layout('a', 'b', [0, 1, 2]), layout('c', 'd', [3, 4, 5])]
    scores = {'start': 4, 'a': 8, 'c': 10}

    def evaluate(prompt, _case):
        return prompt in ('a', 'c')

    proof_calls = []

    def prove(nomination):
        prompt = nomination.original
        proof_calls.append(prompt)
        return SimpleNamespace(prompt=prompt, lookups=3 if prompt == 'a' else 8)

    menu = replay.direct_cycle_menu('start', layouts, {}, evaluate, 8, prove, scores.__getitem__)

    assert proof_calls == ['a', 'c']
    assert sorted(menu.values()) == [4, 6]
    assert replay.allocation.hindsight([menu], 50)['addedHoldoutPasses'] == 6
    assert replay.allocation.hindsight([menu], 0)['addedHoldoutPasses'] == 0
