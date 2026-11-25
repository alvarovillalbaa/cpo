"""Check the packaged fixed openings against the sealed math replay."""

from collections import Counter
from functools import partial
from hashlib import sha256
import json

import pytest

from benchmarks import full_roster_fixed_opening as study
from cpo._contract import digest
from cpo.full_roster_precheck.fixed_opening import run_fixed_opening_episode


RECEIPT_SHA = 'f0b747ac89f2a1e57fe9c42e81c0e383a4a53f2b4d1e6cbc018bfd932a3f021b'


def packaged(schedule, incumbent, _training, cycles, evaluate, *, probe, qualify):
    return run_fixed_opening_episode(incumbent, cycles, evaluate, schedule=schedule, qualify=qualify)


@pytest.mark.parametrize('subject', ('aime', 'arc'))
def test_packaged_openings_reproduce_all_recorded_rosters(subject):
    transfer = study.transfer
    raw = (transfer.math.ROOT / 'docs/full-roster-fixed-opening-v1.json').read_bytes()
    assert sha256(raw).hexdigest() == RECEIPT_SHA
    receipt = json.loads(raw)
    plan, archive = study.prepare()
    assert digest(plan) == digest(receipt['plan']) == receipt['planSha256']
    cells = transfer.math.load_cells(subject, archive[subject]['record'])

    for group in plan['incumbentGroups']:
        for width in plan['challengerCounts']:
            directions = receipt['results'][subject][f'{group}/{width}']['directions']
            for baseline, audit in ((directions[0], directions[1]), (directions[1], directions[0])):
                fold = baseline['calibrationFold']
                subset, trials, _ = study.crossfit.get_fold(cells, plan['datasets'][subject], fold, group, width)
                assert fold == audit['auditFold'] and len(trials) == baseline['trials'] == audit['trials']
                totals = {label: Counter() for label in study.ARMS}
                for trial in trials:
                    _, cost, _, _ = transfer.episode(transfer.RUNNERS[study.ADAPTIVE], subset, trial)
                    totals[study.ADAPTIVE].update(cost)
                    for label in plan['fixedMenu']:
                        expected = transfer.episode(partial(study.run_fixed, label), subset, trial)
                        actual = transfer.episode(partial(packaged, label), subset, trial)
                        assert actual == expected
                        totals[label].update(actual[1])
                assert totals == baseline['calibrationCpoMenu']
                assert totals[study.ADAPTIVE] == audit['audit'][study.ADAPTIVE]
                assert totals[audit['fixedSetting']] == audit['audit'][study.FIXED]
