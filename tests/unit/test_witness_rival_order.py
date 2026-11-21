import pytest

from benchmarks.witness_rival_order import certificate_minima


def test_side_interleaving_still_pays_for_unfavorable_prefix_reads():
    matrix = {'old': (True, False, False), 'new': (False, True, True)}

    def grade(prompt, case):
        return matrix[prompt][case]

    assert certificate_minima('old', 'new', [0, 1, 2], [], grade, 1, False) == (6, 4)


def test_tie_extension_requires_reading_both_complete_base_sides():
    matrix = {'old': (True, False, True, False), 'new': (False, True, True, True)}

    def grade(prompt, case):
        assert case in (2, 3)
        return matrix[prompt][case]

    assert certificate_minima('old', 'new', [0, 1], [2, 3], grade, 1, True) == (8, 7)


def test_rejected_panel_has_no_promotion_certificate():
    with pytest.raises(ValueError, match='favorable grades'):
        certificate_minima('old', 'new', [0, 1], [], lambda _prompt, _case: True, 1, False)
