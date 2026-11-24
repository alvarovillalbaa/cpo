"""T2 binary fixture for exact qualification and correlated scheduling."""

from fractions import Fraction
from functools import cache
from itertools import product
from math import prod

from cpo.joint_order_qualification import _order, finish_joint_order
from cpo.optimizer import Row
from cpo.paired_qualification import QualificationObservation


def test_grouped_expected_cost_matches_uncompressed_search_over_all_queries():
    weights = (13, 3, 6, 19)
    worlds = tuple(product(range(4), repeat=2))
    grades = tuple(tuple((bit >> shift) & 1 for bit in world for shift in (1, 0)) for world in worlds)
    mass = tuple(prod(weights[bit] for bit in world) for world in worlds)

    @cache
    def optimal(available, hidden):
        posterior = {index: grades[index] for index in available}
        peek = grades[available[0]]
        favorable = sum(value for offset, value in enumerate(peek) if offset not in hidden)
        if favorable >= 3 or favorable + len(hidden) < 3:
            return Fraction(0)
        total = sum(mass[index] for index in available)
        choices = []
        for query in hidden:
            remaining = tuple(offset for offset in hidden if offset != query)
            effort = Fraction(1)
            for value in (0, 1):
                subset = tuple(index for index, world in posterior.items() if world[query] == value)
                likelihood = Fraction(sum(mass[index] for index in subset), total)
                effort += likelihood * optimal(subset, remaining)
            choices.append(effort)
        return min(choices)

    assert _order(2, 1, weights, (2, 0, 0, 0, 0), 0)[0] == optimal(tuple(range(16)), (0, 1, 2, 3))
    known = tuple(index for index, world in enumerate(grades) if world[0] == 1)
    assert _order(2, 1, weights, (1, 0, 1, 0, 0), 1)[0] == optimal(known, (1, 2, 3))


def test_qualification_matches_complete_scores_under_every_three_case_assignment():
    rows = tuple(Row(str(index), 'proof') for index in range(3))
    priors = {None: (50, 5, 2, 60)}
    for base, challenger in product(product((False, True), repeat=3), repeat=2):
        for minimum in (1, 2, 3):
            grades = {'base': base, 'better': challenger}
            history = [QualificationObservation('base', '0', 0, base[0])]
            seen = {('base', '0')}

            def read(prompt, row, repeat):
                assert repeat == 0 and (prompt, row.id) not in seen
                seen.add((prompt, row.id))
                value = grades[prompt][int(row.id)]
                history.append(QualificationObservation(prompt, row.id, repeat, value))
                return value

            expected = sum(challenger) - sum(base)
            outcome = finish_joint_order('base', 'better', rows, read, history, ((1, 2), (2, 2)),
                                         minimum, 8, priors=priors)
            assert outcome.prompt == ('better' if expected >= minimum else 'base')
            assert outcome.lower_gain <= expected <= outcome.upper_gain
            assert len(seen) == len(outcome.observations) <= 6
