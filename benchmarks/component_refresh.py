"""Compare refreshing incompatible component diagnostics with testing edits they suggest."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
from inspect import signature
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import component_dependencies as prior, component_merge as fixture, frontier
from benchmarks.component_dependencies import next_edit as rank_compatible
from cpo import optimizer
from cpo._contract import digest
from cpo.evidence import can_reuse_component_feedback as compatible


SEEDS = tuple(range(59401, 59705, 19))
ARMS = ('cpo-dependencies', 'cpo-component', 'cpo-refresh', 'cpo-matched-refresh', 'cpo-explore',
        'cpo-matched-explore', 'gepa-dependencies', 'gepa-dependencies-merge')


def changed_context(source, parent, diagnostic):
    """Use declared scope only. The fixture's oracle is reserved for auditing."""
    return (compatible(source, parent, diagnostic.component, dependencies=())
            and not compatible(source, parent, diagnostic.component, dependencies=diagnostic.declared))


def replacement_probe(encoded_parent, scheduled, probes, training_cache, *, matched, counts):
    parent = json.loads(encoded_parent)
    scheduled_ids = {row.id for row in scheduled}
    stale = set()
    for (encoded_source, case), observation in training_cache.items():
        if encoded_source == encoded_parent or (encoded_parent, case) in training_cache:
            continue
        source = json.loads(encoded_source)
        if any(changed_context(source, parent, diagnosis) for diagnosis in observation.feedback['diagnostics']):
            stale.add(case)
    if not stale or stale & scheduled_ids:
        return None
    for target in sorted((row for row in probes if row.id in stale), key=lambda row: not row.critical):
        control = next((row for row in probes if row.family == target.family and row.critical == target.critical
                        and row.id not in stale | scheduled_ids and (encoded_parent, row.id) not in training_cache), None)
        if control is not None:
            counts['replacements'] += 1
            counts['criticalReplacements'] += target.critical
            return control if matched else target
    return None


def explore(parent, journal, training, seen, _, audit, *, matched, offered):
    """Give a hypothesis the second slot. Its incompatible evidence receives no votes."""
    if audit['proposals'] % 2 == 0:
        encoded_parent = fixture.encode(parent)
        supported, hypotheses = set(), set()
        for (encoded_source, case), observation in journal.items():
            if case not in training:
                continue
            source = json.loads(encoded_source)
            for diagnosis in observation.feedback['diagnostics']:
                action = (diagnosis.component, diagnosis.replacement)
                if compatible(source, parent, diagnosis.component, dependencies=diagnosis.declared):
                    supported.add(action)
                elif changed_context(source, parent, diagnosis):
                    hypotheses.add(action)
        unsupported = {(family, value) for family in frontier.FAMILIES for value in ('guarded', 'broad')
                       if parent[family] != value} - supported
        novel = {}
        for family, replacement in unsupported:
            candidate = {**parent, family: replacement}
            if (encoded_parent, fixture.encode(candidate)) not in seen:
                novel[(family, replacement)] = candidate
        suggested = hypotheses & novel.keys()
        unhinted = novel.keys() - hypotheses
        if suggested and unhinted:
            options = unhinted if matched else suggested
            selected = min(options, key=lambda action: digest([encoded_parent, *action]))
            candidate = novel[selected]
            edge = encoded_parent, fixture.encode(candidate)
            offered.add(edge)
            seen.add(edge)
            return candidate
    return rank_compatible(parent, journal, training, seen, 'dependencies', audit)


def compare(profile, seed, cap):
    arms = {}
    for arm in ARMS:
        counts, offered = Counter(), set()
        refresh = None
        if arm.endswith('-refresh'):
            refresh = partial(replacement_probe, matched=arm == 'cpo-matched-refresh', counts=counts)
        propose = (partial(explore, matched=arm == 'cpo-matched-explore', offered=offered)
                   if arm.endswith('-explore') else rank_compatible)
        reference = 'cpo-dependencies' if refresh or arm.endswith('-explore') else arm

        def run_search(*args, **kwargs):
            result = optimizer.search(*args, **kwargs, refresh_training=refresh)
            counts['offered'] = len(offered)
            explored = [event for event in result.events if (event.get('parent'), event['prompt']) in offered]
            counts['tested'] = len({event['prompt'] for event in explored})
            counts['validated'] = sum(event['kind'] == 'validated' for event in explored)
            counts['selected'] = any(event['kind'] == 'validated' and event['prompt'] == result.prompt for event in explored)
            return result

        with patch.object(prior, 'ARMS', (reference,)), patch.object(prior, 'next_edit', propose), \
                patch.object(fixture, 'search', run_search):
            trial = prior.compare(profile, seed, cap)
        arms[arm] = {**trial['arms'][reference], 'interventions': dict(counts)}
    return {**trial, 'arms': arms}


def prepare():
    plan = prior.prepare()
    root = Path(__file__).resolve().parents[1]
    for name in ('benchmarks/component_refresh.py', 'benchmarks/patches/component-refresh.patch'):
        plan['sourceSha256'][name] = sha256((root / name).read_bytes()).hexdigest()
    return {**plan, 'protocol': 'cpo-component-refresh-v1', 'seedCohort': 'disjoint from dependency and pilot seeds',
            'seeds': list(SEEDS), 'arms': list(ARMS), 'primary': 'cpo-explore',
            'cohortDigests': {profile: digest([prior.cases(profile, seed) for seed in SEEDS]) for profile in prior.PROFILES}}


def panel_report(trials, primary):
    with patch.object(prior, 'PRIMARY', primary), patch.object(prior, 'ARMS', ARMS):
        summary = prior.summarize(trials)
    for arm in ARMS:
        counts = Counter()
        for trial in trials:
            counts.update(trial['arms'][arm]['interventions'])
        summary['totals'][arm]['interventions'] = dict(counts)
    return {**summary, 'trials': trials}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if 'refresh_training' not in signature(optimizer.search).parameters:
        parser.error('Apply benchmarks/patches/component-refresh.patch in a disposable source export')
    plan = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    results = {}
    for cap in plan['caps']:
        results[str(cap)] = {}
        for profile in plan['profiles']:
            trials = [compare(profile, seed, cap) for seed in plan['seeds']]
            results[str(cap)][profile] = panel_report(trials, plan['primary'])
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
