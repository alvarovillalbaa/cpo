from itertools import product

from benchmarks import recorded_qualification_margin as study
from cpo import Row


def test_two_gain_proof_agrees_with_every_single_case_omission_and_reuses_prefix():
    rows = tuple(Row(str(index), 'qualification') for index in range(4))
    for values in product((False, True), repeat=8):
        old, new = values[:4], values[4:]
        prefix = {}
        for row, passed in zip(rows, old, strict=True):
            prefix[row.id] = passed
            if not passed:
                break
        calls = {('incumbent', key) for key in prefix}

        def observe(prompt, row, repeat):
            assert repeat == 0 and (prompt, row.id) not in calls
            calls.add((prompt, row.id))
            return (old if prompt == 'incumbent' else new)[int(row.id)]

        detail = study.minimum_two('incumbent', 'challenger', rows, observe, prefix, ((2, 6), (3, 6)), 0,
                                   study.adapter.EXPECTED)
        differences = [after - before for before, after in zip(old, new, strict=True)]
        positive_after_every_omission = all(sum(differences) - value > 0 for value in differences)
        assert (detail.status == 'promoted') == positive_after_every_omission
        assert len(detail.observations) == len(calls) <= 8
