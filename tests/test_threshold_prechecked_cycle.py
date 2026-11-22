from itertools import product

import pytest

from cpo import Observation, Row
from cpo.prechecked_certificate_cycle import run_prechecked_certificate_cycle
from cpo.threshold_prechecked_cycle import run_threshold_prechecked_cycle


def test_a_single_possible_gain_skips_search_when_two_are_required():
    validation = (Row('v0', 'validation'),)
    proof = tuple(Row(str(index), 'qualification') for index in range(4))
    result = run_threshold_prechecked_cycle(
        'start', ('new',), validation, proof, lambda *_: pytest.fail('The gain is impossible'),
        metric_limit=2, qualify=lambda _, row, __: row.id != '0', minimum_gain=2,
    )
    assert result.prompt == 'start' and result.search.evaluations == 0
    assert result.qualification.upper_gain == 1 and result.qualification_evaluations == 4


def test_all_four_case_proofs_preserve_deployment_and_charge_each_reply_once():
    validation = (Row('v0', 'validation'),)
    proof = tuple(Row(str(index), 'qualification') for index in range(4))
    for grades in product((False, True), repeat=8):
        passed = {'start': grades[:4], 'new': grades[4:]}
        for minimum in range(1, 5):
            def replay(cycle):
                paid = set()

                def qualify(prompt, row, repeat):
                    assert repeat == 0 and (prompt, row.id) not in paid
                    paid.add((prompt, row.id))
                    return passed[prompt][int(row.id)]

                result = cycle('start', ('new',), validation, proof,
                               lambda prompt, _: Observation(prompt == 'new', {}),
                               metric_limit=2, qualify=qualify, minimum_gain=minimum)
                assert result.qualification_evaluations == len(paid) <= 8
                return result

            ordinary = replay(run_prechecked_certificate_cycle)
            threshold = replay(run_threshold_prechecked_cycle)
            assert threshold.prompt == ordinary.prompt
            if minimum == 1:
                assert threshold == ordinary
