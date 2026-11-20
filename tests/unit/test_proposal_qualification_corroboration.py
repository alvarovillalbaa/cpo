from collections import Counter
from itertools import product
from types import SimpleNamespace
from unittest import TestCase

from benchmarks.proposal_qualification_corroboration import corroborate, reserve_cases
from cpo import Row
from cpo.paired_qualification import certify_paired_qualification


class ProposalCorroborationTests(TestCase):
    def test_reserves_are_disjoint_from_the_entire_episode(self):
        layouts = [
            {'train': [0], 'validation': [1, 2], 'qualify': [3, 4]},
            {'train': [0, 2], 'validation': [5], 'qualify': [6, 7]},
        ]
        reserved = reserve_cases(14, [8, 9], 1979, layouts)
        self.assertEqual(reserved, reserve_cases(14, [8, 9], 1979, layouts))
        self.assertEqual([len(layout['corroborate']) for layout in reserved], [2, 2])
        self.assertEqual(set(reserved[0]['corroborate'] + reserved[1]['corroborate']), {10, 11, 12, 13})
        self.assertFalse(any('corroborate' in layout for layout in layouts))
        self.assertEqual(sum(len(layout['corroborate']) for layout in reserve_cases(13, [8, 9], 1979, layouts)), 2)

    def test_certificate_and_paid_replies_match_full_scores_exhaustively(self):
        rows = [Row(str(case), 'task') for case in range(2)]
        panels = list(product('01', repeat=4))
        for incumbent, challenger in product(panels, repeat=2):
            matrix = (incumbent, challenger)
            decision = certify_paired_qualification('0', '1', rows,
                                                    lambda p, row, _: matrix[int(p)][int(row.id)] == '1')
            result = SimpleNamespace(promoted=decision.status == 'promoted', qualification=decision,
                                     prompt=decision.prompt)
            delta = [int(b) - int(a) for a, b in zip(incumbent, challenger)]
            layout = {'seed': 0, 'corroborate': [2, 3]}
            counts = Counter()
            selected, added = corroborate(matrix, '0', result, rows, layout, enforce=True, counters=counts)
            again, paid = corroborate(matrix, '0', result, rows, layout, enforce=False, counters=Counter())
            first_gain, reserve_gain = sum(delta[:2]), sum(delta[2:])
            expected = first_gain >= 2 or (first_gain == 1 and reserve_gain >= 1)
            self.assertEqual(selected, '1' if expected else '0', matrix)
            self.assertEqual(again, result.prompt)
            self.assertEqual(added, paid)
            self.assertEqual(len(added), counts['marginLookups'] + counts['corroborationLookups'])
            keys = [(item.prompt, item.row_id) for item in decision.observations] + [reply[:2] for reply in added]
            self.assertEqual(len(keys), len(set(keys)))
            self.assertLessEqual(len(keys), 8)

    def test_preserve_promotion_without_full_reserve(self):
        rows = [Row('0', 'task')]
        decision = certify_paired_qualification('0', '1', rows, lambda p, *_: p == '1')
        result = SimpleNamespace(promoted=True, qualification=decision, prompt='1')
        counters = Counter()
        selected, paid = corroborate(('0', '1'), '0', result, rows, {'seed': 0, 'corroborate': []},
                                     enforce=True, counters=counters)
        self.assertEqual((selected, paid), ('1', []))
        self.assertEqual(counters['promotionWithoutReserve'], 1)
