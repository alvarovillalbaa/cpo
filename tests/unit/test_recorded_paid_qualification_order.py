from itertools import product

import pytest

from benchmarks import recorded_paid_qualification_order as study
from cpo import Row


@pytest.mark.parametrize('arm', study.ARMS)
def test_only_qualification_lookups_change_for_cpo_and_both_native_controls(arm):
    plan, archive, _ = study.prepare()
    settings = plan['datasets']['aime']
    cells = study.math.load_cells('aime', archive['aime']['record'])
    for seed in settings['seeds'][:2]:
        cohorts = study.math.split_cases(len(next(iter(cells.values()))), seed, settings['cohorts'])
        for start in tuple(cells)[1:]:
            roster = tuple(prompt for prompt in cells if prompt != start)
            arguments = (cells, start, roster, cohorts, seed, plan['searchCap'], arm)
            original, trace, grades = study.original_trial(*arguments)
            for mode in study.ALTERNATIVES:
                actual, new_trace, new_grades = study.run_trial(*arguments, mode)
                assert actual['searchLookups'] == original['searchLookups']
                assert new_trace[:4] == trace[:4] and new_grades == grades
                assert actual['paidLookups'] == actual['searchLookups'] + actual['qualificationLookups']
                if mode == study.CREDIT:
                    assert actual['qualificationLookups'] <= original['qualificationLookups']


@pytest.mark.parametrize('mode', study.ALTERNATIVES)
def test_bounds_and_unique_paid_reads_on_every_three_case_matrix(mode):
    rows = tuple(Row(str(case), 'qualification') for case in range(3))
    old, new = 'old', 'new'
    keys = tuple((prompt, row.id) for prompt in (old, new) for row in rows)
    for bits in product((False, True), repeat=6):
        grid = dict(zip(keys, bits, strict=True))
        prefix = {}
        for row in rows:
            prefix[row.id] = grid[old, row.id]
            if not prefix[row.id]:
                break
        paid = {(old, case) for case in prefix}

        def read(prompt, row, repeat):
            key = (prompt, row.id)
            assert repeat == 0 and key not in paid
            paid.add(key)
            return grid[key]

        result = study.qualify_with_prefix(old, new, rows, read, prefix, ((2, 3), (3, 4)), 5, mode)
        exact_gain = sum(bits[3:]) - sum(bits[:3])
        assert result.prompt == (new if exact_gain > 0 else old)
        assert result.lower_gain <= exact_gain <= result.upper_gain
        assert len(result.observations) == len(paid)
        cells = {old: [(value,) for value in bits[:3]], new: [(value,) for value in bits[3:]]}
        assert study.qualification_floor(cells, old, new, range(3)) <= len(paid)
