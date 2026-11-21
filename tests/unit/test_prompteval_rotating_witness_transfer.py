"""T2 tests for the frozen replay's comparison gate on synthetic counts."""

from benchmarks.prompteval_rotating_witness_transfer import CANDIDATE, PRIMARY, compare, execution_plan


def panel(rows, gain, search_delta=-1):
    return {'holdoutRows': rows, 'episodeCount': 1, 'methods': {
        CANDIDATE: {'holdoutPasses': rows // 2 + gain, 'paidLookups': 10 + search_delta},
        PRIMARY: {'holdoutPasses': rows // 2, 'paidLookups': 10},
    }}


def test_macro_accuracy_prevents_the_largest_subject_from_winning_the_gate():
    panels = [('big', panel(100, 20)), ('small', panel(10, -3))]
    result = compare(panels, CANDIDATE, PRIMARY)
    assert result['pooledPassDelta'] == 17
    assert result['macroAccuracyDelta'] == '-1/20'
    assert result['qualifies'] is False


def test_gate_requires_positive_accuracy_after_each_subject_omission_and_no_extra_lookups():
    small_gain = panel(20, 1)
    panels = [('a', small_gain), ('b', small_gain), ('c', panel(20, -1))]
    assert compare(panels, CANDIDATE, PRIMARY)['qualifies'] is False

    panels[-1] = ('c', panel(20, -1, search_delta=3))
    panels[0] = ('a', panel(20, 3))
    panels[1] = ('b', panel(20, 2))
    assert compare(panels, CANDIDATE, PRIMARY)['qualifies'] is False

    panels[-1] = ('c', panel(20, -1))
    assert compare(panels, CANDIDATE, PRIMARY)['qualifies'] is True


def test_execution_seal_changes_when_the_captured_corpus_changes():
    old = execution_plan('design', 'corpus-a')
    changed = execution_plan('design', 'corpus-b')
    assert old['designSha256'] == changed['designSha256']
    assert old['executionSha256'] != changed['executionSha256']
