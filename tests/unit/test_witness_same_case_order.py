from collections import Counter
from fractions import Fraction
from itertools import product

import pytest

from benchmarks.witness_same_case_order import prove, rates


def test_conditioning_uses_the_other_side_only_when_its_reply_is_paid():
    paired = Counter({(True, True): 4, (False, False): 4})
    for side in (0, 1):
        assert rates(side, None, [4, 4], [8, 8], paired, True) == Fraction(1, 2)
        assert rates(side, False, [4, 4], [8, 8], paired, True) == Fraction(1, 4)
        assert rates(side, True, [4, 4], [8, 8], paired, True) == Fraction(3, 4)
        assert rates(side, True, [4, 4], [8, 8], paired, False) == Fraction(1, 2)


@pytest.mark.parametrize('conditional', [False, True])
def test_exact_gate_and_cost_on_every_small_base_and_reserve(conditional):
    base, reserve = (0, 1), (2, 3)
    for bits in product((False, True), repeat=8):
        grades = dict(zip(product(('start', 'rival'), (*base, *reserve)), bits, strict=True))

        def grade(prompt, case):
            return grades[prompt, case]

        initial = sum(grade('rival', case) - grade('start', case) for case in base)
        final = initial or sum(grade('rival', case) - grade('start', case) for case in reserve)
        expected = 'promoted' if final > 0 else 'rejected'
        for cap in (0, 5, 8):
            result = prove('start', 'rival', base, reserve, grade, {}, 1, cap, conditional=conditional)
            assert len({(row.prompt, row.row_id) for row in result.observations}) == len(result.observations) <= cap
            assert result.status == expected or (cap < 8 and result.status == 'undecided')
            if any(int(row.row_id) in reserve for row in result.observations):
                assert initial == 0
                assert result.observations[4].row_id in ('2', '3')


def test_shared_validation_and_proof_case_is_rejected():
    with pytest.raises(ValueError, match='independent'):
        prove('start', 'rival', [1], [2], lambda *_: True, {('rival', 2): True}, 1, 4, conditional=True)
