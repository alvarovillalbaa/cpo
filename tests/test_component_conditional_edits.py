from collections import Counter

from benchmarks.component_conditional_edits import conditional_edit, edit_branch, score, shifted_labels
from benchmarks.component_dependencies import Diagnostic
from benchmarks.component_merge import encode
from cpo import Observation


def test_conditional_repair_preserves_fallback_and_fixes_the_interaction():
    initial = {'aggregate': 'guarded', 'precedence': 'guarded', 'eligibility': 'guarded'}
    legacy = {'id': 'legacy', 'needs': [], 'forbids': ['aggregate'], 'interaction': False}
    interaction = {'id': 'interaction', 'needs': ['aggregate', 'precedence'], 'forbids': ['eligibility'],
                   'interaction': True}
    fixed = {**initial, 'aggregate': edit_branch(initial['aggregate'], True, 'broad')}
    assert score(initial, legacy, 'routing').passed and not score(initial, interaction, 'routing').passed
    assert score(fixed, legacy, 'routing').passed and score(fixed, interaction, 'routing').passed
    assert not score({**initial, 'aggregate': 'broad'}, legacy, 'routing').passed
    assert not score(fixed, {**interaction, 'interaction': False}, 'routing').passed
    assert edit_branch('scope:off:broad', False, 'guarded') == fixed['aggregate']


def test_conditional_operator_requires_compatible_training_witnesses():
    initial = {'aggregate': 'guarded', 'precedence': 'guarded', 'eligibility': 'guarded'}
    diagnosis = Diagnostic('aggregate', 'broad', 1, ('precedence',))
    journal = {(encode(initial), 'training'): Observation(False, {'diagnostics': [diagnosis]})}
    training = {'training': {'critical': True, 'interaction': True}}
    assert conditional_edit(initial, journal, training, set(), 'dependencies', Counter())['aggregate'] == 'scope:guarded:broad'
    assert conditional_edit(initial, journal, {}, set(), 'dependencies', Counter()) == initial
    mixed = {**journal, (encode(initial), 'other'): journal[encode(initial), 'training']}
    training['other'] = {'critical': False, 'interaction': False}
    assert conditional_edit(initial, mixed, training, set(), 'dependencies', Counter())['aggregate'] == 'broad'


def test_label_shift_changes_only_the_explicit_condition_for_a_seeded_subset():
    rows = [{'id': str(index), 'interaction': index % 2 == 0, 'needs': []} for index in range(36)]
    shifted = shifted_labels(rows, 17)
    assert sum(before != after for before, after in zip(rows, shifted)) == 7
    assert [{**after, 'interaction': before['interaction']} for before, after in zip(rows, shifted)] == rows
    assert shifted == shifted_labels(rows, 17)
