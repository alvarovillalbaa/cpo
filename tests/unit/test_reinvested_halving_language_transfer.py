"""T2 budget checks for the transfer's binding-cap diagnostics."""

from benchmarks.continuous_search_controls import HALVING, settings
from benchmarks.reinvested_halving_language_transfer import full_round_quote


def test_full_round_quote_matches_simple_controls_at_every_panel_width():
    for rows in (3, 6, 8):
        for roster in (4, 8):
            caps = [cap for _, mode, width, cap in settings(rows) if mode == HALVING and width == roster]
            assert full_round_quote(roster, rows) == max(caps)


def test_original_cap_leaves_room_for_narrow_eager_but_limits_wide_eager():
    assert full_round_quote(4, 6) == 16
    assert full_round_quote(8, 6) == 24
