from importlib.metadata import PackageNotFoundError, version
import unittest

from benchmarks import prompteval_transfer as transfer


try:
    GEPA_VERSION = version('gepa')
except PackageNotFoundError:
    GEPA_VERSION = None


class PromptEvalTransferTests(unittest.TestCase):
    def test_import_binds_complete_matrices_and_shared_holdouts(self):
        data, sizes, fingerprint = transfer.read_source()
        manifest = transfer.plan(data, sizes, fingerprint)
        self.assertEqual(len(data['panels']), 6)
        self.assertEqual(sizes, {'formal_logic': 126, 'high_school_computer_science': 100, 'world_religions': 171})
        for subject, cases in manifest['holdoutCaseIDs'].items():
            self.assertEqual(len(cases), sizes[subject] * 30 // 100)
            self.assertEqual(cases, sorted(set(cases)))
            self.assertTrue(all(0 <= case < sizes[subject] for case in cases))

    def test_minibatch_requires_a_strict_gain(self):
        self.assertEqual(transfer.minibatch_shortlist(['base', 'a'], [3, 8, 9],
                                                    lambda _prompt, _row: True), ['base'])
        self.assertEqual(transfer.minibatch_shortlist(['base', 'a'], [3, 8, 9],
                                                    lambda prompt, row: prompt == 'a' and row == 8), ['base', 'a'])

    @unittest.skipUnless(GEPA_VERSION == '0.1.4', 'requires the pinned GEPA benchmark dependency')
    def test_all_arms_use_the_same_holdout_and_obey_lookup_caps(self):
        corpus, sizes, _ = transfer.read_source()
        panel = corpus['panels'][0]
        subject = panel['subject']
        excluded = transfer.holdout(subject, sizes[subject])
        for seed in transfer.SEEDS[:2]:
            rows = transfer.compare(panel['correctness'], excluded, seed)
            self.assertTrue(set(excluded).isdisjoint(rows['train'] + rows['validation']))
            self.assertTrue(set(rows['train']).isdisjoint(rows['validation']))
            self.assertEqual(set(rows['arms']), set(transfer.ARMS))
            for arm in rows['arms'].values():
                self.assertIn(arm['candidate'], rows['candidates'])
                self.assertLessEqual(arm['evaluations'], transfer.LOOKUP_LIMIT)
                vector = panel['correctness'][int(arm['candidate'])]
                self.assertEqual(arm['holdoutPasses'], sum(vector[case] == '1' for case in excluded))


if __name__ == '__main__':
    unittest.main()
