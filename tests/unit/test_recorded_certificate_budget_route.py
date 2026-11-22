import pytest

from benchmarks import recorded_certificate_budget_route as route
from cpo import Observation, Row


@pytest.mark.parametrize(('incumbent_passes', 'chosen'), [(2, True), (3, False)])
def test_cap_thirteen_routes_on_paid_grades_and_reuses_them(incumbent_passes, chosen):
    rows = tuple(Row(str(i), 'task') for i in range(6))
    selector = route.sequential._screen if chosen else route.BATCH_SCREEN
    roster = ('first', 'second', 'third')

    def replay(screen):
        called = {}

        def evaluate(prompt, row):
            key = prompt, row.id
            assert key not in called
            called[key] = Observation(prompt != 'start' or int(row.id) < incumbent_passes, {})
            return called[key]

        result = screen('start', roster, rows, evaluate, 13)
        return result, tuple(called.items())

    seen = []
    assert replay(lambda *args: route.route_screen(*args, seen)) == replay(selector)
    assert seen == [chosen]
