from itertools import product
import unittest

from cpo import Row
from cpo.paired_qualification import QualificationObservation, certify_paired_qualification
from cpo.qualification_precheck import run_prechecked_qualification


class QualificationPrecheckTests(unittest.TestCase):
    def test_exact_with_repeats_critical_cases_and_families(self):
        rows = (Row('critical', 'one', True), Row('regular', 'one'), Row('other', 'two'))
        keys = [(prompt, row.id, repeat) for prompt in ('old', 'new') for row in rows for repeat in range(2)]
        for bits in product((False, True), repeat=len(keys)):
            matrix = dict(zip(keys, bits, strict=True))
            for minimum_gain in (1, 2, 6):
                paid, nominations = {}, []

                def qualify(prompt, row, repeat):
                    return matrix[prompt, row.id, repeat]

                def observe(prompt, row, repeat):
                    key = (prompt, row.id, repeat)
                    self.assertNotIn(key, paid)
                    reply = qualify(prompt, row, repeat)
                    paid[key] = reply
                    return reply

                def nominate():
                    nominations.append('new')
                    return 'new'

                old = certify_paired_qualification('old', 'new', rows, qualify, repeats=2,
                                                    minimum_gain=minimum_gain, seed=7)
                new = run_prechecked_qualification('old', rows, nominate, observe, repeats=2,
                                                    minimum_gain=minimum_gain, seed=7, evaluation_limit=12)
                self.assertEqual((new.decision.status, new.prompt), (old.status, old.prompt))
                exact = sum(bits[6:]) - sum(bits[:6])
                self.assertLessEqual(new.decision.lower_gain, exact)
                self.assertGreaterEqual(new.decision.upper_gain, exact)
                self.assertEqual(new.decision.observations,
                                 tuple(QualificationObservation(*key, passed) for key, passed in paid.items()))
                self.assertLessEqual(new.qualification_evaluations, 12)
                if new.nominee is None:
                    self.assertFalse(nominations)
                    self.assertLess(new.decision.upper_gain, minimum_gain)
                    self.assertEqual(new.precheck_evaluations, len(paid))
                else:
                    self.assertEqual(nominations, ['new'])

    def test_tight_caps_keep_ordinary_dispatch_order(self):
        rows = (Row('one', 'task'), Row('two', 'task'))
        for cap in range(4):
            expected = certify_paired_qualification('old', 'new', rows, lambda p, *_: p == 'new',
                                                      seed=3, evaluation_limit=cap)
            actual = run_prechecked_qualification('old', rows, lambda: 'new', lambda p, *_: p == 'new',
                                                    seed=3, evaluation_limit=cap)
            self.assertEqual(actual.decision, expected)
            self.assertEqual(actual.precheck_evaluations, 0)

    def test_retained_nominee_accounts_for_prepaid_miss(self):
        rows = (Row('one', 'task'), Row('two', 'task'))
        actual = run_prechecked_qualification('old', rows, lambda: 'old', lambda *_: False)
        self.assertEqual(actual.nominee, 'old')
        self.assertEqual(actual.decision.status, 'rejected')
        self.assertEqual(actual.decision.observations, (QualificationObservation('old', 'one', 0, False),))
        self.assertEqual(actual.qualification_evaluations, 1)

    def test_impossible_and_invalid_inputs_spend_zero(self):
        row = Row('one', 'task')

        def unexpected(*_):
            self.fail('Invalid or impossible setup dispatched a callback')

        result = run_prechecked_qualification('old', [row], unexpected, unexpected, minimum_gain=2)
        self.assertIsNone(result.nominee)
        self.assertEqual(result.decision.upper_gain, 1)
        self.assertEqual(result.qualification_evaluations, 0)
        for rows, options in (([row, row], {}), ([row], {'repeats': 0}), ([row], {'evaluation_limit': -1})):
            with self.assertRaises(ValueError):
                run_prechecked_qualification('old', rows, unexpected, unexpected, **options)

    def test_invalid_outcome_cannot_enter_search(self):
        with self.assertRaisesRegex(ValueError, 'exact boolean'):
            run_prechecked_qualification('old', [Row('one', 'task')], lambda: self.fail('Search ran'),
                                         lambda *_: 1)
