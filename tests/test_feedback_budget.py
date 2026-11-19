import json
import unittest

from benchmarks import feedback_budget, grounded, typed_policy


class ObservedRepairTests(unittest.TestCase):
    def test_repair_uses_only_an_observed_training_error(self):
        training = typed_policy.cohorts()['outage']['train']
        sample = training[0]
        actual = {**sample['expected'], 'reason': 'DEFAULT'}
        request = {'task': 'outage', 'input': {'current': grounded.BASELINE, 'labeledTraining': training,
                   'recentFeedback': [{'id': sample['id'], 'observed': json.dumps(actual)}]}}

        proposal = json.loads(feedback_budget.observed_repair(request))
        self.assertEqual(json.loads(proposal['instruction'])['fields'], ['reason'])
        request['input']['recentFeedback'][0]['observed'] = json.dumps(sample['expected'])
        self.assertEqual(json.loads(feedback_budget.observed_repair(request))['instruction'], grounded.BASELINE)

    def test_validation_feedback_is_rejected(self):
        cohorts = typed_policy.cohorts()['ticket']
        sample = cohorts['validation'][0]
        request = {'task': 'ticket', 'input': {'current': grounded.BASELINE, 'labeledTraining': cohorts['train'],
                   'recentFeedback': {'current_candidate': [
                       {'id': sample['id'], 'observed': json.dumps(sample['expected'])}
                   ]}}}
        with self.assertRaisesRegex(ValueError, 'training cohort'):
            feedback_budget.observed_repair(request)


if __name__ == '__main__':
    unittest.main()
