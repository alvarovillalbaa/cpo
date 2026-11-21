from benchmarks import witness_no_nominee_admission as rescue


def test_paid_routes_distinguish_unpaired_rates_from_matched_validation_wins():
    grades = {
        ('start', 1): False, ('start', 2): False, ('start', 3): True,
        ('paired', 1): True, ('paired', 2): True, ('paired', 3): False,
        ('unpaired', 4): True, ('unpaired', 5): True, ('unpaired', 6): True,
    }

    choices, observed = rescue.choose('start', ('unread', 'paired', 'unpaired'), grades)

    assert observed == ('paired', 'unpaired')
    assert choices == {rescue.ANY: 'unpaired', rescue.RATE: 'unpaired', rescue.PAIR: 'paired', rescue.TWO: None}


def test_high_rate_with_one_reply_fails_the_supported_rate_gate():
    choices, _ = rescue.choose('start', ('rival',), {('rival', 4): True})

    assert choices[rescue.ANY] == 'rival'
    assert choices[rescue.RATE] is None


def test_hindsight_spends_only_its_credit_and_uses_one_proof_per_episode():
    menus = [{2: 3, 4: 7}, {3: 6}]

    assert rescue.hindsight(menus, 6) == {'paidLookups': 5, 'addedHoldoutPasses': 9}
    assert rescue.hindsight(menus, 0) == {'paidLookups': 0, 'addedHoldoutPasses': 0}
