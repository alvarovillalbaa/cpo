from collections import Counter
from random import Random

from benchmarks import witness_matched_anchors as replay


def test_race_can_select_a_stronger_candidate_that_misses_the_first_witness():
    layout = {'validation': [1, 2, 3, 4, 5], 'seed': 8, 'alternatives': ['first', 'stronger']}
    ordered = layout['validation'].copy()
    Random(layout['seed']).shuffle(ordered)
    anchors = ordered[:4]
    grades = {prompt: dict(zip(anchors, values, strict=True)) for prompt, values in {
        'start': (False, False, True, False), 'first': (True, False, True, False),
        'stronger': (False, True, True, True),
    }.items()}

    def grade(prompt, case):
        return grades[prompt][case]

    assert replay.select('start', layout, grade, {'evaluationLookupLimit': 12}, replay.FIRST, Counter()) == 'first'
    assert replay.select('start', layout, grade, {'evaluationLookupLimit': 12}, replay.BEST, Counter()) == 'stronger'


def test_perfect_incumbent_costs_only_four_reads_in_both_arms():
    layout = {'validation': [1, 2, 3, 4], 'seed': 8, 'alternatives': ['first']}
    for method in (replay.FIRST, replay.BEST):
        reads = []

        def grade(prompt, case):
            reads.append((prompt, case))
            return True

        activity = Counter()
        assert replay.select('start', layout, grade, {'evaluationLookupLimit': 8}, method, activity) == 'start'
        assert len(reads) == activity['anchorLookups'] == 4
        assert all(prompt == 'start' for prompt, _ in reads)


def test_race_never_reads_past_the_search_cap():
    layout = {'validation': [1, 2, 3, 4], 'seed': 8, 'alternatives': ['first', 'second']}
    for cap in range(13):
        for method in (replay.FIRST, replay.BEST):
            charged = Counter()
            replay.select('start', layout, lambda prompt, _: prompt != 'start',
                          {'evaluationLookupLimit': cap}, method, charged)
            assert charged['anchorLookups'] <= cap
