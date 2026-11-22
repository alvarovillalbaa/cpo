from itertools import product

import pytest

from cpo import Observation, Row
from cpo.deferred_certificate_cycle import _screen, run_deferred_certificate_cycle
from cpo.prechecked_certificate_cycle import _screen as eager


@pytest.mark.parametrize('critical', [False, True])
def test_deferred_screen_matches_every_three_case_board_under_seven_caps(critical):
    rows = (Row('0', 'task'), Row('1', 'task', critical=critical), Row('2', 'task'))
    prompts = ('start', 'a', 'b', 'c')
    for grades in product((False, True), repeat=len(rows) * len(prompts)):
        board = dict(zip(product(prompts, (row.id for row in rows)), grades, strict=True))
        for cap in range(3, 10):
            def run(screen):
                paid = {}

                def evaluate(prompt, row):
                    key = prompt, row.id
                    assert key not in paid
                    paid[key] = board[key]
                    return Observation(paid[key], {})

                result, counts = screen(prompts[0], prompts[1:], rows, evaluate, cap)
                assert result.evaluations == len(paid) <= cap
                return (result.prompt, result.finalist, counts), paid

            before, eager_calls = run(eager)
            after, deferred_calls = run(_screen)
            assert after == before
            assert deferred_calls.items() <= eager_calls.items()


def test_unused_reserved_probe_never_reaches_the_evaluator_or_changes_qualification():
    rows = tuple(Row(str(index), 'validation') for index in range(3))
    proof = (Row('proof', 'qualification'),)
    paid = []

    def evaluate(prompt, row):
        assert prompt != 'second'
        paid.append((prompt, row.id))
        return Observation(prompt == 'first' or row.id == '2', {})

    result = run_deferred_certificate_cycle(
        'start', ('first', 'second'), rows, proof, evaluate, metric_limit=7,
        qualify=lambda prompt, _, __: prompt == 'first',
    )
    assert result.prompt == 'first' and result.promoted
    assert result.search.evaluations == 5
    assert result.qualification_evaluations == 2
    assert paid == [('start', '0'), ('start', '1'), ('start', '2'), ('first', '0'), ('first', '1')]
