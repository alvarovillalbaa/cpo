import json

import pytest

from benchmarks import first_gain_response_robustness as benchmark


@pytest.mark.parametrize('codepoint', (0xD800, 0xDC00))
def test_lone_surrogates_reject_whole_drafts(codepoint):
    raw = json.dumps({'rewrite': 'valid rewrite', 'repair': 'bad ' + chr(codepoint)})
    assert benchmark.proposals(raw, 'starting prompt', ('rewrite', 'repair')) == ()


def test_correctly_paired_unicode_is_preserved():
    draft = 'Return the exact action. 😀'
    raw = json.dumps({'instruction': draft})
    assert benchmark.proposals(raw, 'starting prompt', ('instruction',)) == (draft,)


def test_escaped_duplicate_key_and_type_mutation_lose_all_credit():
    expected = {'available': 0, 'review': True}
    assert benchmark.grounded.score('{"available":false,"review":true}', expected) == (False, 0)
    assert benchmark.grounded.score('{"available":0,"review":1}', expected) == (False, 0)
    assert benchmark.grounded.score('{"available":0,"review":true,"\\u0072eview":true}', expected) == (False, 0)
