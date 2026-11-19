import unittest

from benchmarks.qualification_repeat_sensitivity import ObservedRow, qualification_slots


class QualificationRepeatSensitivityTests(unittest.TestCase):
    def test_repetition_changes_case_coverage_at_the_same_slot_ceiling(self):
        cases = (1, 3, 4, 8, 11, 15, 16, 20)
        width = 25
        single = qualification_slots(cases, width, 'eight-cases')
        repeats = qualification_slots(cases, width, 'four-repeated')
        self.assertEqual(single, list(cases))
        self.assertEqual(len(repeats), len(single))
        self.assertEqual(len(set(repeats)), len(repeats))
        self.assertEqual([divmod(slot, width) for slot in repeats],
                         [(repeat, case) for case in cases[:4] for repeat in (0, 1)])

    def test_flips_are_stable_and_confined_to_the_qualification_cases(self):
        row = '10100101'
        mask = {1, 2, 4, 6}
        forced = ObservedRow(row, len(row), mask, 'fixed', 100)
        clean = ObservedRow(row, len(row), mask, 'fixed', 0)
        for case, archived in enumerate(row):
            self.assertEqual(clean[case], archived)
            if case in mask:
                self.assertNotEqual(forced[case], archived)
                self.assertEqual(forced[case + len(row)], forced[case])
            else:
                self.assertEqual(forced[case], archived)
                with self.assertRaises(IndexError):
                    forced[case + len(row)]
        noisy = ObservedRow(row, len(row), mask, 'fixed', 50)
        slots = [case + len(row) * repeat for case in sorted(mask) for repeat in (0, 1)]
        first = [noisy[slot] for slot in slots]
        self.assertEqual(first, list(reversed([noisy[slot] for slot in reversed(slots)])))
        self.assertTrue(any(a != b for a, b in zip(first[::2], first[1::2], strict=True)))
