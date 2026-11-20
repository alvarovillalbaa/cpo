"""Compare certified promotion with full validation on fixed replies."""

from itertools import product

from cpo import Observation, ProposalPair, Row
from cpo.opening_screen_cycle import run_opening_screen_cycle


def test_opening_validation_certificate_matches_full_reads_and_qualification():
    prompts = ('incumbent', 'rewrite', 'repair')
    train = (Row('train', 'a', fields=2),)
    holdout = (Row('q1', 'a', True), Row('q2', 'b'))
    for critical, matrix, budget in product((0, 1, 6, 7), range(512), (6, 8)):
        validation = tuple(Row(str(i), 'a' if i < 2 else 'b', bool(critical & (1 << i)), 2)
                           for i in range(3))
        outcomes = {(prompt, row.id): bool(matrix & (1 << (offset + 3 * slot)))
                    for slot, prompt in enumerate(prompts) for offset, row in enumerate(validation)}

        def run(certify_validation):
            paid = []

            def evaluate(prompt, row):
                paid.append((prompt, row.id))
                passed = outcomes[prompt, row.id]
                return Observation(passed, {}, 2 if passed else int(row.id == '1'))

            result = run_opening_screen_cycle(
                prompts[0], train, validation, holdout, evaluate, opening_pair=ProposalPair(*prompts[1:]),
                metric_limit=budget, qualify=lambda prompt, row, _: prompt != 'incumbent' or row.id == 'q1',
                screen_rows=2, field_credit=True, qualification_limit=3, certify_opening=True,
                certify_validation=certify_validation,
            )
            assert result.search.evaluations == len(paid) == len(set(paid)) <= budget
            return result, set(paid)

        full, full_calls = run(False)
        certified, certified_calls = run(True)
        assert certified.search.prompt == full.search.prompt
        assert certified.qualification == full.qualification
        assert certified_calls <= full_calls


def test_validation_certificate_skips_remaining_pairs_once_rejected():
    rows = (Row('screen', 'a'), Row('critical', 'b', True), Row('unneeded', 'a'))
    calls = []
    passes = {
        'incumbent': {'critical'}, 'rewrite': {'screen'}, 'repair': set(),
    }

    def evaluate(prompt, row):
        calls.append((prompt, row.id))
        return Observation(row.id in passes[prompt], {})

    result = run_opening_screen_cycle(
        'incumbent', (Row('train', 'a'),), rows, (Row('holdout', 'a'),), evaluate,
        opening_pair=ProposalPair('rewrite', 'repair'), metric_limit=6, qualify=lambda *_: False,
        screen_rows=1, qualification_limit=0, certify_opening=True, certify_validation=True,
    )
    assert result.search.prompt == 'incumbent'
    assert result.search.events[-1]['kind'] == 'certified-validation-gate'
    assert result.qualification is None
    assert all(case != 'unneeded' for _, case in calls)
