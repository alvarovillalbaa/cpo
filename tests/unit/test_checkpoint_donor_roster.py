from collections import Counter

import pytest

from benchmarks.checkpoint_donor_roster import DONOR, MIXED, SEEDED, align_donors, ceiling, donor_rosters


def test_donor_ranking_only_reads_training_and_hybrid_keeps_four_original_slots():
    start = '0'
    seeded = tuple(map(str, range(1, 9)))
    templates = tuple(map(str, range(17)))
    training = (3, 5)
    paid = Counter()

    def read(prompt, case):
        assert prompt != start and case in training
        paid[prompt, case] += 1
        return int(int(prompt) >= 9)

    rosters = donor_rosters(start, seeded, templates, training, read, 'subject', 104)

    assert rosters[SEEDED] == seeded
    assert set(rosters[DONOR]) == set(map(str, range(9, 17)))
    assert rosters[MIXED][1::2] == seeded[:4]
    assert set(rosters[MIXED][::2]) <= set(rosters[DONOR])
    assert paid == Counter({(prompt, case): 1 for prompt in templates[1:] for case in training})


def test_checkpoint_pairs_require_equal_verified_case_order():
    left, right = ['01'] * 100, ['10'] * 100
    panels = [('subject', 'left', left), ('subject', 'right', right)]
    entries = [{'subject': name, 'model': model, 'caseOrderSha256': 'same', 'correctness': matrix}
               for name, model, matrix in panels]

    assert align_donors(panels, entries)['subject', 'left']['model'] == 'right'
    entries[1]['caseOrderSha256'] = 'different'
    with pytest.raises(ValueError, match='same ordered cases'):
        align_donors(panels, entries)


def test_gated_hindsight_ceiling_uses_both_target_panels_before_held_out_scores():
    cells = {'start': (0, 0, 0, 0, 0), 'qualification-only': (0, 1, 1, 1, 1),
             'validation-only': (1, 0, 0, 1, 1), 'both': (1, 1, 0, 1, 0)}
    roster = tuple(cells)[1:]
    roles = (), (0,), (1, 2), (3, 4)

    assert ceiling(cells, 'start', roster, roles, 1) == 1
    assert ceiling(cells, 'start', roster, roles, 2) == 0
