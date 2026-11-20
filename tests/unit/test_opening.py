import json
import unittest

from cpo.opening import OpeningReply, collect_opening


class OpeningTests(unittest.TestCase):
    def collect(self, request, *, mode='fill-missing', budget=2400, limit=40):
        return collect_opening('seed', request, mode=mode, pair_tokens=1200, single_tokens=600,
                               output_budget=budget, max_instruction_bytes=limit)

    def test_partial_reply_keeps_valid_rewrite_without_dispatching_it_again(self):
        calls = []

        def request(role, cap):
            calls.append((role, cap))
            return OpeningReply('completed', '{"rewrite":"better","repair":"seed"}' if role == 'pair' else
                                '{"instruction":"smaller edit"}')

        result = self.collect(request)
        self.assertEqual(calls, [('pair', 1200), ('repair', 600)])
        self.assertEqual(result.prompts, ('better', 'smaller edit'))
        self.assertEqual([attempt.accepted for attempt in result.attempts], [('rewrite',), ('repair',)])

    def test_capped_reply_has_no_candidates_even_if_it_contains_parseable_text(self):
        responses = {
            'pair': OpeningReply('output_limit', '{"rewrite":"never use","repair":"never use either"}'),
            'rewrite': OpeningReply('completed', '{"instruction":"rewrite only"}'),
            'repair': OpeningReply('output_limit', ''),
        }
        result = self.collect(lambda role, _cap: responses[role])
        self.assertEqual(result.prompts, ('rewrite only',))
        self.assertIsNone(result.repair)
        self.assertEqual([attempt.status for attempt in result.attempts], ['output_limit', 'completed', 'output_limit'])

    def test_reserved_budget_can_fund_only_one_split_request(self):
        calls = []

        def request(role, cap):
            calls.append((role, cap))
            return OpeningReply('completed', '{"instruction":"only rewrite"}')

        result = self.collect(request, mode='split', budget=600)
        self.assertEqual(calls, [('rewrite', 600)])
        self.assertEqual(sum(attempt.max_output_tokens for attempt in result.attempts), 600)

    def test_unknown_transport_result_does_not_dispatch_another_request(self):
        def request(role, _cap):
            self.assertEqual(role, 'pair')
            raise TimeoutError('request status unknown')

        with self.assertRaisesRegex(TimeoutError, 'status unknown'):
            self.collect(request)

    def test_rejects_duplicate_keys_and_invalid_serialized_instructions(self):
        for response in ('{"rewrite":"x","rewrite":"y","repair":"z"}',
                         json.dumps({'rewrite': '\ud800', 'repair': '😀' * 4}),
                         '{"rewrite":"a","repair":"b","extra":true}'):
            with self.subTest(response=response):
                result = self.collect(lambda *_: OpeningReply('completed', response), mode='pair', limit=20)
                self.assertEqual(result.prompts, ())
