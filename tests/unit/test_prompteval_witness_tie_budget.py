"""Exercise the paired-read boundary and tie stopping rule with known scores."""

from collections import Counter
from random import Random

from benchmarks.prompteval_witness_tie_budget import choose


def scenario(*, tied=True, cap=20, two_finalists=True, always=False):
    validation = list(range(6))
    order = validation.copy()
    Random(90).shuffle(order)
    rows = {
        'incumbent': (True, False, False, False, False, False),
        'early': (True, True, True, False, False, False),
        'late': (True, True if two_finalists else False, tied, True, True, True),
    }
    result = {(prompt, case): passed for prompt, scores in rows.items() for case, passed in zip(order, scores)}
    reads = []
    activity = Counter()

    def observe(prompt, case):
        reads.append((prompt, case))
        return result[prompt, case]

    nominee = choose('incumbent', {'validation': validation, 'seed': 90, 'alternatives': ['early', 'late']}, observe,
                     {'evaluationLookupLimit': cap}, always=always, counts=activity)
    return nominee, reads, activity, order


def test_pays_for_one_additional_pair_to_resolve_a_tie():
    nominee, reads, activity, order = scenario()
    assert nominee == 'late'
    assert len(reads) == 10
    assert reads[-2:] == [('early', order[3]), ('late', order[3])]
    assert activity == {'twoFinalistCycles': 1, 'firstCaseTies': 1, 'extraValidationReads': 2,
                        'differentNominations': 1}


def test_pays_for_resolved_comparison_only_in_always_extend_control():
    nominee, reads, activity, _ = scenario(tied=False)
    assert nominee == 'early'
    assert len(reads) == 8
    assert activity['extraValidationReads'] == 0

    nominee, reads, activity, _ = scenario(tied=False, always=True)
    assert nominee == 'late'
    assert len(reads) == 14
    assert activity['extraValidationReads'] == 6


def test_has_to_fund_an_entire_pair():
    nominee, reads, activity, _ = scenario(cap=9)
    assert nominee == 'early'
    assert len(reads) == 8
    assert activity['extraValidationReads'] == 0


def test_leaves_the_original_choice_with_one_finalist():
    nominee, reads, activity, _ = scenario(two_finalists=False)
    assert nominee == 'early'
    assert len(reads) == 5
    assert not activity
