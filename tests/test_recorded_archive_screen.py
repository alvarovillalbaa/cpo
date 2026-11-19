from benchmarks.recorded_archive_screen import screen
from cpo import Observation, Row


def test_screen_preserves_critical_passes_and_matches_full_validation_with_fewer_calls():
    panel = (Row('routine', 'task'), Row('critical', 'task', True), Row('extra', 'task'))
    observations = {('base', row.id): Observation(row.critical, {}) for row in panel}
    outcomes = {'risky': {'critical': False, 'routine': True, 'extra': True},
                'safe': {'critical': True, 'routine': True, 'extra': False}}

    def evaluate(prompt, row):
        return Observation(outcomes[prompt][row.id], {})

    def run(certified):
        return screen('base', ['risky', 'safe'], observations, panel, evaluate,
                      metric_limit=6, candidate_limit=2, certified=certified)

    full, full_calls, _ = run(False)
    stopped, actual_calls, attempts = run(True)
    assert full == stopped == 'safe'
    assert full_calls == 6 and actual_calls == 3
    assert [attempt['status'] for attempt in attempts] == ['critical_regression', 'promote']


def test_screen_stops_before_spending_when_no_gain_can_be_certified_in_budget():
    rows = (Row('a', 'task', True), Row('b', 'task'))
    observations = {('base', row.id): Observation(row.critical, {}) for row in rows}

    def evaluate(*_):
        raise AssertionError('Unaffordable candidate reached the evaluator')

    assert screen('base', ['next'], observations, rows, evaluate, metric_limit=1,
                  candidate_limit=1, certified=True) == ('base', 0, [])
