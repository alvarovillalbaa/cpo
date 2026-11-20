"""T2 checks of the fixed-reply opening certificate against ordinary search."""

from itertools import product

from cpo import Observation, ProposalPair, Row, search
from cpo.opening_certificate import search_with_opening_certificate


def test_certificate_matches_ordinary_search_and_never_adds_a_read():
    train = [Row('t', 'a', fields=2)]
    prompts = ('incumbent', 'rewrite', 'repair')
    for critical, bits, budget in product((0, 1, 3, 7), range(512), (5, 6, 12)):
        rows = [Row(str(i), 'a' if i < 2 else 'b', bool(critical & (1 << i)), 2) for i in range(3)]
        cases = {prompt: {row.id: bool(bits & (1 << (idx * len(rows) + offset)))
                          for offset, row in enumerate(rows)} for idx, prompt in enumerate(prompts)}
        results = []
        for run in (search, search_with_opening_certificate):
            paid = []

            def observe(prompt, row):
                paid.append((prompt, row.id))
                passed = cases[prompt].get(row.id, False)
                return Observation(passed, {}, 2 if passed else int(row.id == '1'))

            result = run(prompts[0], train, rows, observe, lambda *_: (), opening_pair=ProposalPair(*prompts[1:]),
                         metric_limit=budget, rounds=2, train_per_round=1, adaptive=True, field_credit=True)
            assert result.evaluations == len(paid) == len(set(paid)) <= budget
            results.append((result, set(paid)))
        reference, certificate = results
        assert certificate[0].prompt == reference[0].prompt
        assert certificate[0].reflections == reference[0].reflections
        assert certificate[1] <= reference[1]


def test_perfect_rewrite_skips_incumbent_suffix_and_preserves_critical_row():
    validation = [Row('critical', 'a', True), Row('miss', 'a'), Row('late', 'b')]
    calls = []

    def evaluate(prompt, row):
        calls.append((prompt, row.id))
        return Observation(prompt == 'rewrite' or row.id == 'critical', {})

    result = search_with_opening_certificate(
        'old', [Row('train', 'a')], validation, evaluate, lambda *_: (),
        opening_pair=ProposalPair('rewrite', 'repair'), metric_limit=6, rounds=1, train_per_round=1,
    )
    assert result.prompt == 'rewrite'
    assert result.evaluations == 5
    assert ('old', 'late') not in calls
    assert result.events[-1]['incumbentMiss'] == 'miss'
