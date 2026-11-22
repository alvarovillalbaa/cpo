from fractions import Fraction
from functools import lru_cache
from itertools import product

from cpo import Row
from cpo.regression_free_qualification import _next_read, certify_regression_free_qualification


def test_regression_free_proof_matches_every_four_case_board_and_prefix():
    rows = tuple(Row(str(i), 'task' if i < 3 else 'other') for i in range(4))
    for bits in product((False, True), repeat=8):
        grades = {'start': bits[:4], 'next': bits[4:]}
        expected = (all(not old or new for old, new in zip(bits[:4], bits[4:], strict=True))
                    and sum(bits[4:]) > sum(bits[:4]))
        for length in range(5):
            prefix = bits[:length]
            paid = {('start', row.id) for row in rows[:length]}

            def qualify(prompt, row, repeat):
                key = prompt, row.id
                assert repeat == 0 and key not in paid
                paid.add(key)
                return grades[prompt][int(row.id)]

            result = certify_regression_free_qualification(
                'start', 'next', rows, qualify, incumbent_prefix=prefix,
                validation_counts=((sum(bits[:4]), 4), (sum(bits[4:]), 4)),
            )
            assert result.prompt == ('next' if expected else 'start')
            assert len(result.observations) == len(paid) <= 8
            assert [reply.passed for reply in result.observations[:length]] == list(prefix)


def test_single_unread_row_costs_one_and_a_half_reads_at_equal_rates():
    assert _next_read((1, 0, 0, 0, 0), False, (2, 2)) == (24, (0, 0))


def test_grouped_scheduler_matches_unrestricted_two_row_search():
    @lru_cache(maxsize=None)
    def expected(pairs, rates):
        if (True, False) in pairs:
            return Fraction()
        repaired = (False, True) in pairs
        risky = any(old is not False and new is not True for old, new in pairs)
        possible_repair = any(old is not True and new is not False for old, new in pairs)
        if (repaired and not risky) or not possible_repair:
            return Fraction()
        choices = []
        for index, pair in enumerate(pairs):
            for side, grade in enumerate(pair):
                if grade is not None:
                    continue
                need = 1
                for passed, likelihood in ((False, 4 - rates[side]), (True, rates[side])):
                    next_pair = tuple(passed if i == side else value for i, value in enumerate(pair))
                    next_pairs = (*pairs[:index], next_pair, *pairs[index + 1:])
                    need += Fraction(likelihood, 4) * expected(next_pairs, rates)
                choices.append(need)
        return min(choices)

    row_states = ((None, None), (False, None), (True, None), (None, False), (None, True))
    for states in product(range(len(row_states)), repeat=2):
        pairs = tuple(row_states[state] for state in states)
        counts = tuple(states.count(state) for state in range(len(row_states)))
        scale = 4 ** sum(value is None for pair in pairs for value in pair)
        for rates in product((1, 2, 3), repeat=2):
            cost, _ = _next_read(counts, False, rates)
            assert Fraction(cost, scale) == expected(pairs, rates)


def test_large_panel_reuses_prefix_and_retains_original_callback_rows():
    rows = tuple(Row(str(i), 'task') for i in range(9))
    paid = {('start', '0')}

    def qualify(prompt, row, repeat):
        key = prompt, row.id
        assert repeat == 0 and key not in paid
        assert row is rows[int(row.id)]
        paid.add(key)
        return prompt == 'next' or row.id != '0'

    result = certify_regression_free_qualification('start', 'next', rows, qualify, incumbent_prefix=(False,))
    assert result.prompt == 'next'
    assert len(result.observations) == len(paid) <= 18
