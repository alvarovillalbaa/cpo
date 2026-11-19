import unittest

from cpo import Observation, ProposalBatch, ProposalPair, Row, classify_json_reply, run_cycle, search


class CycleTests(unittest.TestCase):
    def setUp(self):
        self.train = [Row("train", "sample")]
        self.validation = [Row("validation", "sample")]
        self.holdout = [Row("critical", "sample", True), Row("ordinary", "sample")]
        self.search_calls = []
        self.qualification_calls = []

    def evaluate(self, prompt, row):
        self.assertIn(row, self.train + self.validation)
        self.assertFalse(self.qualification_calls)
        self.search_calls.append((prompt, row.id))
        return Observation(prompt == "challenger", {"missed": row.id})

    def propose(self, incumbent, feedback, history, width):
        self.assertEqual(incumbent, "incumbent")
        self.assertEqual([row.id for row, _ in feedback], ["train"])
        self.assertEqual(history, [("incumbent", {})])
        return ["challenger"]

    def cycle(self, qualify, **options):
        def record(prompt, row, repeat):
            self.assertIn(row, self.holdout)
            self.qualification_calls.append((prompt, row.id, repeat))
            return qualify(prompt, row, repeat)

        return run_cycle("incumbent", self.train, self.validation, self.holdout, self.evaluate,
                         self.propose, metric_limit=3, rounds=1, train_per_round=1, qualify=record,
                         **options)

    def test_qualify_with_paired_repeats_after_search(self):
        result = self.cycle(lambda prompt, row, _: row.critical or prompt == "challenger", repeats=2)
        self.assertEqual(result.prompt, "challenger")
        self.assertTrue(result.promoted)
        self.assertEqual(result.search.evaluations, len(self.search_calls))
        self.assertEqual(result.qualification_evaluations, len(self.qualification_calls))
        self.assertEqual(len(set(self.qualification_calls)), 8)

    def test_critical_regression_blocks_promotion_even_with_gain(self):
        def qualify(prompt, row, repeat):
            if row.critical:
                return repeat == 0 or prompt == "incumbent"
            return prompt == "challenger"

        result = self.cycle(qualify, repeats=2)
        self.assertFalse(result.promoted)
        self.assertEqual(result.prompt, "incumbent")

    def test_overlapping_holdout_fails_before_search(self):
        self.holdout = self.train
        with self.assertRaisesRegex(ValueError, "disjoint"):
            self.cycle(lambda *_: True)
        self.assertFalse(self.search_calls)

    def test_uncalibrated_outcome_raises(self):
        with self.assertRaisesRegex(ValueError, "boolean"):
            self.cycle(lambda *_: 1)

    def test_unchanged_incumbent_skips_qualification(self):
        self.propose = lambda *_: ["incumbent"]
        result = self.cycle(lambda *_: self.fail("unchanged prompt must not be dispatched"))
        self.assertEqual(result.prompt, "incumbent")
        self.assertFalse(result.promoted)
        self.assertFalse(result.outcomes)

    def test_complete_rewrite_is_evaluated_first(self):
        self.propose = lambda *_: ProposalPair(rewrite="challenger", repair="other")
        result = self.cycle(lambda prompt, row, _: row.critical or prompt == "challenger")
        self.assertEqual(self.search_calls[-1], ("challenger", "validation"))
        self.assertTrue(result.promoted)

    def test_precomputed_opening_is_qualified_on_separate_rows(self):
        self.propose = lambda *_: self.fail("The precomputed pair needs no reflection")
        result = self.cycle(lambda prompt, row, _: row.critical or prompt == "challenger",
                            opening_pair=ProposalPair(rewrite="challenger", repair="other"))
        self.assertEqual(self.search_calls, [("incumbent", "validation"), ("challenger", "validation")])
        self.assertEqual(result.search.reflections, 0)
        self.assertEqual(result.qualification_evaluations, 4)
        self.assertTrue(result.promoted)

    def test_family_regression_blocks_promotion_even_with_gain(self):
        self.holdout = [Row("west", "west"), Row("east-1", "east"), Row("east-2", "east")]
        result = self.cycle(lambda prompt, row, _: (row.family == "west") == (prompt == "incumbent"))
        self.assertFalse(result.promoted)

    def test_typed_grading_rejects_coercion_and_duplicate_keys(self):
        self.assertEqual(classify_json_reply('{"release":true}', {"release": True}), "pass")
        self.assertEqual(classify_json_reply('{"release":1}', {"release": True}), "wrong_types")
        self.assertEqual(classify_json_reply('{"release":false,"release":true}', {"release": True}), "invalid_json")

    def test_exhausted_parent_yields_to_complementary_candidate(self):
        train = [Row("train", "routing")]
        validation = [Row("alpha", "routing"), Row("beta", "routing")]
        passed = {"a": {"alpha"}, "beta repair": {"beta"}, "complete": {"alpha", "beta"}}
        parents = []

        def propose(parent, *_):
            parents.append(parent)
            next_prompt = "beta repair" if parent == "a" else "complete"
            return ProposalBatch((next_prompt,), exhausted=True)

        result = search("a", train, validation, lambda prompt, row: Observation(row.id in passed[prompt], {}),
                        propose, metric_limit=15, rounds=4, train_per_round=1, adaptive=True)
        self.assertEqual(parents, ["a", "beta repair"])
        self.assertEqual(result.prompt, "complete")
