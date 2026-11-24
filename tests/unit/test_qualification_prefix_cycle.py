from functools import partial

import pytest

from cpo import Observation, Row
from cpo.qualification_prefix_cycle import run_qualification_prefix_cycle
from cpo.quoted_shared_validation_cycle import _screen


@pytest.mark.parametrize('first_miss', range(5))
def test_routes_only_after_the_paid_qualification_prefix(first_miss):
    qualification = tuple(Row(f'q{i}', 'qualification') for i in range(4))
    validation = (Row('v', 'validation'),)
    reads = []
    selected = []

    def qualify(prompt, row, repeat):
        reads.append((prompt, row))
        return prompt == 'challenger' or row.id != f'q{first_miss}'

    def screen(index, incumbent, roster, rows, observe, cap):
        selected.append(index)
        assert rows == validation
        assert reads == [('base', row) for row in qualification[:index + 1]]
        return _screen(incumbent, roster, rows, observe, cap, halve=False)

    result = run_qualification_prefix_cycle(
        'base', ('challenger',), validation, qualification,
        lambda prompt, row: Observation(prompt == 'challenger', {}), metric_limit=2,
        qualify=qualify, screens=tuple(partial(screen, i) for i in range(len(qualification))),
    )
    if first_miss == len(qualification):
        assert selected == []
        assert reads == [('base', row) for row in qualification]
        assert result.prompt == 'base'
    else:
        assert selected == [first_miss]
        assert result.prompt == 'challenger'
        assert len(reads) == len(set(reads))


def test_requires_a_screen_for_each_qualification_row():
    with pytest.raises(ValueError, match='one callable search screen per qualification row'):
        run_qualification_prefix_cycle('base', (), (Row('v', 'validation'),), (Row('q', 'qualification'),),
                                       None, qualify=None, metric_limit=1, screens=())
