import unittest

from cpo import Observation, Row
from cpo.single_finalist import select_single_finalist


class SingleFinalistTests(unittest.TestCase):
    def test_gain_first_can_nominate_the_candidate_that_improves_exact_score(self):
        rows = tuple(Row(case, 'task') for case in ('old-point', 'gain', 'second-gain'))
        passed = {'old': {'old-point'}, 'first': {'old-point'}, 'later': {'gain', 'second-gain'}}

        def evaluate(prompt, row):
            return Observation(row.id in passed[prompt], {})

        prefix = select_single_finalist('old', ('first', 'later'), rows, evaluate, metric_limit=7)
        gain = select_single_finalist('old', ('first', 'later'), rows, evaluate, metric_limit=7, screen='gain-first')
        self.assertEqual((prefix.prompt, prefix.finalist), ('old', 'first'))
        self.assertEqual((gain.prompt, gain.finalist), ('later', 'later'))

    def test_tie_probe_never_consumes_the_finalist_reserve(self):
        rows = tuple(Row(case, 'task') for case in ('screen', 'next', 'last'))
        calls = []

        def evaluate(prompt, row):
            calls.append((prompt, row.id))
            return Observation(prompt != 'old', {})

        result = select_single_finalist('old', ('first', 'second', 'third'), rows, evaluate, metric_limit=8)
        self.assertEqual((result.prompt, result.evaluations), ('first', 6))
        self.assertNotIn(('second', 'next'), calls)
        self.assertEqual(len(set(calls)), result.evaluations)

    def test_a_finalist_needs_to_preserve_critical_incumbent_passes(self):
        rows = (Row('protected', 'policy', True), Row('miss', 'policy'), Row('another', 'policy'))
        outcome = select_single_finalist('old', ('candidate',), rows,
                                         lambda prompt, row: Observation((prompt == 'old') == row.critical, {}),
                                         metric_limit=7, screen='gain-first')
        self.assertEqual((outcome.prompt, outcome.finalist), ('old', 'candidate'))

    def test_first_gain_does_not_screen_later_candidates(self):
        rows = (Row('miss', 'task'), Row('other', 'task'))
        paid = []

        def evaluate(prompt, row):
            paid.append((prompt, row.id))
            return Observation(prompt == 'winner', {})

        result = select_single_finalist('old', ('rejected', 'winner', 'not-called'), rows, evaluate,
                                        metric_limit=6, screen='first-gain')
        self.assertEqual((result.prompt, result.evaluations), ('winner', 4))
        self.assertNotIn(('not-called', 'miss'), paid)
