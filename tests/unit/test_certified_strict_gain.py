from itertools import product
from unittest import TestCase

from benchmarks import certified_strict_gain as race
from cpo import Observation, Row
from cpo.settled_episode import EpisodeCycle


class StrictGainTests(TestCase):
    def test_every_three_row_panel_under_each_useful_cap(self):
        rows = tuple(Row(str(index), 'validation') for index in range(3))
        for board in product((False, True), repeat=9):
            truth = tuple(board[index:index + 3] for index in (0, 3, 6))
            for cap in (4, 7, 9):
                observed = {}

                def evaluate(prompt, row):
                    key = prompt, int(row.id)
                    self.assertNotIn(key, observed)
                    observed[key] = truth[prompt][key[1]]
                    return Observation(observed[key], {})

                result, rates = race.screen(cap, 0, (1, 2), rows, evaluate, 9, prepaid={'0'},
                                            use_validation_rates=True)
                self.assertEqual(result.evaluations, len(observed))
                self.assertLessEqual(len(observed), cap)
                self.assertIn((0, 0), observed)
                if result.finalist is not None:
                    nominee = result.finalist
                    known_passes = sum(grade for (prompt, _), grade in observed.items() if prompt == nominee)
                    known_misses = sum(not grade for (prompt, _), grade in observed.items() if prompt == 0)
                    self.assertGreater(known_passes, 3 - known_misses)
                    self.assertEqual(rates[1][0], known_passes)
                if cap == 9:
                    self.assertEqual(result.finalist is not None, max(map(sum, truth[1:])) > sum(truth[0]))

    def test_gate_can_reject_a_strict_validation_winner(self):
        validation = tuple(Row(f'v{index}', 'validation') for index in range(6))
        qualification = tuple(Row(f'q{index}', 'qualification') for index in range(4))
        cycle = EpisodeCycle(('winner', 'other'), validation, qualification, 0)
        consulted = set()

        def read(prompt, row, favorable):
            key = prompt, row.id
            self.assertNotIn(key, consulted)
            consulted.add(key)
            return prompt == favorable

        def qualify(prompt, row, repeat):
            self.assertEqual(repeat, 0)
            return read(prompt, row, 'none')

        result = race.run(10, 'base', (), (cycle,),
                          lambda prompt, row: Observation(read(prompt, row, 'winner'), {}),
                          probe=None, qualify=qualify)
        only = result.cycles[0]
        self.assertEqual(only.search.finalist, 'winner')
        self.assertEqual(only.qualification.status, 'rejected')
        self.assertEqual(result.prompt, 'base')
        self.assertEqual(result.evaluations, len(consulted))
        self.assertLessEqual(only.search.evaluations, 10)
