import unittest

from benchmarks.recorded_outage_witness import reserve_witness, selected_prompt, witness_bounds


class OutageWitnessTests(unittest.TestCase):
    def test_reserves_target_stratum_and_selects_first_incumbent_pass(self):
        rows = [{'id': case, 'critical': True, 'input': f'Record {case}. Duration minutes={minutes}; '
                 f'Plan=PLUS; Monthly fee whole USD=55; Evidence={evidence}.'}
                for case, minutes, evidence in [('c', 122, 'MISSING'), ('a', 120, 'MISSING'),
                                                ('d', 119, 'MISSING'), ('b', 120, 'POSTED')]]
        incumbent = {'a': (False, 2), 'c': (True, 3)}
        self.assertEqual(reserve_witness(rows, incumbent), (['a', 'c'], 'c', 2))

    def test_missing_reply_cannot_be_treated_as_a_pass_or_failure(self):
        with self.assertRaises(KeyError):
            selected_prompt('candidate', 'incumbent', True, {})
        self.assertEqual(selected_prompt('candidate', 'incumbent', False, {}), 'candidate')

    def test_unknown_reply_is_shared_across_methods_in_the_bounds(self):
        arms = dict.fromkeys(('cpo', 'gepa-sequential', 'gepa-batched'),
                            {'chosen': 'new', 'calls': 2, 'witnessRequired': True})
        trials = [{'holdout': ('critical',), 'arms': arms}] * 2
        matrix = {'old': {'critical': (False, 2)}, 'new': {'critical': (True, 3)}}
        result = witness_bounds(trials, 'old', {}, matrix, {'critical'}, ['new'])
        self.assertEqual(result['candidateMetrics']['cpo'], {'passes': [0, 2], 'calls': [6, 6], 'promotions': [0, 2]})
        self.assertEqual(result['matchedCriticalLosses']['gepa-sequential'], [0, 0])
        self.assertEqual(result['pairedPassDelta']['gepa-sequential'], [0, 0])
