from types import SimpleNamespace
import unittest

from benchmarks.episode_screen_adaptation import DEFERRED, WIDE, ScreenSchedule, paired_deltas


def observed(finalist=None, promoted=False):
    return SimpleNamespace(search=SimpleNamespace(finalist=finalist), promoted=promoted)


class EpisodeScreenAdaptationTests(unittest.TestCase):
    def test_evidence_comes_from_an_earlier_cycle_on_the_same_incumbent(self):
        schedule = ScreenSchedule('after-empty')
        self.assertEqual(schedule.choose('a'), DEFERRED)
        schedule.observe(observed())
        self.assertEqual(schedule.choose('b'), DEFERRED)
        schedule.observe(observed())
        self.assertEqual(schedule.choose('b'), WIDE)
        schedule.observe(observed('c', True))
        self.assertEqual(schedule.wide_promotions, 1)
        self.assertEqual(schedule.choose('c'), DEFERRED)

    def test_unpromoted_and_empty_streaks_are_distinct(self):
        empty = ScreenSchedule('once-after-two-empty')
        unpromoted = ScreenSchedule('once-after-two-unpromoted')
        for schedule in (empty, unpromoted):
            for finalist in (None, 'b'):
                self.assertEqual(schedule.choose('a'), DEFERRED)
                schedule.observe(observed(finalist))
        self.assertEqual(empty.choose('a'), DEFERRED)
        self.assertEqual(unpromoted.choose('a'), WIDE)

    def test_one_wide_screen_applies_to_the_whole_episode(self):
        schedule = ScreenSchedule('once-after-two-empty')
        for incumbent, expected in [('a', DEFERRED), ('a', DEFERRED), ('a', WIDE),
                                    ('b', DEFERRED), ('b', DEFERRED), ('b', DEFERRED)]:
            self.assertEqual(schedule.choose(incumbent), expected)
            schedule.observe(observed())

    def test_paired_deltas_keep_episode_alignment(self):
        self.assertEqual(paired_deltas([4, 2, 5, 1], [3, 2, 6, 2]), {'gains': 1, 'ties': 1, 'losses': 2})
