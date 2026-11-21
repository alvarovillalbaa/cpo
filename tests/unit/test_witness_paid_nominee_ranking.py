from unittest.mock import patch

from benchmarks import witness_paid_nominee_ranking as study


def test_rank_excludes_unread_prompts_and_preserves_ties():
    incumbent = '0'
    paid = {('0', 0): False, ('1', 0): True, ('2', 0): True}
    original = study.Nomination('2', 3, paid)
    assert study.rank(original, incumbent, ('1', '2', '3')) == dict.fromkeys(study.RULES, '2')
    assert study.rank(study.Nomination(None, 0, {}), incumbent, ('1', '2')) == dict.fromkeys(study.RULES)


def test_rank_can_use_a_challenger_without_a_paid_paired_win():
    paid = {('0', 0): False, ('1', 0): True, ('1', 1): False, ('2', 2): True, ('2', 3): True}
    choices = study.rank(study.Nomination('1', 5, paid), '0', ('1', '2', 'unread'))
    assert choices['smoothed-pass-rate'] == '2'
    assert choices['paired-margin'] == '1'
    assert choices['case-adjusted'] == '2'


def test_cross_fit_uses_only_admission_and_respects_paid_cap():
    stats = {rule: {'proofLookups': 10, 'promotions': 1} for rule in study.RULES}
    stats['smoothed-pass-rate'].update(proofLookups=11, promotions=4)
    stats['paired-margin'].update(proofLookups=9, promotions=2)
    assert study.fit(stats) == 'paired-margin'


def test_search_stops_before_the_first_admission_reply():
    original = study.gap.paired.replay.original

    def witness(_incumbent, _layout, observe, _limits):
        observe('1', 7)
        return '1'

    def play(_matrix, _held, _start, _layouts, _active, _policy, select):
        nominee = select('0', {}, lambda _p, _c: True, {})
        study.REPLAY.qualify('0', nominee)
        raise AssertionError('Search crossed its nomination boundary')

    def forbidden(*_args, **_kwargs):
        raise AssertionError('Admission was read before ranking')

    with (patch.object(original, 'play', play), patch.object(original, 'witness', witness),
          patch.object(study.REPLAY, 'qualify', forbidden)):
        result = study.search_to_nomination([], set(), '0', [], {}, 'retire-assigned', 16)
    assert result == study.Nomination('1', 1, {('1', 7): True})
