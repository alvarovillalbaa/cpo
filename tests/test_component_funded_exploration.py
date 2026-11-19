from types import SimpleNamespace

from benchmarks.component_dependencies import Diagnostic
from benchmarks.component_funded_exploration import choose_pair, should_promote
from benchmarks.component_merge import encode
from cpo import Observation, Row


def test_pair_has_one_unsupported_hint_and_two_unmeasured_candidates():
    old = {'aggregate': 'off', 'precedence': 'off', 'eligibility': 'off'}
    parent = {**old, 'precedence': 'guarded'}
    hint = {**parent, 'aggregate': 'guarded'}
    chosen = encode(parent)
    result = SimpleNamespace(prompt=chosen, events=[{'kind': 'validated', 'prompt': chosen, 'passed': []}])
    diagnosis = Observation(False, {'diagnostics': [Diagnostic('aggregate', 'guarded', 1, ('precedence',))]})
    journal = {(encode(old), 'train'): diagnosis}
    pair = choose_pair(result, journal, {'train'}, {'validation'}, 11)
    assert pair.parent == chosen
    assert pair.hint == encode(hint)
    assert pair.alternative not in (chosen, pair.hint)
    assert choose_pair(result, journal, set(), {'validation'}, 11) is None

    journal[pair.hint, 'validation'] = diagnosis
    assert choose_pair(result, journal, {'train'}, {'validation'}, 11) is None
    del journal[pair.hint, 'validation']
    journal[chosen, 'train'] = diagnosis
    assert choose_pair(result, journal, {'train'}, {'validation'}, 11) is None


def test_promotion_requires_a_strict_gain_without_displacing_a_critical_pass():
    rows = [Row('critical', 'aggregate', True), Row('a', 'aggregate'), Row('b', 'aggregate')]
    incumbent = {'critical': True, 'a': False, 'b': False}
    assert should_promote(incumbent, {**incumbent, 'a': True}, rows)
    assert not should_promote(incumbent, {'critical': False, 'a': True, 'b': True}, rows)
    assert not should_promote(incumbent, incumbent, rows)
