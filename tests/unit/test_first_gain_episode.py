from dataclasses import replace
from unittest import TestCase

from cpo import Observation, Row
from cpo.full_roster_precheck.certified_nomination import run_certified_nomination_episode
from cpo.full_roster_precheck.first_gain import run_first_gain_episode
from cpo.settled_episode import EpisodeCycle


def cycle(index, *, depth=6, critical=False):
    return EpisodeCycle(
        (f'winner-{index}', f'other-{index}'),
        tuple(Row(f'v{index}-{row}', 'validation', critical=critical and row == 0) for row in range(depth)),
        tuple(Row(f'q{index}-{row}', 'qualification') for row in range(4)),
        index,
    )


class FirstGainEpisodeTests(TestCase):
    def play(self, runner, cycles, **kwargs):
        seen = []

        def record(prompt, row):
            key = prompt, row.id
            self.assertNotIn(key, seen)
            seen.append(key)
            return prompt.startswith('winner')

        result = runner('base', iter(cycles), lambda prompt, row: Observation(record(prompt, row), {}),
                        qualify=lambda prompt, row, _: record(prompt, row), **kwargs)
        self.assertEqual(result.evaluations, len(seen))
        return result, seen

    def test_default_certifies_and_the_minimum_budget_includes_the_opening(self):
        result, _ = self.play(run_first_gain_episode, (cycle(0),))
        self.assertEqual(result.prompt, 'winner-0')
        self.assertEqual(result.cycles[0].qualification.status, 'promoted')
        result, seen = self.play(run_first_gain_episode, (cycle(0),), uniform_read_limit=2)
        self.assertEqual(result.prompt, 'base')
        self.assertIsNone(result.cycles[0].search.finalist)
        self.assertLessEqual(sum(row.startswith('v') for _, row in seen), 2)

    def test_fallback_screens_keep_the_original_trace(self):
        for first in (cycle(0, depth=2), cycle(0, critical=True)):
            original = self.play(run_certified_nomination_episode, (first,))
            result = self.play(run_first_gain_episode, (first,), uniform_read_limit=2)
            self.assertEqual(result, original)

    def test_layout_and_limit_errors_precede_the_first_callback(self):
        first, second = cycle(0), cycle(1)
        invalid = replace(second, qualification=first.qualification)

        def unexpected(*args):
            self.fail('Layout or cap errors must precede evaluator callbacks')

        with self.assertRaisesRegex(ValueError, 'disjoint'):
            run_first_gain_episode('base', (first, invalid), unexpected, qualify=unexpected)
        for value in (True, 1, 19, 3.0):
            with self.assertRaisesRegex(ValueError, 'uniform_read_limit'):
                run_first_gain_episode('base', (first,), unexpected, qualify=unexpected, uniform_read_limit=value)

    def test_nested_episode_uses_its_own_limit(self):
        first = cycle(0)
        nested = []

        def evaluate(prompt, row):
            if not nested:
                nested.append(self.play(run_first_gain_episode, (first,), uniform_read_limit=2)[0])
            return Observation(prompt.startswith('winner'), {})

        result = run_first_gain_episode('base', (first,), evaluate,
                                        qualify=lambda prompt, row, _: prompt.startswith('winner'))
        self.assertEqual(nested[0].prompt, 'base')
        self.assertEqual(result.prompt, 'winner-0')
