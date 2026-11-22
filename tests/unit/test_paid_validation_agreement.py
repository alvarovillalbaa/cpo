from functools import partial

import pytest

from benchmarks.paid_validation_agreement import guarded_screen, witnessed_repair
from cpo import Observation, Row
from cpo.certified_shared_validation_cycle import run_certified_shared_validation_cycle
from cpo.two_sided_certificate_cycle import _run


def test_repair_requires_two_opposing_grades_on_the_same_case():
    grades = {('base', 'easy'): True, ('base', 'hard'): False, ('nominee', 'easy'): True}
    assert not witnessed_repair('base', 'nominee', grades)
    assert witnessed_repair('base', 'nominee', {**grades, ('nominee', 'hard'): True})


@pytest.mark.parametrize('seek,cap,finalist,lookups', [(False, 19, None, 6), (True, 7, None, 6),
                                                     (True, 8, 'nominee', 8)])
def test_spare_cap_reserves_the_pair_and_keeps_the_original_qualification_path(seek, cap, finalist, lookups):
    validation = tuple(Row(str(i), 'validation') for i in range(6))
    qualification = tuple(Row(str(i), 'qualification') for i in range(6, 9))

    def run(cycle):
        search = []

        def evaluate(prompt, row):
            key = prompt, row.id
            assert key not in search
            search.append(key)
            return Observation(key != ('base', '3'), {})

        result = cycle('base', ('nominee',), validation, qualification, evaluate, metric_limit=cap,
                       qualify=lambda prompt, *_: prompt != 'base')
        return result, search

    original, before = run(run_certified_shared_validation_cycle)
    result, after = run(partial(_run, screen=partial(guarded_screen, seek=seek)))
    assert after[:len(before)] == before
    assert result.search.finalist == finalist
    assert result.search.evaluations == len(after) == lookups
    if finalist is None:
        assert result.qualification.observations == original.qualification.observations[:1]
    else:
        assert after[len(before):] == [('base', '3'), ('nominee', '3')]
        assert result.qualification == original.qualification


def test_spare_lookups_skip_challengers_on_incumbent_passes():
    rows = tuple(Row(str(i), 'validation') for i in range(6))
    challenger_cases = []

    def evaluate(prompt, row):
        if prompt == 'nominee':
            challenger_cases.append(row.id)
        return Observation(True, {})

    result, counts = guarded_screen('base', ('nominee',), rows, evaluate, 19, seek=True)
    assert result.finalist is None and counts is None
    assert challenger_cases == ['0', '1', '2']
    assert result.evaluations == 9
