from collections import Counter
from random import Random

from benchmarks import prompteval_first_proof_budget as reference, witness_split_finalists as split


def fixture():
    layout = {'validation': [1, 2, 3, 4], 'seed': 8, 'alternatives': ['first', 'same', 'different']}
    ordered = layout['validation'].copy()
    Random(layout['seed']).shuffle(ordered)
    return layout, ordered


def test_cached_second_miss_uses_a_distinct_finalist_and_neutral_tie_case():
    layout, (miss, keep, extra_miss, tie) = fixture()
    grades = {('start', miss): False, ('start', keep): True, ('first', miss): True, ('first', keep): True,
              ('same', extra_miss): False, ('different', extra_miss): True, ('different', keep): True,
              ('first', tie): False, ('different', tie): True}
    read = []

    def observe(prompt, case):
        read.append((prompt, case))
        return grades[prompt, case]

    activity = Counter()
    selected = split.select('start', layout, observe, {'evaluationLookupLimit': 9}, {extra_miss: False}, activity)

    assert selected == 'different'
    assert ('start', extra_miss) not in read
    assert read[-2:] == [('first', tie), ('different', tie)]
    assert len(read) == 9
    assert activity['priorOnlyAlternate'] == activity['alternateNominees'] == 1


def test_fallback_to_original_screen_has_identical_reads_without_a_second_miss():
    layout, (miss, keep, tie, _) = fixture()
    grades = {('start', miss): False, ('start', keep): True, ('first', miss): True, ('first', keep): True,
              ('same', miss): True, ('same', keep): True, ('first', tie): False, ('same', tie): True}
    def run(selector):
        reads = []

        def observe(prompt, case):
            reads.append((prompt, case))
            return grades[prompt, case]

        return selector('start', layout, observe, {'evaluationLookupLimit': 8}), reads

    assert run(lambda *args: split.select(*args, {}, Counter())) == run(
        lambda *args: reference.witness_challenger(*args, rotate=True, finalists=2))


def test_cap_preserves_the_first_finalist_after_discovering_two_misses():
    layout, (miss, extra_miss, keep, _) = fixture()
    scores = {('start', miss): False, ('start', extra_miss): False, ('start', keep): True,
              ('first', miss): True, ('first', keep): True}
    activity = Counter()
    result = split.select('start', layout, lambda prompt, case: scores.pop((prompt, case)),
                          {'evaluationLookupLimit': 5}, {}, activity)

    assert result == 'first'
    assert not scores
    assert activity['alternateAvailable'] == 1
    assert activity['alternateProbes'] == 0
