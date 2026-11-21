from unittest.mock import patch

from benchmarks import witness_mmlu_gap as gap


def test_budget_neutral_menu_checks_proof_before_reading_holdout():
    layouts = ({'qualify': [0, 1], 'alternatives': ('paid', 'too-expensive'), 'seed': 0},
               {'qualify': [2, 3], 'alternatives': ('unread', 'rejected'), 'seed': 1})
    paid = {('start', 90): False, ('paid', 90): True, ('too-expensive', 91): True}
    decision = gap.Decision('start', 'witness-rejected', 15, 4, paid)
    observed = []

    def qualify(incumbent, challenger, current, bank, touched, evaluate, **options):
        assert incumbent == 'start' and not touched
        assert bank == ([] if options['seed'] == 0 else [0, 1])
        evaluate(challenger, current[0])
        bank.append(99)
        return (incumbent if challenger == 'rejected' else challenger, (),
                {'qualificationLookups': 5 if challenger == 'too-expensive' else 4})

    def score(prompt):
        observed.append(prompt)
        return {'start': 5, 'paid': 7, 'unread': 9}[prompt]

    with patch.object(gap.REPLAY, 'qualify', qualify):
        result = gap.price_options(decision, 'start', layouts, {}, 'retire-assigned',
                                   lambda p, c: 0 <= c < 4, score)
    assert result == {'retention': 0, 'paid-paired-win': 2, 'already-read': 2, 'whole-roster': 4}
    assert set(observed) == {'start', 'paid', 'unread'}


def test_no_settled_proof_supplies_no_new_admission_budget():
    decision = gap.Decision('start', 'fallback-capped', 16, 0, {})
    with patch.object(gap.REPLAY, 'qualify', side_effect=AssertionError('Unexpected proof')):
        result = gap.price_options(decision, 'start', (), {}, 'retire-assigned', None, lambda _: 3)
    assert result == dict.fromkeys(gap.MENUS, 0)
    assert gap.attribute('native', 'start', decision) == 'native-promoted-after-fallback-capped'


def test_paid_paired_win_requires_both_exact_grades_on_one_case():
    observed = {('start', 1): False, ('start', 2): True, ('other', 1): True, ('challenger', 2): True}
    assert gap.paired_win(observed, 'start', 'other')
    assert not gap.paired_win(observed, 'start', 'challenger')
