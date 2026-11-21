from types import SimpleNamespace

import pytest

from benchmarks import witness_first_proof_fit as source, witness_first_proof_gain as replay
from benchmarks.witness_admission_retry import Decision


def test_rejects_an_evaluation_subject_before_accessing_any_labels():
    with pytest.raises(ValueError, match='subjects must be disjoint'):
        replay.train([SimpleNamespace(subject='evaluation')], {'evaluation'})


def test_training_scores_the_deployed_prompt_after_qualification():
    inputs = {name: (number,) + (0.0,) * 8 for number, name in enumerate(('first', 'helpful', 'rejected'))}
    decisions = {'first': Decision('first', 12, 'promoted'), 'helpful': Decision('helpful', 8, 'promoted'),
                 'rejected': Decision('incumbent', 17, 'rejected')}
    outcomes = {'first': (1, 0), 'helpful': (1, 1), 'incumbent': (0, 0)}
    episode = source.Episode('development', 'first', 'first', inputs, decisions.__getitem__, outcomes.__getitem__)

    _, report = replay.train([episode], {'evaluation'})

    assert report['labels'] == {'candidates': 3, 'aboveOriginal': 1, 'belowOriginal': 1}


def test_guard_keeps_the_best_gain_at_or_below_the_nominees_predicted_cost():
    episode = SimpleNamespace(nominee='first', inputs={'first': (0.0, 1.0), 'costly': (2.0, 2.0),
                                                      'affordable': (1.0, 1.0), 'lower': (-1.0, 0.0)})

    assert replay.guarded_choice(episode, (1.0, 0.0), (0.0, 1.0)) == 'affordable'
    assert replay.guarded_choice(episode, (0.0, 0.0), (0.0, 1.0)) == 'first'
