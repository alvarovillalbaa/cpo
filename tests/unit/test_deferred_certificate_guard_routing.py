import pytest

from benchmarks import deferred_certificate_guard_routing as routing


@pytest.mark.parametrize(('challenger', 'expected', 'after_regression', 'unless_proved'), [
    (True, 'preserved', False, False),
    (False, 'observed-regression', True, True),
    (None, 'unverified-preservation', False, True),
])
def test_route_distinguishes_failed_and_unread_incumbent_passes(
    challenger, expected, after_regression, unless_proved,
):
    grades = {('start', 'pass'): True, ('start', 'miss'): False,
              ('next', 'miss'): True, ('unrelated', 'pass'): False}
    if challenger is not None:
        grades['next', 'pass'] = challenger
    status = routing.validation_status('start', 'next', grades)
    assert status == expected
    assert routing.guard_needed(routing.OBSERVED, status) is after_regression
    assert routing.guard_needed(routing.UNVERIFIED, status) is unless_proved


def test_observed_regression_takes_precedence_over_an_unread_pass():
    grades = {('start', 'unread'): True, ('start', 'failed'): True, ('next', 'failed'): False}
    assert routing.validation_status('start', 'next', grades) == 'observed-regression'
