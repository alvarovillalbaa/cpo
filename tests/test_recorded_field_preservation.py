import unittest

from benchmarks.recorded_field_preservation import field_guard


class FieldPreservationTests(unittest.TestCase):
    def test_equal_field_totals_can_hide_a_lost_correct_field(self):
        rows = {'critical': {'critical': True}}
        masks = {('old', 'critical'): frozenset({'eligible'}),
                 ('new', 'critical'): frozenset({'amount'})}
        for preserve_identity, expected in ((False, []), (True, ['critical'])):
            with self.subTest(preserve_identity=preserve_identity):
                blocked, extra = field_guard('old', 'new', tuple(rows), rows, masks, (),
                                             preserve_identity=preserve_identity)
                self.assertEqual((blocked, extra), (expected, 1))

    def test_charges_only_missing_protected_replies_until_rejection(self):
        rows = {case: {'critical': case != 'ordinary'} for case in
                ('ordinary', 'empty', 'paid', 'loss', 'unused')}
        masks = {('old', case): frozenset({'amount'}) for case in rows}
        masks['old', 'empty'] = frozenset()
        masks['new', 'paid'] = frozenset({'amount'})
        masks['new', 'loss'] = frozenset()
        rejected, extra = field_guard('old', 'new', tuple(rows), rows, masks, {'paid': False},
                                      preserve_identity=True)
        self.assertEqual((rejected, extra), (['loss'], 1))
