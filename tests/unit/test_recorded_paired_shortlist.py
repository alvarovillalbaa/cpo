from collections import Counter

from benchmarks import recorded_paired_shortlist as study
from cpo import Observation, Row


def run(*, keep_ties, cap=100, winner_protects=True):
    rows = tuple(Row(str(case), 'validation', case == 1) for case in range(6))
    training = (Row('t1', 'training'), Row('t2', 'training'))
    roster = tuple(f'p{index}' for index in range(8))
    scores = {'start': {'1', '2', '3'}, **{prompt: {'0', '1'} for prompt in roster}}
    scores['p7'] = {row.id for row in rows}
    if not winner_protects:
        scores['p7'].remove('1')
    ledger, audit = {}, Counter()

    def observe(prompt, row):
        assert row in rows
        key = prompt, row.id
        if key not in ledger:
            assert len(ledger) < cap
            ledger[key] = Observation(row.id in scores[prompt], {})
        return ledger[key]

    winner = study.shortlist('start', roster, rows, training, observe, ledger, cap=cap,
                             keep_ties=keep_ties, audit=audit)
    if winner != 'start':
        assert len(ledger) + 4 <= cap
    return winner, audit, len(ledger)


def test_ties_keep_a_strong_late_candidate_on_identical_screening_grades():
    assert run(keep_ties=False)[0] == 'start'
    winner, audit, _ = run(keep_ties=True)
    assert winner == 'p7'
    assert audit['screenLookups'] == 16


def test_exact_finalist_must_preserve_incumbent_critical_passes():
    assert run(keep_ties=True, winner_protects=False)[0] == 'start'


def test_shortlist_leaves_room_for_training_and_skips_an_unfunded_screen():
    winner, audit, reads = run(keep_ties=True, cap=10)
    assert winner == 'start'
    assert not audit
    assert reads == 6
