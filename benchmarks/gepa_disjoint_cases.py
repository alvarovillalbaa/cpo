"""Use stable case IDs with GEPA's shared evaluation cache."""

from collections.abc import Sequence

from benchmarks.opening_screen_typed import gepa_select as native_select


class CaseRows(Sequence):
    def __init__(self, rows):
        self.rows = tuple(rows)
        self.by_id = {row['id']: row for row in self.rows}
        if len(self.by_id) != len(self.rows):
            raise ValueError('GEPA case IDs must be distinct')

    def __getitem__(self, index):
        return self.rows[index]

    def __len__(self):
        return len(self.rows)

    def all_ids(self):
        return list(self.by_id)

    def fetch(self, ids):
        return [self.by_id[key] for key in ids]


def select(initial, bank, groups, evaluate, reflect, **options):
    """Keep native GEPA's separate splits and use their original case IDs."""
    train, validation = CaseRows(groups['train']), CaseRows(groups['validation'])
    if train.by_id.keys() & validation.by_id.keys():
        raise ValueError('GEPA training and validation case IDs must be disjoint')
    return native_select(initial, bank, {**groups, 'train': train, 'validation': validation},
                         evaluate, reflect, **options)
