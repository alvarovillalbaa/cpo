from itertools import product

from benchmarks import recorded_joint_training_qualification as study
from cpo import Row


def test_balanced_bound_matches_every_small_board_with_and_without_paid_grades():
    prompts = ('old', 'new')
    panels = ((Row('q1', 'qualification'),), (Row('t1', 'training'), Row('t2', 'training')))
    keys = [tuple((prompt, row.id) for prompt in prompts for row in rows) for rows in panels]
    for grades in product((False, True), repeat=6):
        outcomes = dict(zip(keys[0] + keys[1], grades, strict=True))
        expected = 2 * (grades[1] - grades[0]) + sum(grades[4:]) - sum(grades[2:4]) > 0
        for prefix in ((0, 0), (1, 0), (2, 1), (2, 4)):
            paid = tuple({key: outcomes[key] for key in panel[:width]}
                         for panel, width in zip(keys, prefix, strict=True))
            bought = set()

            def read(prompt, row):
                key = prompt, row.id
                assert all(key not in ledger for ledger in paid) and key not in bought
                bought.add(key)
                return outcomes[key]

            assert study.settle_balanced(prompts, panels, (read, read), paid, (1, 3), (7, 2)) == expected
            assert len(bought) <= 6 - sum(prefix)


def test_joint_proof_can_extend_qualification_and_accept_only_after_strict_independent_gain():
    cells = {prompt: tuple((grade, None, False) for grade in outcomes) for prompt, outcomes in {
        'start': (1, 0, 0, 0, 1, 0, 0, 0, 0, 0),
        'new': (0, 0, 0, 0, 1, 1, 0, 1, 1, 1),
    }.items()}
    cohorts = ([0, 1, 2, 3], [4, 5, 6], [7, 8], [9])
    args = (cells, 'start', ('new',), cohorts, 31, 10)
    old, _, _, _ = study.prior.run_trial(*args, ())
    nonloss, trace, grades, _ = study.run_trial(*args, study.NONLOSS)
    assert trace[3] == 'start' and grades == (0,)
    assert nonloss['qualificationLookups'] == old['qualificationLookups']
    balanced, trace, grades, _ = study.run_trial(*args, study.BALANCED)
    assert trace[3] == 'new' and grades == (1,)
    assert balanced['qualificationLookups'] == 4
    assert balanced['extraQualificationLookups'] == balanced['qualificationLookups'] - old['qualificationLookups'] == 1
    assert balanced['searchLookups'] == old['searchLookups'] + balanced['trainingLookups']

    unqualified = {**cells, 'new': (*cells['new'][:7], (0, None, False), (0, None, False), cells['new'][-1])}
    for arm in study.ARMS:
        point, trace, grades, bucket = study.run_trial(unqualified, *args[1:], arm)
        assert trace[3] == 'start' and grades == (0,) and bucket is None
        assert 'trainingLookups' not in point and point['extraQualificationLookups'] == 0
