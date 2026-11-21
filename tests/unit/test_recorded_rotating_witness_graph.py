"""T2 tests for the offline parent-linked comparison on a tiny graded graph."""

from benchmarks.recorded_rotating_witness_graph import opening_proof, search
from cpo import Observation, Row
from cpo.family_qualification import certify_family_qualification


TRAIN = (Row('train-a', 'task'), Row('train-b', 'task'))
VALIDATION = tuple(Row(case, 'task') for case in ('pass', 'miss', 'tie'))
GRADES = {'old': {'pass'}, 'rewrite': {'pass', 'miss'}, 'repair': set(), 'child': {'pass', 'miss', 'tie'}}


def test_graph_uses_the_witness_selected_parent_and_its_own_paid_feedback():
    calls, edges = [], []

    def evaluate(prompt, row):
        calls.append((prompt, row.id))
        return Observation(row.id in GRADES[prompt], {'parent': prompt, 'row': row.id})

    def propose(parent, feedback):
        edges.append(parent)
        assert {row.id for row, _ in feedback} == {'train-a', 'train-b'}
        assert all(reply.feedback == {'parent': parent, 'row': row.id} for row, reply in feedback)
        return 'child'

    result, activity = search('old', TRAIN, VALIDATION, evaluate, propose, opening=('rewrite', 'repair'),
                              cap=24, seed=5, later_slots=1)
    assert result.prompt == 'child'
    assert edges == ['rewrite']
    assert result.evaluations == len(set(calls)) == len(calls) <= 24
    assert activity['descendantSlots'] == activity['laterMoves'] == 1


def test_graph_does_not_buy_a_proposal_without_budget_for_its_screen():
    def evaluate(prompt, row):
        return Observation(row.id in GRADES[prompt], {})

    def propose(*_):
        raise AssertionError('The remaining budget does not fund a later screen')

    result, activity = search('old', TRAIN, VALIDATION, evaluate, propose, opening=('rewrite', 'repair'),
                              cap=8, seed=5, later_slots=4)
    assert result.prompt == 'rewrite'
    assert result.evaluations <= 8 and activity['descendantSlots'] == 0


def test_exact_opening_falls_back_when_the_screen_leader_loses_a_family():
    rows = (*VALIDATION, Row('other-family', 'protected'))
    grades = {'old': {'pass', 'other-family'}, 'rewrite': {'pass', 'miss', 'tie'},
              'repair': {'pass', 'miss', 'other-family'}}
    for prioritize in (False, True):
        calls = []

        def evaluate(prompt, row):
            calls.append((prompt, row.id))
            return Observation(row.id in grades[prompt], {})

        result, counts = opening_proof('old', ('rewrite', 'repair'), rows, evaluate, certify_family_qualification,
                                       cap=12, seed=9, prioritize=prioritize)
        assert result.prompt == 'repair'
        assert counts['proofsAttempted'] == 2
        assert result.evaluations == len(set(calls)) == len(calls) <= 12
