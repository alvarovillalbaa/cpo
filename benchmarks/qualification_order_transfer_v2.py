"""Keep the original schedule after excluding one incomplete archive task."""

from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from benchmarks import qualification_order_transfer as original
from benchmarks.case_difficulty_allocation import checked_file


ROOT = original.ROOT
DESIGN = ROOT / 'docs/qualification-order-transfer-design-v2.json'
SNAPSHOT = ROOT / 'benchmarks/data/qualification-order-transfer-v2.json'
TASKS = {**original.TASKS, 'LMentry': tuple(task for task in original.TASKS['LMentry']
                                          if task != 'word_not_containing')}
PREVIOUS = '0defe10b24e645c666921e88f0520532079852a22c62bdabd3733ff5903156de'
OLD_SHA = 'ceb5b1e7bbbf268d66cc451c7c58f37e6c60b7614a24313dedaaeaf35c4ce67d'
original_design = original.design


def design(members, prior):
    stored = checked_file('docs/qualification-order-transfer-design-v1.json', OLD_SHA)
    if stored['designSha256'] != PREVIOUS:
        raise ValueError('The initial enrollment must retain its published identity')
    plan = original_design(members, prior)
    original_members = [item for item in stored['design']['members'] if item['subject'] != 'lmentry-word_not_containing']
    if members != original_members or prior != stored['design']['priorInventory']:
        raise ValueError('The revised roster must preserve every structurally eligible enrollment')
    plan.update(protocol='cpo-qualification-order-transfer-v2', previousDesignSha256=PREVIOUS,
                structuralExclusion={'subject': 'lmentry-word_not_containing', 'casesPerModel': 26,
                                     'frozenMinimumCases': 98})
    plan['sourceSha256']['benchmarks/qualification_order_transfer_v2.py'] = sha256(Path(__file__).read_bytes()).hexdigest()
    return plan


if __name__ == '__main__':
    with patch.multiple(original, TASKS=TASKS, DESIGN=DESIGN, SNAPSHOT=SNAPSHOT, design=design):
        original.main()
