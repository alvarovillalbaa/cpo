"""T2 scripted labels exercising the signed backup ranking."""

from fractions import Fraction

from benchmarks.continuous_archive_backup import Opportunity
from benchmarks.continuous_backup_value import keys, rank, summarize
from cpo.paired_qualification import QualificationObservation


def test_missing_context_uses_parent_prediction():
    labels = {'all': (10, '1/2', 20)}
    context = ('all', 'paid', 'paid/1', 'paid/1/2/3')
    assert summarize(labels, context, 24) == Fraction(1, 40)


def test_signed_rank_declines_negative_gain_even_with_higher_proof_probability():
    counts = ((2, 4), (4, 4))
    probe = Opportunity('high-risk', 'v1', counts, 7, Fraction(9, 10))
    repair = Opportunity('paid-repair', None, counts, 6, Fraction(1, 3))
    prefix = (QualificationObservation('base', 'q0', 0, False),)
    labels = {'all': (200, '1/10', 600), 'paid': (100, '2', 300), 'probe': (100, '-19/10', 300)}
    assert keys(repair, prefix)[:3] == ('all', 'paid', 'paid/1')
    candidate, = rank((probe, repair), prefix, labels, 24)
    assert candidate.candidate == 'paid-repair'
    assert 0 < candidate.priority < Fraction(1, 3)
