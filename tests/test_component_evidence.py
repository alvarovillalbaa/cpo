"""Exercise feedback reuse across prompt edits and missing declarations."""

from cpo.evidence import can_reuse_component_feedback as compatible


def test_unknown_scope_requires_exact_parent():
    source = {'routing': 'v1', 'format': 'json'}
    assert compatible(source, dict(source), 'routing')
    assert not compatible(source, {**source, 'format': 'text'}, 'routing')


def test_declared_scope_requires_only_the_component_and_its_dependencies():
    source = {'routing': 'v1', 'format': 'json', 'eligibility': 'all'}
    current = {**source, 'eligibility': 'active'}
    assert compatible(source, current, 'routing', dependencies=('format',))
    assert not compatible(source, {**current, 'routing': 'v2'}, 'routing', dependencies=('format',))
    assert not compatible(source, {**current, 'format': 'text'}, 'routing', dependencies=('format',))
    assert compatible(source, {**current, 'format': 'text'}, 'routing', dependencies=())


def test_undeclared_component_or_inconsistent_schema_prevents_reuse():
    source = {'routing': 'v1', 'format': 'json'}
    assert not compatible(source, source, 'eligibility')
    assert not compatible(source, source, 'routing', dependencies=('eligibility',))
    assert not compatible(source, {'routing': 'v1', 'rendering': 'json'}, 'routing', dependencies=())
