"""T2 checks for tracing the first barrier to the simple control's deployment."""

from benchmarks.reinvested_halving_gap_attribution import channel


def test_attribution_identifies_pruning_separately_from_final_rank_and_admission():
    roster = ('a', 'b', 'c', 'd')
    survivors = [('a', 'b'), ('a', 'b'), ('a', 'b'), ('a', 'b'), ('a', 'b'), ('a',)]
    assert channel('base', roster, 'e', 'base', survivors) == 'outside-cpo-roster'
    assert channel('base', roster, 'c', 'base', survivors) == 'dropped-at-row-1'
    assert channel('base', roster, 'b', 'base', survivors) == 'lost-final-rank'
    assert channel('base', roster, 'a', 'base', survivors) == 'no-validation-gain'
    assert channel('base', roster, 'base', 'a', survivors) == 'simple-retained'
    assert channel('base', roster, 'a', 'a', survivors) == 'same-deployment'
