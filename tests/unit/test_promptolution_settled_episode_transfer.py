import pytest

from benchmarks import promptolution_settled_episode_transfer as study


@pytest.mark.parametrize('task', study.donor.TASKS)
def test_geometry_preserves_roster_and_makes_validation_and_admission_disjoint(task):
    plan = study.prepare()
    held = tuple(range(study.donor.HOLDOUT))
    seed = plan['seeds'][0]
    layout = study.layout(plan, task, seed, held)
    original = study.donor.schedule(plan, task, seed, held)
    all_cases = list(held)
    for index, ((roster, train, validation, proof), old) in enumerate(zip(layout, original, strict=True)):
        assert roster == old[0] and train == tuple(old[2])
        assert validation == tuple(old[1][index * 6:(index + 1) * 6])
        assert proof == tuple(old[3][:4])
        assert len(roster) == 2 and len(train) == 16 and len(validation) == 6 and len(proof) == 4
        all_cases.extend((*train, *validation, *proof))
    assert len(all_cases) == len(set(all_cases))


@pytest.mark.parametrize('method', (study.SETTLED, study.FEEDBACK, 'gepa-sequential/validation-6/cap-32',
                                    'gepa-batched/validation-6/cap-32', study.BASE))
def test_real_runners_charge_disjoint_paid_roles(method):
    plan = study.prepare()
    seed = plan['seeds'][0]
    windows = study.layout(plan, 'gsm8k', seed, tuple(range(study.donor.HOLDOUT)))
    matrix = {name: ('0' if name == plan['startingProgram'] else '1') * 300 for name in plan['programs']}
    winner, counts, trace = study.play(plan, matrix, windows, seed, method)
    selected, _, observations = trace
    keys = [key for key, _ in observations]
    assert winner == selected and winner in matrix
    assert counts['paidLookups'] == len(keys) == len(set(keys))
    assert all(case >= study.donor.HOLDOUT for _, _, case in keys)
    if method == study.BASE:
        assert not keys and selected == plan['startingProgram']
    else:
        assert selected != plan['startingProgram']
        assert any(prompt != plan['startingProgram'] for _, prompt, _ in keys)


def test_matched_budget_reselects_among_affordable_controls_only():
    plan = {'resampleSeed': 11, 'draws': 3, 'seeds': [7]}
    totals = {name: {'paidLookups': spend} for name, spend in (('cpo', 3), ('feasible', 2), ('expensive', 4))}
    count = study.donor.HOLDOUT
    scores = {'cpo': [1] * count, 'feasible': [0] * count, 'expensive': [1] * count}
    result = study.compare(plan, [(totals, scores)], 'cpo', ('feasible', 'expensive'))
    assert result['control'] == 'feasible'
    assert result['passDelta'] == count
    assert result['affordableControls'] == ('feasible',)
    assert result['interval95PercentagePoints'] == [100, 100]
    uncapped = study.compare(plan, [(totals, scores)], 'cpo', ('expensive',), enforce_cap=False)
    assert uncapped['comparedControls'] == ('expensive',)
    assert uncapped['paidLookupDelta'] == -1
