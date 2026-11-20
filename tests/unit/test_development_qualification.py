import unittest

from cpo.development_qualification import Sample, run_development_qualification


ARMS = ('cpo', 'initial', 'gepa')
GATE = {'minimumPassesPerTask': 1, 'minimumAddedPasses': 1, 'maxSearchCostPercentForEfficiency': 90}


class DevelopmentQualificationTests(unittest.TestCase):
    def test_stops_before_a_second_paid_request_when_floor_is_unattainable(self):
        schedule = (Sample('task', 'a', 0, True, ('cpo',)), Sample('task', 'a', 0, True, ('initial', 'gepa')))
        dispatched = []

        def observe(sample):
            dispatched.append(sample)
            return False

        result = run_development_qualification(schedule, observe, gate=GATE, search_costs={'cpo': 100, 'gepa': 100})
        self.assertEqual(dispatched, list(schedule[:1]))
        self.assertEqual(result.observations, (False,))
        self.assertEqual(result.status, 'rejected')
        self.assertIn({'gate': 'task-floor', 'task': 'task', 'maximumPasses': 0, 'requiredPasses': 1}, result.reasons)

    def test_full_qualification_keeps_both_shared_replies(self):
        schedule = tuple(Sample('task', 'a', n, False, ARMS) for n in range(2))
        result = run_development_qualification(schedule, lambda sample: sample.repeat == 0,
                                               gate=GATE, search_costs={'cpo': 90, 'gepa': 100})
        self.assertEqual(result.status, 'qualified')
        self.assertEqual(result.observations, (True, False))
        self.assertEqual(result.reasons, ())

    def test_structurally_impossible_panel_uses_zero_calls(self):
        sample = Sample('task', 'a', 0, True, ARMS)
        result = run_development_qualification([sample], lambda _: self.fail('Structure already prevents a gain'),
                                               gate=GATE, search_costs={'cpo': 100, 'gepa': 100})
        self.assertEqual(result.status, 'rejected')
        self.assertEqual(result.observations, ())
        self.assertEqual(result.reasons, ({'gate': 'quality-or-efficiency', 'arm': 'gepa', 'maximumAddedPasses': 0},))

    def test_invalid_sample_matrix_fails_before_dispatch(self):
        row = Sample('task', 'a', 0, False, ARMS)
        for schedule in ((row, row), (Sample('task', 'a', 1, False, ARMS),),
                         (row, Sample('task', 'a', 1, True, ARMS)), (Sample('task', 'a', 0, False, ('cpo',)),)):
            with self.assertRaises(ValueError):
                run_development_qualification(schedule, lambda _: self.fail('Invalid schedule dispatched'),
                                              gate=GATE, search_costs={'cpo': 90, 'gepa': 100})

    def test_accepts_only_exact_boolean_outcomes(self):
        with self.assertRaisesRegex(ValueError, 'exact boolean'):
            run_development_qualification([Sample('task', 'a', 0, True, ARMS)], lambda _: 1,
                                          gate=GATE, search_costs={'cpo': 90, 'gepa': 100})
