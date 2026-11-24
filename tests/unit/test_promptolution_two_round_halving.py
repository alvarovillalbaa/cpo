from itertools import product

import pytest

from benchmarks import promptolution_two_round_halving as study
from cpo import Observation, Row


def test_spare_quote_slot_can_recover_a_first_round_tie():
    rows = (Row('0', 'validation'), Row('1', 'validation'))
    grades = {'base': (True, False), 'first': (True, False), 'second': (True, True)}

    def observe(prompt, row):
        return Observation(grades[prompt][int(row.id)], {})

    args = 'base', ('first', 'second'), rows, observe
    old, _ = study._ORIGINAL(*args, 6)
    revised, counts = study.screen(*args, 6)
    assert old.finalist is None
    assert revised.finalist == 'second'
    assert counts == ((1, 2), (2, 2))
    assert revised.evaluations <= 6
    assert study.screen(*args, 5) == study._ORIGINAL(*args, 5)


def test_certified_two_round_cut_matches_eager_selection_for_every_four_row_panel():
    prompts = ('base', 'first', 'second')
    rows = tuple(Row(str(index), 'validation') for index in range(4))
    for values in product((False, True), repeat=len(prompts) * len(rows)):
        grades = dict(zip(product(prompts, rows), values, strict=True))
        seen = set()

        def observe(prompt, row):
            assert (prompt, row) not in seen
            seen.add((prompt, row))
            return Observation(grades[prompt, row], {})

        challenger = max(prompts[1:], key=lambda prompt: sum(grades[prompt, row] for row in rows[:2]))
        base, contender = (sum(grades[prompt, row] for row in rows) for prompt in ('base', challenger))
        finalist = challenger if contender > base else None
        result, counts = study.screen('base', prompts[1:], rows, observe, 10)
        assert result.finalist == finalist
        assert counts == (((base, 4), (contender, 4)) if finalist else None)
        assert result.evaluations == len(seen) <= 10


@pytest.mark.parametrize(('candidates', 'cap', 'critical'), (
    (('first', 'second'), 9, False),
    (('first', 'second'), 10, True),
    (('first', 'second', 'third'), 10, False),
))
def test_unfunded_cut_and_unsupported_panels_use_the_original_screen(monkeypatch, candidates, cap, critical):
    rows = tuple(Row(str(index), 'validation', critical=critical and index == 3) for index in range(4))
    expected = object()

    def original(incumbent, roster, panel, evaluate, quote):
        assert (incumbent, roster, panel, evaluate, quote) == ('base', candidates, rows, None, cap)
        return expected

    monkeypatch.setattr(study, '_ORIGINAL', original)
    assert study.screen('base', candidates, rows, None, cap) is expected
