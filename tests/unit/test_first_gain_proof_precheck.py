from itertools import product
from unittest import TestCase

from benchmarks import first_gain_proof_precheck as study
from cpo import Observation, Row
from cpo.settled_episode import EpisodeCycle


class ProofPrecheckTests(TestCase):
    def test_all_four_case_boards_with_full_and_capped_prechecks(self):
        rows = tuple(Row(str(index), 'proof') for index in range(4))
        for bits in product((False, True), repeat=12):
            scores = [sum(bits[offset:offset + 4]) for offset in (0, 4, 8)]
            both_rejected = max(scores[1:]) <= scores[0]
            for allowance in (8, 12):
                observed = set()

                def observe(side, row):
                    index = 4 * side + int(row.id)
                    self.assertNotIn(index, observed)
                    observed.add(index)
                    return bits[index]

                state = study.initial_board(rows, observe, allowance=allowance, trigger=0)
                self.assertLessEqual(len(observed), allowance)
                if allowance == 12:
                    self.assertEqual(state is not None, both_rejected)
                if state is not None:
                    self.assertTrue(both_rejected)
                    self.assertLessEqual(max(study.upper_margins(4, state)), 0)

    def play(self, proofs, precheck):
        validation = tuple(Row(f'v{n}', 'validation') for n in range(6))
        qualification = tuple(Row(f'q{n}', 'proof') for n in range(4))
        cycle = EpisodeCycle(('a', 'b'), validation, qualification, 0)
        observed = set()

        def record(prompt, row):
            key = prompt, row.id
            self.assertNotIn(key, observed)
            observed.add(key)

        def evaluate(prompt, row):
            record(prompt, row)
            return Observation(prompt == 'a', {})

        def qualify(prompt, row, repeat):
            self.assertEqual(repeat, 0)
            record(prompt, row)
            return proofs[prompt][int(row.id[1:])]

        if precheck:
            result = study.run((12, 0), 'base', (), (cycle,), evaluate, probe=None, qualify=qualify)
        else:
            result = study.first_gain.run_first_gain_episode('base', (cycle,), evaluate, qualify=qualify)
        self.assertEqual(result.evaluations, len(observed))
        return result.cycles[0]

    def test_independent_admission_never_switches_the_validation_nominee(self):
        proofs = {'base': (True, False, False, False), 'a': (False,) * 4, 'b': (True,) * 4}
        before = self.play(proofs, False)
        after = self.play(proofs, True)
        self.assertEqual(before.search.finalist, 'a')
        self.assertEqual(after.search.finalist, before.search.finalist)
        self.assertEqual(after.prompt, 'base')

    def test_two_exact_rejections_avoid_the_screen(self):
        proofs = {'base': (True, True, False, False), 'a': (False,) * 4, 'b': (False,) * 4}
        before = self.play(proofs, False)
        after = self.play(proofs, True)
        self.assertEqual(after.prompt, before.prompt)
        self.assertIsNone(after.search.finalist)
        self.assertEqual(after.search.evaluations, 1)
        self.assertLess(after.search.evaluations, before.search.evaluations)
