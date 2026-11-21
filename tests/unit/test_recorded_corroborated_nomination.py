from itertools import product

from benchmarks import recorded_corroborated_nomination as study


def test_every_small_gain_combination_matches_the_exact_ordering():
    for first_validation, rival_validation, first_training, rival_training in product(
            range(1, 5), range(1, 5), range(-3, 4), range(-3, 4)):
        training = {'first': first_training, 'rival': rival_training}
        offers = (('first', first_validation), ('rival', rival_validation))
        scores = {'start': 0, **{prompt: min(margin, training[prompt]) for prompt, margin in offers}}
        expected = max(scores, key=scores.__getitem__)
        targets = []

        def prove(prompt, target):
            targets.append((prompt, target))
            return training[prompt] >= target

        assert study.nominate('start', offers, prove) == expected
        assert len(targets) == len(set(targets))
        assert all(target <= rival_validation for _, target in targets)


def test_two_certificates_can_replace_a_training_supported_primary():
    cells = {prompt: tuple((score, None, False) for score in grades) for prompt, grades in {
        'start': (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        'first': (1, 0, 0, 0, 1, 1, 1, 1, 0, 0),
        'rival': (1, 1, 0, 0, 0, 1, 1, 1, 0, 1),
    }.items()}
    cohorts = ([0, 1, 2, 3], [4, 5, 6], [7, 8], [9])
    args = (cells, 'start', ('rival', 'first'), cohorts, 31, 15)
    _, old, old_grades = study.parent.run_trial(*args)
    metrics, current, grades = study.run_trial(*args)
    assert old[2:4] == ('first', 'first') and old_grades == (0,)
    assert current[2:4] == ('rival', 'rival') and grades == (1,)
    assert metrics['paidAlternateTrials'] == metrics['alternateNominations'] == 1
    assert metrics['retrospectiveCeilingPasses'] == 1
    assert metrics['searchLookups'] <= args[-1]

    # Without room to settle both contenders, retain the original allowance and decision.
    constrained = (*args[:-1], 14)
    assert study.run_trial(*constrained) == study.parent.run_trial(*constrained)

    # A better held-out grade can't make an independently rejected prompt eligible.
    bad_rival = (*cells['rival'][:7], (0, None, False), *cells['rival'][8:])
    assert study.retrospective_ceiling({**cells, 'rival': bad_rival}, 'start', ('first', 'rival'), cohorts) == 0
