"""Verify the packaged routing policy against the sealed language and math results."""

from hashlib import sha256
import json
from unittest.mock import patch

from benchmarks import validation_routed_opening as study
from cpo._contract import digest
from cpo.full_roster_precheck.validation_routing import run_validation_routed_episode


RECEIPT_SHA = '5b461240dec45149ef92e912f615a5f12b34d0ca5a8a637fa71c60e3d81607d8'


def packaged(incumbent, _training, cycles, evaluate, *, probe, qualify):
    return run_validation_routed_episode(incumbent, cycles, evaluate, qualify=qualify)


def test_packaged_route_reproduces_the_sealed_language_and_math_receipt():
    raw = (study.language.refit.transfer.ROOT / 'docs/validation-routed-opening-v1.json').read_bytes()
    assert sha256(raw).hexdigest() == RECEIPT_SHA
    expected = json.loads(raw)
    plan, language_plan, prior, math_plan, reference, data = study.prepare()
    assert digest(plan) == digest(expected['plan']) == expected['planSha256']
    with patch.object(study, 'play', packaged):
        language = study.measure_language(language_plan, prior)
        math = study.measure_math(math_plan, reference, data)
    assert json.loads(json.dumps({'language': language, 'math': math})) == {
        'language': expected['language'], 'math': expected['math'],
    }
