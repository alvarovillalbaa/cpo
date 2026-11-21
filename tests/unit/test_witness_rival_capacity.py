import pytest

from benchmarks import witness_proof_split
from benchmarks.witness_admission_retry import Decision
from benchmarks.witness_paid_nominee_ranking import Nomination
from benchmarks.witness_rival_capacity import LIMITS, Rival, assess, summarize_rivals


@pytest.mark.parametrize(('rivals', 'unseen', 'label'), [
    ([], False, 'no-improving-enrolled-rival'),
    ([Rival('1', -1, 'promoted', 4)], True, 'improving-rivals-unread'),
    ([Rival('1', 5, 'rejected', 2)], True, 'paid-improvement-fails-proof'),
    ([Rival('1', 5, 'promoted', 8)], True, 'paid-improvement-exceeds-cap'),
    ([Rival('1', 1, 'promoted', 5)], True, 'paid-improvement-fits'),
])
def test_classifies_each_reason_before_ranking(rivals, unseen, label):
    cause, _ = summarize_rivals(rivals, unseen, spent=3, remaining=7)

    assert cause == label


def test_two_hindsight_limits_enforce_distinct_costs_and_complete_certificates():
    cheap = Rival('1', 2, 'promoted', 3)
    costly = Rival('2', 3, 'promoted', 5)
    rivals = [cheap, costly, Rival('3', 40, 'rejected', 1), Rival('4', 50, 'promoted', 6)]

    cause, best = summarize_rivals(rivals, unseen_gain=True, spent=3, remaining=5)

    assert cause == 'paid-improvement-fits'
    assert best == dict(zip(LIMITS, (cheap, costly), strict=True))


def test_replay_caps_the_published_rival_and_never_qualifies_an_unpaid_rival(monkeypatch):
    monkeypatch.setattr(witness_proof_split, 'CAP', 6)
    matrix = ('001000', '000000', '001110', '001111')
    layouts = [
        {'qualify': [0, 1], 'alternatives': ['1']},
        {'qualify': [2, 3], 'alternatives': ['2', '3']},
    ]
    plan = {'minimumQualificationGain': 1, 'maximumExtensionRows': 0}
    nomination = Nomination('1', 2, {('1', 5): True, ('2', 5): False})
    observed = Decision('0', 6, 'undecided', retry=True, retry_lookups=3)

    cause, best, first_spend, _, options = assess(matrix, [4], '0', layouts, plan, nomination, observed)

    assert cause == 'paid-improvement-exceeds-cap'
    assert first_spend == 3
    assert options == [Rival('2', 1, 'promoted', 4)]
    assert all(option.gain == option.lookups == 0 for option in best.values())
