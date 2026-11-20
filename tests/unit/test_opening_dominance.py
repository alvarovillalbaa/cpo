"""Compare a partial dominance proof against exact adaptive opening search."""

from itertools import product

from cpo import Observation, ProposalPair, Row
from cpo.opening_dominance import certify_opening_dominance
from cpo.opening_screen_cycle import run_opening_screen_cycle


def test_dominance_proof_preserves_selection_qualification_and_budget():
    prompts = ('incumbent', 'rewrite', 'repair')
    train = (Row('train', 'a', fields=2),)
    holdout = (Row('q1', 'a', True), Row('q2', 'b'))
    pair = ProposalPair('rewrite', 'repair')
    for critical in (0, 5):
        validation = tuple(Row(str(i), 'a' if i < 2 else 'b', bool(critical & (1 << i)), 2)
                           for i in range(3))
        for values in product(range(3), repeat=9):
            outcomes = dict(zip(product(prompts, (row.id for row in validation)), values, strict=True))

            def run(certify_dominance):
                paid = []

                def evaluate(prompt, row):
                    paid.append((prompt, row.id))
                    fields = outcomes[prompt, row.id]
                    return Observation(fields == row.fields, {}, fields)

                result = run_opening_screen_cycle(
                    prompts[0], train, validation, holdout, evaluate, opening_pair=pair, metric_limit=8,
                    qualify=lambda prompt, row, _: prompt != prompts[0] or row.id == 'q1',
                    screen_rows=2, field_credit=True, qualification_limit=3, certify_opening=True,
                    certify_validation=True, certify_dominance=certify_dominance,
                )
                assert result.search.evaluations == len(paid) == len(set(paid)) <= 8
                return result

            baseline, certified = run(False), run(True)
            assert certified.search.prompt == baseline.search.prompt
            assert certified.qualification == baseline.qualification


def test_strict_dominance_leaves_a_rewrite_miss_unobserved():
    rows = tuple(Row(case, 'a', fields=2) for case in ('gain', 'unknown'))
    reads = []

    def evaluate(prompt, row):
        reads.append((prompt, row.id))
        passed = prompt == 'rewrite' and row.id == 'gain'
        return Observation(passed, {}, 2 if passed else 0)

    result = run_opening_screen_cycle(
        'old', (Row('train', 'a', fields=2),), rows, (Row('holdout', 'a'),), evaluate,
        opening_pair=ProposalPair('rewrite', 'repair'), metric_limit=6,
        qualify=lambda *_: False, screen_rows=2, field_credit=True, qualification_limit=0,
        certify_opening=True, certify_validation=True, certify_dominance=True,
    )
    assert result.search.prompt == 'rewrite'
    assert result.search.events[0]['kind'] == 'certified-opening-dominance'
    assert ('rewrite', 'unknown') not in reads


def test_field_gain_accounts_for_the_unseen_incumbent_fields():
    rows = tuple(Row(str(case), 'a', fields=4) for case in range(3))
    fields = {'old': (4, 0, 1), 'rewrite': (4, 2, 0)}
    paid = []

    def observe(prompt, row):
        paid.append((prompt, row.id))
        matched = fields[prompt][int(row.id)]
        return Observation(matched == row.fields, {}, matched)

    proof = certify_opening_dominance('old', 'rewrite', rows, observe, field_credit=True)
    assert proof['matchedFieldGainLowerBound'] == 1
    assert proof['knownPassed'] == ['0']
    assert ('rewrite', '2') not in paid
