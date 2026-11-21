"""Verify admission attempts and the realized-budget comparator."""

from benchmarks import prompteval_witness_budget_controls as replay


def test_an_unsuccessful_nomination_consumes_an_attempt_and_ends_later_search(monkeypatch):
    incumbent = 'start'
    nominated = iter((incumbent, 'first challenger'))
    calls, attempts = [], []

    def choose(method, *_):
        calls.append(method)
        return next(nominated)

    monkeypatch.setattr(replay.transfer, 'select', choose)
    selections = [replay.route('admission-attempts/1', incumbent, {}, None, {}, attempts) for _ in range(4)]
    assert selections == [incumbent, 'first challenger', incumbent, incumbent]
    assert calls == [replay.BASELINE, replay.BASELINE]
    assert attempts == ['first challenger']


def test_best_affordable_setting_ranks_equal_subject_accuracy_then_realized_cost():
    totals = {'expensive': {'paidLookups': 17}, 'bulk-winner': {'paidLookups': 12}, 'best': {'paidLookups': 9},
              'tied': {'paidLookups': 11}}
    accuracy = {'expensive': '4/5', 'bulk-winner': '2/5', 'best': '1/2', 'tied': '1/2'}
    assert replay.affordable(totals, totals, accuracy, 12) == 'best'
