from functools import partial
from itertools import product

from benchmarks.validation_routed_nominee_certificate import screen
from cpo import Observation, Row
from cpo.ordered_uniform_validation import MISSES, screen as original_screen
from cpo.two_sided_certificate_cycle import _run


PROMPTS = ('base', 'first', 'second')


def test_every_four_case_panel_preserves_the_exact_ordered_nominee():
    rows = tuple(Row(str(i), 'validation') for i in range(4))
    for panel in product((False, True), repeat=12):
        grades = dict(zip(product(PROMPTS, rows), panel, strict=True))
        total = [sum(grades[prompt, row] for row in rows) for prompt in PROMPTS]
        index = max(range(3), key=total.__getitem__)
        prefix = rows[:2] if grades['base', rows[0]] else rows[:1]
        paid = {}

        def evaluate(prompt, row):
            assert (prompt, row) not in paid
            paid[prompt, row] = grades[prompt, row]
            return Observation(paid[prompt, row], {})

        result, counts = screen(PROMPTS[0], PROMPTS[1:], rows, evaluate, 12,
                                prepaid={row.id for row in prefix}, use_rates=True)
        assert tuple(paid)[:len(prefix)] == tuple(('base', row) for row in prefix)
        assert result.evaluations == len(paid) <= 12
        assert result.prompt == PROMPTS[index]
        assert result.finalist == (PROMPTS[index] if index else None)
        if index:
            for prompt, count in zip(('base', result.finalist), counts, strict=True):
                replies = [grade for (name, _), grade in paid.items() if name == prompt]
                assert count == (sum(replies), len(replies))


def test_partial_and_neutral_rates_preserve_the_independent_proof_decision():
    validation = tuple(Row(f'v{index}', 'validation') for index in range(6))
    qualification = tuple(Row(f'q{index}', 'qualification') for index in range(4))
    grades = dict(zip(PROMPTS, ((False,) * 6, (True,) * 6, (False,) * 6), strict=True))

    def evaluate(prompt, row):
        return Observation(grades[prompt][int(row.id[1:])], {})

    screens = (partial(original_screen, order=MISSES),
               *(partial(screen, prepaid={'v0'}, use_rates=mode) for mode in (True, False)))
    for panel in product((False, True), repeat=8):
        proof = dict(zip(product(PROMPTS[:2], qualification), panel, strict=True))
        chosen = 'first' if sum(panel[4:]) > sum(panel[:4]) else 'base'
        for race in screens:
            paid = set()

            def qualify(prompt, row, repeat):
                assert repeat == 0 and (prompt, row) not in paid
                paid.add((prompt, row))
                return proof[prompt, row]

            result = _run('base', PROMPTS[1:], validation, qualification, evaluate,
                          metric_limit=18, qualify=qualify, screen=race)
            assert result.prompt == chosen
            assert result.qualification_evaluations == len(paid) <= 8
