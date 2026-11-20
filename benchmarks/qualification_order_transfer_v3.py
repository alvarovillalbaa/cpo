"""Replay the revised enrollment with only published capture dependencies."""

from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from benchmarks import qualification_order_transfer_v2 as previous
from benchmarks.case_difficulty_allocation import checked_file


original = previous.original
DESIGN = original.ROOT / 'docs/qualification-order-transfer-design-v3.json'
SNAPSHOT = original.ROOT / 'benchmarks/data/qualification-order-transfer-v3.json'
PREVIOUS = '1ba03ee5d77d0eacf090e3881c103d65c6f8ba1c6b16d361c9539df20d598234'
OLDER_SNAPSHOT = '66cfc58fb006b87063ed2e4b3bb5561b7d27bc89b70c9267c4a7fa1f9afd9f17'
OLD_SHA = 'e7f3789abb291ae307034a39af9eb0296d81a10bec1977272c36eeb840e691cf'


def design(members, prior):
    stored = checked_file('docs/qualification-order-transfer-design-v2.json', OLD_SHA)
    if stored['designSha256'] != PREVIOUS:
        raise ValueError('The revised experiment must retain its published identity')
    plan = previous.design(members, prior)
    if any(key != 'sourceSha256' and value != stored['design'][key] for key, value in plan.items()):
        raise ValueError('The source amendment may change only capture infrastructure')
    plan.update(protocol='cpo-qualification-order-transfer-v3', infrastructureAmendment={
        'parentDesignSha256': PREVIOUS,
        'parentSnapshotSha256': OLDER_SNAPSHOT,
        'change': 'Inline identical member selection and reduction to remove the unpublished helper import.',
    })
    plan['sourceSha256']['benchmarks/qualification_order_transfer_v3.py'] = sha256(Path(__file__).read_bytes()).hexdigest()
    return plan


def freeze():
    plan = checked_file('docs/qualification-order-transfer-design-v2.json', OLD_SHA)['design']
    return design(plan['members'], plan['priorInventory'])


if __name__ == '__main__':
    with patch.multiple(original, TASKS=previous.TASKS, DESIGN=DESIGN, SNAPSHOT=SNAPSHOT, design=design, freeze=freeze):
        original.main()
