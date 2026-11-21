"""Check the proof funding bound against all completions of a small paired panel."""

from collections import Counter
from itertools import combinations, product

from benchmarks.recorded_paired_opening_affordability import minimum_reads, search
from cpo import Observation, ProposalPair, Row


ROWS = (Row('a', 'first', True), Row('b', 'first'), Row('c', 'second'))
SIDES = ('old', 'new')
CELLS = tuple((prompt, row.id) for prompt in SIDES for row in ROWS)


def accepts(full):
    gains = Counter()
    for row in ROWS:
        old, new = (full[prompt, row.id] for prompt in SIDES)
        if row.critical and old and not new:
            return False
        gains[row.family] += new - old
    return sum(gains.values()) >= 1 and min(gains.values()) >= 0


def test_the_minimum_matches_exhaustive_completion_and_purchase():
    for grades in product((None, False, True), repeat=len(CELLS)):
        known = {key: grade for key, grade in zip(CELLS, grades, strict=True) if grade is not None}
        unknown = [key for key in CELLS if key not in known]
        completions = [dict(zip(unknown, tail, strict=True)) for tail in product((False, True), repeat=len(unknown))]
        sufficient = None
        for count in range(len(unknown) + 1):
            if any(all(accepts({**known, **rest}) for rest in completions
                       if all(rest[key] == outcome for key, outcome in zip(purchase, paid, strict=True)))
                   for purchase in combinations(unknown, count) for paid in product((False, True), repeat=count)):
                sufficient = count
                break
        assert minimum_reads(ROWS, *SIDES, known) == sufficient


def test_unaffordable_proofs_stop_without_changing_the_blind_budgeted_nominee():
    prompts = ('old', 'rewrite', 'repair')
    cells = [(prompt, row.id) for prompt in prompts for row in ROWS]
    saved = unlocked = 0
    for grades, cap in product(product((False, True), repeat=len(cells)), (6, 7, 8)):
        matrix = dict(zip(cells, grades, strict=True))
        outcomes = []
        for policy in ('reserve', 'spend-remainder', 'minimum-reads'):
            ledger = {}

            def evaluate(prompt, row):
                key = prompt, row.id
                assert key not in ledger and len(ledger) < cap
                ledger[key] = matrix[key]
                return Observation(ledger[key], {})

            result = search(prompts[0], ProposalPair(*prompts[1:]), ROWS, evaluate, cap, 17, policy, Counter())
            assert result.evaluations == len(ledger)
            if result.prompt != 'old':
                translated = {('new' if prompt == result.prompt else prompt, row): grade
                              for (prompt, row), grade in ledger.items()}
                assert minimum_reads(ROWS, *SIDES, translated) == 0
            outcomes.append(result)
        reserve, blind, bounded = outcomes
        assert blind.prompt == bounded.prompt and bounded.evaluations <= blind.evaluations
        saved += bounded.evaluations < blind.evaluations
        unlocked += bounded.prompt == 'repair' and reserve.prompt == 'old'
    assert saved > 0 and unlocked > 0
