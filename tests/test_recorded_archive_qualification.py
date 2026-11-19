from benchmarks.recorded_archive_qualification import nominate, qualification
from cpo import Observation, Row


PANEL = (Row('critical', 'task', True), Row('routine', 'task'), Row('edge', 'task'))


def test_nomination_can_reuse_paid_ties_without_buying_a_second_proposal():
    paid = {('head', 'critical'): Observation(True, {}), ('head', 'routine'): Observation(False, {}),
            ('head', 'edge'): Observation(True, {}), ('known-loss', 'edge'): Observation(False, {}),
            ('tie', 'critical'): Observation(True, {})}
    checks = []

    def observe(prompt, row):
        checks.append((prompt, row.id))
        return Observation(True, {})

    result = nominate('head', 'incumbent', ('known-loss', 'tie'), {'known-loss', 'tie'}, paid, PANEL,
                      observe, evaluation_limit=1, proposal_limit=0)
    assert result == ('tie', 1, [])
    assert checks == [('tie', 'edge')]


def test_early_critical_rejection_leaves_budget_for_a_second_challenger():
    values = {'incumbent': (True, False, False), 'head': (False, True, True), 'alternate': (True, True, False)}
    scores = {name: dict(zip((row.id for row in PANEL), vector)) for name, vector in values.items()}

    def observe(prompt, row):
        return Observation(scores[prompt][row.id], {})

    selected, count, attempts = qualification('incumbent', 'head', 'alternate', PANEL, observe,
                                               metric_limit=6, paired=False)
    assert selected == 'alternate' and count == 6
    assert [attempt['status'] for attempt in attempts] == ['critical_regression', 'promote']


def test_complete_pair_chooses_the_larger_qualified_gain_only_when_funded():
    values = {'incumbent': (True, False, False), 'head': (True, True, False), 'alternate': (True, True, True)}
    scores = {name: dict(zip((row.id for row in PANEL), vector)) for name, vector in values.items()}

    def observe(prompt, row):
        return Observation(scores[prompt][row.id], {})

    assert qualification('incumbent', 'head', 'alternate', PANEL, observe, metric_limit=8, paired=True)[:2] == ('head', 5)
    winner, count, decisions = qualification('incumbent', 'head', 'alternate', PANEL, observe, metric_limit=9, paired=True)
    assert winner == 'alternate' and count == 9
    assert [entry['status'] for entry in decisions] == ['promote', 'promote']
