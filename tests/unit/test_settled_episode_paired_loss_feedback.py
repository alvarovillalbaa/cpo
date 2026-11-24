from collections import Counter, defaultdict
from itertools import product

import pytest

from benchmarks.settled_episode_paired_loss_feedback import SUBTYPES, fit_tables, menu, paired_loss
from cpo.paired_qualification import QualificationObservation
from cpo.settled_episode_schedule import choose_schedule


@pytest.mark.parametrize(('rows', 'loss'), (
    ((('old', 'a', 0, True), ('new', 'a', 0, False)), True),
    ((('new', 'a', 0, False), ('old', 'a', 0, True)), True),
    ((('old', 'a', 0, True), ('new', 'a', 1, False)), False),
    ((('old', 'a', 0, True), ('new', 'b', 0, False)), False),
    ((('old', 'a', 0, False), ('new', 'a', 0, True)), False),
    ((('old', 'a', 0, True), ('other', 'a', 0, False)), False),
    ((('new', 'a', 0, False),), False),
))
def test_signal_requires_observed_grades_for_the_same_pair(rows, loss):
    assert paired_loss('old', 'new', tuple(QualificationObservation(*row) for row in rows)) is loss


def test_fit_matches_actual_probe_costs_and_keeps_unsupported_states_fixed():
    reference = tuple((f'base-{state}', 'original', 'original') for state in range(3))
    options = ('original', 'alternative')
    pairs = ((False, False), (False, True), (True, False), (True, True))
    counts = {'cohort': Counter(pair[0] for pair in pairs)}
    support = defaultdict(set, {(1, 1): {'first', 'second', 'third'}, (2, 1): {'first', 'second'}})
    points = defaultdict(Counter)
    budgets = {'cohort': 40}

    def measured(state, rule):
        bonus = (state + 1) * 3 if rule[-1] == 'alternative' else 1 if rule[1] == 'alternative' else 0
        return {'holdoutPasses': 4 + bonus, 'paidLookups': 6 if bonus else 8}

    for state, rule in enumerate(reference):
        for setting in {*menu(rule, 0, options), *menu(rule, 1, options)}:
            for pair in pairs:
                if sum(pair) == state:
                    points['cohort', state, setting].update(measured(state, setting))

    tables = set()
    for subtype in range(2):
        choices = [menu(rule, subtype, options) if len(support[state, subtype]) >= 3 else (rule,)
                   for state, rule in enumerate(reference)]
        tables.update(product(*choices))
    feasible = []
    for table in tables:
        total = Counter()
        for pair in pairs:
            paid = []

            def probe(_prompt, index):
                paid.append(index)
                return pair[index]

            rule = choose_schedule('initial', range(2), probe, actions=table)
            total.update(measured(sum(pair), rule), paidLookups=len(paid))
        if total['paidLookups'] <= budgets['cohort']:
            feasible.append((-total['holdoutPasses'], total['paidLookups'], table))

    quality, spend, winner = min(feasible)
    result = fit_tables(reference, options, budgets, counts, points, support, 3)
    assert result['rules'] == winner
    assert result['rules'][1][-1] == 'alternative'
    assert result['rules'][0] == reference[0] and result['rules'][2] == reference[2]
    assert result['alteredSubtype'] == SUBTYPES[1]
    assert result['points'] == {'cohort': {'holdoutPasses': -quality, 'paidLookups': spend}}
    assert result['feasibleTables'] == len(feasible)
