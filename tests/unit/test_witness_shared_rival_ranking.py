from benchmarks import witness_shared_rival_ranking as rank


def test_ranking_uses_only_paid_enrolled_backups_and_preserves_reference_ties():
    grades = {('old', 1): False, ('first', 1): True, ('first', 2): True,
              ('backup', 1): True, ('other', 1): True, ('outside', 1): True}
    pool, result = rank.choices('old', 'first', ('first', 'other', 'backup', 'unpaid'), grades, 'backup')

    assert pool == ('other', 'backup')
    assert result == dict.fromkeys((rank.RATE, rank.PAIRED, rank.ADJUSTED), 'backup')


def test_paired_margin_can_choose_a_paid_rival_with_a_matched_gain():
    grades = {('old', 1): False, ('first', 1): True, ('reference', 2): True, ('rival', 1): True}
    _, result = rank.choices('old', 'first', ('first', 'reference', 'rival'), grades, 'reference')

    assert result[rank.PAIRED] == 'rival'
    assert result[rank.RATE] == 'reference'


def test_ceiling_leaves_room_for_the_future_fixed_reservation():
    events = [(7, False, [(3, 12), (2, 7)]), (8, True, [(1, 0)]), (7, False, [(2, 6)])]

    assert rank.ceiling(events, 10) == (13, 5)


def test_ceiling_skips_unfundable_retry_and_breaks_gain_ties_by_lower_cost():
    events = [(10, False, [(1, 100)]), (7, False, [(3, 5), (2, 5)])]

    assert rank.ceiling(events, 7) == (5, 2)
