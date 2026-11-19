from collections import Counter

from benchmarks.component_dependencies import Diagnostic
from benchmarks.component_merge import encode
from benchmarks.component_refresh import changed_context, explore, replacement_probe
from cpo import Observation, Row


SOURCE = {'aggregate': 'off', 'precedence': 'off', 'eligibility': 'off'}
PARENT = {**SOURCE, 'precedence': 'guarded'}
DIAGNOSIS = Diagnostic('aggregate', 'guarded', 1, ('precedence',))


def test_refresh_matches_critic_and_family_and_skips_already_measured_rows():
    target, control = (Row(name, 'aggregate', True) for name in ('target', 'control'))
    scheduled = Row('scheduled', 'aggregate')
    rows = (target, control, scheduled)
    observation = Observation(False, {'diagnostics': [DIAGNOSIS]})
    cache = {(encode(SOURCE), target.id): observation}
    counts = Counter()

    def choose(matched):
        return replacement_probe(encode(PARENT), (scheduled,), rows, cache, matched=matched, counts=counts)

    assert choose(False) == target
    assert choose(True) == control
    assert counts == {'replacements': 2, 'criticalReplacements': 2}
    cache[encode(PARENT), target.id] = Observation(True, {'diagnostics': []})
    assert choose(False) is None


def test_exploration_does_not_vote_from_incompatible_evidence():
    assert changed_context(SOURCE, PARENT, DIAGNOSIS)
    assert not changed_context(SOURCE, PARENT, DIAGNOSIS._replace(declared=()))
    assert not changed_context(SOURCE, {**PARENT, 'aggregate': 'broad'}, DIAGNOSIS)
    journal = {(encode(SOURCE), 'train'): Observation(False, {'diagnostics': [DIAGNOSIS]})}
    training = {'train': {'critical': False}}
    first = explore(PARENT, journal, training, set(), 'dependencies', Counter(proposals=1),
                    matched=False, offered=set())
    assert first == PARENT
    audit = Counter(proposals=2)
    offered = set()
    explored = explore(PARENT, journal, training, set(), 'dependencies', audit, matched=False, offered=offered)
    assert explored == {**PARENT, 'aggregate': 'guarded'}
    assert offered == {(encode(PARENT), encode(explored))}
    assert audit['stale'] == 0 and audit['transferred'] == 0
