from collections import Counter
from fractions import Fraction
from itertools import product

from benchmarks import recorded_joint_candidate_race as study
from cpo import Observation, Row


def test_earlier_training_can_be_the_cheaper_rejection():
    quotes = ((Fraction(3, 4), 2, ()), (Fraction(1, 2), 1, ()))
    assert study.panel_order(quotes, study.VALIDATION_FIRST) == (0, 1)
    assert study.panel_order(quotes, study.ADAPTIVE_ORDER) == (1, 0)
    assert study.panel_order(((1, 0, ()), quotes[1]), study.VALIDATION_FIRST) == (1, 0)
    assert study.panel_order((quotes[0], (1, 0, ())), study.ADAPTIVE_ORDER) == (0, 1)


def test_both_races_find_a_joint_certificate_on_every_small_funded_board():
    prompts = ('start', 'first', 'second')
    validation = (Row('v1', 'validation', critical=True), Row('v2', 'validation'))
    training = (Row('t1', 'training'),)
    rows = validation + training
    keys = tuple((prompt, row.id) for prompt in prompts for row in rows)
    for grades in product((False, True), repeat=len(keys)):
        board = dict(zip(keys, grades, strict=True))
        target = sum(grades[:2]) + 1
        valid = {prompt for prompt in prompts[1:]
                 if sum(board[prompt, row.id] for row in validation) >= target
                 and board[prompt, 't1'] > board['start', 't1']
                 and (not grades[0] or board[prompt, 'v1'])}
        for mode in study.MODES:
            ledger, audit = {}, Counter()

            def read(prompt, row):
                key = prompt, row.id
                assert key not in ledger
                ledger[key] = Observation(board[key], {})
                return ledger[key]

            result = study.race(prompts[0], prompts[1:], validation, training, read, ledger,
                                cap=9, mode=mode, audit=audit)
            assert (result is None) == (not valid)
            if result:
                winner, _ = result
                assert winner in valid and ledger[winner, 't1'].passed
                assert sum(ledger[winner, row.id].passed for row in validation
                           if (winner, row.id) in ledger) >= target
            assert len(ledger) == audit['trainingReads'] + audit['validationReads']
            if mode == study.VALIDATION_FIRST:
                assert audit['trainingBeforeValidationCertificate'] == 0


def test_training_changes_the_independent_nominee_with_no_second_attempt():
    cells = {prompt: tuple((grade, None, False) for grade in outcomes) for prompt, outcomes in {
        'start': (0, 0, 0, 0, 0, 0, 0, 0, 0),
        'first': (0, 0, 0, 0, 1, 1, 1, 1, 0),
        'second': (1, 1, 0, 0, 1, 1, 1, 1, 1),
    }.items()}
    cohorts = ([0, 1, 2, 3], [4, 5], [6, 7], [8])
    args = (cells, 'start', ('first', 'second'), cohorts, 31, 12)
    _, trace, original_grades = study.core.trial(*args, study.core.FIRST)
    assert trace[2:4] == ('first', 'start') and original_grades == (0,)
    for mode in study.MODES:
        point, trace, grades = study.run_trial(*args, mode)
        assert trace[2:4] == ('second', 'second') and grades == (1,)
        assert point['qualificationLookups'] <= 2 * len(cohorts[2])
        assert point['searchLookups'] <= args[-1]
