import unittest

from benchmarks.routed_paid_qualification import PaidQualification


class PaidQualificationTests(unittest.TestCase):
    def check(self, evidence, passed, *, count=3, promoted=False):
        cases = tuple(range(len(passed)))
        paid = []

        def evaluate(prompt, case):
            paid.append((prompt, case))
            return passed[case]

        def profile(incumbent, challenger, cohort, observe):
            for case in cohort[:count]:
                observe(incumbent, case)
            return promoted, 0, ()

        evidence.check(profile, 'old', 'new', cases, evaluate)
        self.assertEqual(paid, [('old', case) for case in cases[:count]])

    def test_terminal_requires_paid_perfect_incumbent_and_final_cycle(self):
        evidence = PaidQualification('terminal', cycles=4)
        evidence.begin([None, None])
        self.check(evidence, (True, True, True))
        self.assertFalse(evidence.skip())
        evidence.begin([None] * 3)
        self.assertFalse(evidence.skip())
        self.check(evidence, (True, True, True))
        self.assertTrue(evidence.skip())
        self.assertEqual(evidence.audit['skippedBeforeFinal'], 0)

    def test_unknown_miss_and_archived_promotion_do_not_skip_search(self):
        evidence = PaidQualification('all-cycles', cycles=4)
        for passed, count, promoted in (((True, True, True), 2, False), ((True, False, True), 3, False),
                                        ((True, True, True), 3, True)):
            evidence.begin([])
            self.check(evidence, passed, count=count, promoted=promoted)
            self.assertFalse(evidence.skip())

    def test_all_cycles_can_skip_earlier_search(self):
        evidence = PaidQualification('all-cycles', cycles=4)
        evidence.begin([None])
        self.check(evidence, (True, True, True))
        self.assertTrue(evidence.skip())
        self.assertEqual(evidence.audit['skippedBeforeFinal'], 1)
