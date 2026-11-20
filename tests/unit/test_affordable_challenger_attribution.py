from unittest import TestCase

from benchmarks import affordable_challenger_attribution as audit


class AffordableChallengerAttributionTests(TestCase):
    layout = {'validation': [0, 1], 'qualify': [2, 3, 4, 5]}
    matrix = ['000000', '101010', '111111']

    def classify(self, paid=None, prior=None, *, mode='deferred', incumbent='0', position=0,
                 archive=False, deployed=False):
        step = {'incumbent': incumbent, 'selected': incumbent, 'challenger': incumbent, 'archivePromoted': archive}
        return audit.classify(self.matrix, '0', '1', position, self.layout, step, paid or {}, prior or {}, mode,
                              deployed=deployed)['stage']

    def test_a_cached_incumbent_miss_can_complete_the_witness(self):
        self.assertEqual(self.classify({('1', 0): True}), 'read-without-witness')
        self.assertEqual(self.classify({('1', 0): True}, {('0', 0): False}), 'paid-gain-witness')

    def test_distinguish_truncated_roster_and_archive_preemption(self):
        self.assertEqual(self.classify(mode='balanced', position=6), 'outside-wide-roster')
        self.assertEqual(self.classify(mode='balanced', position=5), 'unread')
        self.assertEqual(self.classify(mode='archive', archive=True), 'archive-preempted')

    def test_path_change_can_block_an_originally_viable_candidate(self):
        self.assertTrue(audit.eligible(self.matrix, '0', '0', '1', self.layout))
        self.assertEqual(self.classify(incumbent='2'), 'blocked-against-current')
        self.assertEqual(self.classify(incumbent='2', deployed=True), 'deployed-earlier')

    def test_full_search_overrides_a_single_witness_as_the_furthest_stage(self):
        paid = {('0', 0): False, ('1', 0): True, ('1', 1): False}
        self.assertEqual(self.classify(paid), 'fully-scored-other-nominee')

    def test_replay_captures_cached_reads_without_charging_them_twice(self):
        _, inputs = audit.prepare()
        panels, _, plan, _ = inputs['llama-mistral']
        matrix = panels[0]['correctness']
        held = audit.route.CONFIRMATION.holdout(panels[0]['subject'], len(matrix[0]))
        seed = plan['schedule']['seeds'][0]
        start, _ = audit.audit.gepa.continuous.schedule(len(matrix[0]), len(matrix), held, seed, plan['schedule'])
        totals, _, reads, _ = audit.trace_search(matrix, held, seed, plan, start)
        self.assertEqual(sum(map(len, reads)), totals['searchLogical'])
        self.assertEqual(len({key for cycle in reads for key in cycle}), totals['searchPaid'])
        self.assertGreater(totals['searchLogical'], totals['searchPaid'])
