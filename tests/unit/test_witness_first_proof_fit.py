from benchmarks import witness_first_proof_fit as replay
from benchmarks.witness_admission_retry import Decision


def test_paid_features_only_count_observed_matched_cases():
    grades = {('start', 3): False, ('start', 4): True, ('first', 3): True, ('rival', 4): False, ('rival', 5): True}
    inputs = replay.features('start', 'first', ('first', 'rival'), grades, 3, {'first': 0, 'rival': 4})
    nominees = {prompt: dict(zip(replay.FEATURES, vector, strict=True)) for prompt, vector in inputs.items()}

    assert nominees['first']['paired-wins'] == 1 / 3
    assert nominees['rival']['paired-wins'] == 0
    assert nominees['rival']['paired-losses'] == 1 / 3
    assert nominees['rival']['validation-coverage'] == 2 / 3
    assert nominees['rival']['paired-coverage'] == 1 / 3


def test_fitting_uses_proof_labels_and_never_scores_holdout():
    inputs = {'first': (1.0,) + (0.0,) * 8, 'rival': (0.0,) * 9}
    decisions = {'first': Decision('start', 14, 'rejected'), 'rival': Decision('rival', 9, 'promoted')}

    def holdout(_prompt):
        raise AssertionError('Fitting cannot inspect held-out grades')

    episode = replay.Episode('development', 'first', 'first', inputs, decisions.__getitem__, holdout)
    weights, report = replay.train([episode])

    assert report['candidateLabels'] == 2
    assert report['promotedLabels'] == 1
    assert {replay.choose(inputs, vector) for vector in weights.values()} == {'rival'}


def test_zero_weight_ties_keep_the_existing_nominee():
    inputs = {'first': (1.0,), 'rival': (0.0,)}

    assert replay.choose(inputs, (0.0,)) == 'first'
