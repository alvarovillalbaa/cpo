"""The replay prefix must match an explicitly capped production path."""

from benchmarks import prompteval_matched_admission_attempt as replay


PLAN = {'evaluationLookupLimit': 8, 'qualificationPolicy': 'extend-ties', 'minimumQualificationGain': 1,
        'maximumExtensionRows': 2}
LAYOUTS = ({'seed': 17, 'validation': [0, 1], 'train': [], 'qualify': [2], 'alternatives': ['1']},
           {'seed': 11, 'validation': [0, 1], 'train': [], 'qualify': [3], 'alternatives': ['2']})


def test_first_rejected_admission_exhausts_the_shared_cap(monkeypatch):
    def nominate(_, incumbent, layout, observe, __):
        observe(incumbent, 0)
        candidate, = layout['alternatives']
        observe(candidate, 1)
        return candidate

    monkeypatch.setattr(replay.transfer, 'select', nominate)
    full, totals, _, capped, paid = replay.observed_path(('10000', '11000', '11011'), [4], '0', LAYOUTS,
                                                         PLAN, 'gepa-batched/80', 'retire-assigned', verify=True)
    assert (full, capped) == ('2', '0')
    assert paid == 4
    assert totals['paidLookups'] == 7


def test_without_a_nomination_all_paid_search_stays_in_the_prefix(monkeypatch):
    def retain(_, incumbent, layout, observe, __):
        observe(incumbent, layout['validation'][0])
        return incumbent

    monkeypatch.setattr(replay.transfer, 'select', retain)
    full, totals, _, capped, paid = replay.observed_path(('10000', '11000', '11011'), [4], '0', LAYOUTS,
                                                         PLAN, replay.CPO, 'retire-assigned', verify=True)
    assert full == capped == '0'
    assert paid == totals['paidLookups'] == 1
