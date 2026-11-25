from random import Random

from benchmarks.validation_routed_tail import screen
from cpo import Observation, Row
from cpo.ordered_uniform_validation import MISSES, screen as ordered_screen


PROMPTS = ('base', 'first', 'second')


def play(policy, grades, rows, *, cap=18):
    paid = set()

    def evaluate(prompt, row):
        key = prompt, row.id
        assert key not in paid
        paid.add(key)
        return Observation(grades[prompt][int(row.id)], {})

    result, scores = policy(PROMPTS[0], PROMPTS[1:], rows, evaluate, cap)
    assert result.evaluations == len(paid) <= cap
    return (result.prompt, scores), paid


def ordered(*args):
    return ordered_screen(*args, order=MISSES)


def stalled(*args):
    return screen(*args, extend_one_pass=False)


def close(*args):
    return screen(*args, extend_one_pass=True)


def test_paid_continuation_recovers_the_full_uniform_decision_after_a_stall():
    random = Random(722)
    for size in (5, 6):
        rows = tuple(Row(str(i), 'validation') for i in range(size))
        for _ in range(128):
            grades = {prompt: [bool(random.getrandbits(1)) for _ in rows] for prompt in PROMPTS}
            short, _ = play(ordered, grades, rows[:4])
            full, _ = play(ordered, grades, rows)
            stopped, _ = play(stalled, grades, rows)
            extended, _ = play(close, grades, rows)
            chosen, scores = short
            assert stopped == (full if chosen == 'base' else short)
            must_extend = scores is None or scores[1][0] - scores[0][0] == 1
            assert extended == (full if must_extend else short)


def test_perfect_incumbent_needs_no_contender_tail_replies():
    rows = tuple(Row(str(i), 'validation') for i in range(6))
    grades = {prompt: [True] * 6 for prompt in PROMPTS}
    (winner, scores), paid = play(stalled, grades, rows)
    assert (winner, scores) == ('base', None)
    assert paid == {('base', row.id) for row in rows}


def test_critical_or_unfunded_tail_keeps_original_screen():
    rows = tuple(Row(str(i), 'validation', critical=i == 5) for i in range(6))
    grades = dict(zip(PROMPTS, ([False, True] * 3, [True] * 6, [False] * 6), strict=True))
    assert play(close, grades, rows) == play(ordered, grades, rows)
    ordinary = tuple(Row(row.id, row.family) for row in rows)
    assert play(close, grades, ordinary, cap=12) == play(ordered, grades, ordinary, cap=12)
