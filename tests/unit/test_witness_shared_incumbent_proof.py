from itertools import product

from benchmarks import witness_admission_retry as retry, witness_shared_incumbent_proof as shared


def test_full_charge_matches_the_existing_capped_proof_on_same_cases():
    base, reserve = (1, 2), (3,)
    keys = tuple(product(('old', 'backup'), (*base, *reserve)))
    for votes in product((False, True), repeat=len(keys)):
        grades = dict(zip(keys, votes, strict=True))

        def grade(prompt, case):
            return grades[prompt, case]

        for cap in range(len(keys) + 1):
            original = retry.scalar_proof('old', 'backup', base, reserve, grade, {}, 1, cap)
            assert shared.prove('old', 'backup', base, reserve, grade, {}, 1, cap, {}) == (
                original.prompt, len(original.observations), 0, original.status)


def test_only_cached_incumbent_replies_are_free():
    calls = []

    def grade(prompt, case):
        calls.append((prompt, case))
        return prompt == 'backup'

    result = shared.prove('old', 'backup', (1, 2), (), grade, {}, 1, 2, {1: False, 2: False})

    assert result[0] == 'backup'
    assert result[1] == len(calls)
    assert result[2] > 0
    assert result[3] == 'promoted'
    assert all(prompt == 'backup' for prompt, _ in calls)


def test_cache_cannot_spend_past_the_paid_limit():
    def grade(_prompt, _case):
        raise AssertionError('The exhausted allowance cannot purchase a grade')

    prompt, paid, _, status = shared.prove('old', 'backup', (1, 2), (3,), grade, {}, 1, 0, {1: False})

    assert (prompt, paid, status) == ('old', 0, 'undecided')
