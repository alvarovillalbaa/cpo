from unittest import TestCase

from benchmarks import first_gain_regime_confirmation as study


class RegimeConfirmationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.panel, cls.development = study.prepare()

    def costs(self):
        return {tally: {self.plan['candidate']: 90, **dict.fromkeys(self.plan['controls'], 100)}
                for tally in study.TALLIES}

    def test_every_regime_is_covered_and_exact_inputs_stay_disjoint(self):
        self.assertEqual(self.plan['generationRequestCeiling'], 576)
        self.assertEqual(self.plan['casesByTask'], {'ticket': 8, 'warehouse': 24, 'outage': 16})
        for task, rows in self.panel.items():
            self.assertEqual([study.coverage.regime(task, row) for row in rows],
                             list(study.coverage.REGIMES[task]))
            previous = {row['input'] for panel in self.development[task].values() for row in panel}
            self.assertTrue(previous.isdisjoint(row['input'] for row in rows))

    def test_shared_persistent_error_fails_the_absolute_check(self):
        plan, panel = self.plan, self.panel
        task = 'warehouse'
        branch = study.coverage.REGIMES[task][0]
        outcomes = study.scripted(plan, panel, target=task, branch=branch, failed_repeats=2)
        verdict = study.evaluate(plan, panel, outcomes, self.costs())
        self.assertTrue(verdict['pairedGateMet'])
        self.assertTrue(verdict['perTaskFloorMet'])
        self.assertEqual(verdict['failedRegimeCases'][task], [panel[task][0]['id']])
        self.assertFalse(verdict['qualified'])

    def test_a_single_shared_failure_leaves_one_exact_repeat(self):
        plan, panel = self.plan, self.panel
        outcomes = study.scripted(plan, panel, target='outage', branch=study.coverage.REGIMES['outage'][0],
                                  failed_repeats=1)
        self.assertTrue(study.evaluate(plan, panel, outcomes, self.costs())['qualified'])

    def test_refuses_a_missing_or_nonboolean_grade(self):
        plan, panel = self.plan, self.panel
        key = panel['ticket'][0]['id'], 0
        outcomes = study.scripted(plan, panel)
        outcomes['ticket'].pop(key)
        with self.assertRaisesRegex(ValueError, 'all paired cases'):
            study.evaluate(plan, panel, outcomes, self.costs())
        outcomes = study.scripted(plan, panel)
        outcomes['ticket'][key][plan['candidate']] = 1
        with self.assertRaisesRegex(ValueError, 'Boolean scores'):
            study.evaluate(plan, panel, outcomes, self.costs())

    def test_efficiency_must_hold_on_both_development_tallies(self):
        plan, panel = self.plan, self.panel
        costs = self.costs()
        costs['attributedSearchRequests'][plan['candidate']] = 91
        result = study.evaluate(plan, panel, study.scripted(plan, panel), costs)
        self.assertTrue(result['pairedByTally']['logicalSearchUses']['qualified'])
        self.assertFalse(result['pairedByTally']['attributedSearchRequests']['qualified'])
        self.assertFalse(result['qualified'])
