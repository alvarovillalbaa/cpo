import unittest

from benchmarks.task_budget_selection import CPO, REFERENCE, choose_setting, evaluate_folds, training_subjects


class TaskBudgetSelectionTests(unittest.TestCase):
    def task(self, small, large, *, maximum=100, cohort='first', benchmark='bbh', alternative_cost=9):
        return {'cohort': cohort, 'benchmark': benchmark, 'maxPasses': maximum, 'options': {
            REFERENCE: {'holdoutPasses': small, 'paidLookups': 10},
            (CPO, 36): {'holdoutPasses': large, 'paidLookups': alternative_cost},
        }}

    def test_targets_cannot_change_their_own_setting(self):
        tasks = {
            'target': self.task(15, 80),
            'other': self.task(80, 40),
            'third': self.task(75, 60),
        }
        first = evaluate_folds(tasks, 'same-benchmark', (CPO,))['folds']['target']
        tasks['target'] = self.task(99, 0, alternative_cost=40)
        second = evaluate_folds(tasks, 'same-benchmark', (CPO,))['folds']['target']
        self.assertEqual((first['method'], first['cap']), (second['method'], second['cap']))
        self.assertEqual(second['trainingSubjects'], ['other', 'third'])
        self.assertNotEqual(first['realized'], second['realized'])

    def test_heldout_cohort_removes_all_its_tasks(self):
        tasks = {'target': self.task(1, 2), 'same': self.task(1, 2),
                 'other': self.task(1, 2, cohort='second', benchmark='mmlu')}
        self.assertEqual(training_subjects(tasks, 'target', 'other-cohorts'), ('other',))
        self.assertEqual(training_subjects(tasks, 'target', 'same-benchmark'), ('same',))

    def test_training_scores_are_normalized_per_task_under_the_cost_bound(self):
        small = self.task(9, 5, maximum=10)
        large = self.task(60, 70, maximum=100)
        chosen, metrics = choose_setting([small, large], (CPO,))
        self.assertEqual(chosen, REFERENCE)
        self.assertEqual(metrics['accuracy'], '3/4')
        unaffordable = self.task(0, 99, alternative_cost=11)
        chosen, _ = choose_setting([unaffordable], (CPO,))
        self.assertEqual(chosen, REFERENCE)
