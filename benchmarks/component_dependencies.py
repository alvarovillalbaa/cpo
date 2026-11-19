"""Test feedback reuse when an edit's validity depends on another component."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from traceback import extract_tb
from typing import NamedTuple
from unittest.mock import patch

from benchmarks import component_merge as fixture, frontier
from cpo import Observation
from cpo._contract import digest
from cpo.evidence import can_reuse_component_feedback


SEEDS = tuple(range(58301, 58605, 19))
PROFILES = ('local', 'routing', 'approval', 'unknown')
ARMS = ('cpo-parent', 'cpo-component', 'cpo-dependencies', 'gepa-dependencies', 'gepa-dependencies-merge')
PRIMARY = 'cpo-dependencies'


class Diagnostic(NamedTuple):
    component: str
    replacement: str
    priority: int
    declared: tuple[str, ...] | None = ()
    actual: tuple[str, ...] = ()


def cases(profile, seed):
    base = 'reverse-precedence' if profile in ('routing', 'unknown') else 'multi-clause'
    return frontier.make_cpo_cases(base, seed)


def score(program, row, profile):
    diagnostics = []
    target, dependency = ('eligibility', 'aggregate') if profile == 'approval' else ('aggregate', 'precedence')
    contextual = profile != 'local' and len(row['needs']) > 1
    for family in row['needs']:
        if contextual and family == dependency and program[dependency] == 'off':
            diagnostics.append(Diagnostic(dependency, 'guarded', 2))
        elif contextual and family == target:
            replacement = 'guarded' if program[dependency] == 'off' else 'broad'
            if program[family] != replacement:
                scope = (dependency,)
                diagnostics.append(Diagnostic(family, replacement, 1, None if profile == 'unknown' else scope, scope))
        elif program[family] == 'off':
            diagnostics.extend(Diagnostic(family, replacement, 0) for replacement in ('guarded', 'broad'))
    diagnostics.extend(Diagnostic(family, 'guarded', 3) for family in row['forbids'] if program[family] == 'broad')
    return Observation(not diagnostics, {'diagnostics': diagnostics})


def next_edit(parent, journal, training, seen, mode, audit):
    votes = {}
    encoded_parent = fixture.encode(parent)
    for (encoded_source, case), observation in journal.items():
        if case not in training or (mode == 'parent' and encoded_source != encoded_parent):
            continue
        source = json.loads(encoded_source)
        for diagnostic in observation.feedback['diagnostics']:
            scope = diagnostic.declared if mode == 'dependencies' else ()
            if not can_reuse_component_feedback(source, parent, diagnostic.component, dependencies=scope):
                continue
            if encoded_source != encoded_parent:
                audit['transferred'] += 1
                audit['stale'] += not can_reuse_component_feedback(
                    source, parent, diagnostic.component, dependencies=diagnostic.actual)
            action = (diagnostic.component, diagnostic.replacement, diagnostic.priority)
            votes.setdefault(action, {})[case] = 1 + int(training[case]['critical'])
    ranked = sorted(votes, key=lambda action: (-action[2], -sum(votes[action].values()),
                                              frontier.FAMILIES.index(action[0]), action[1] != 'guarded'))
    for family, replacement, _ in ranked:
        candidate = {**parent, family: replacement}
        edge = encoded_parent, fixture.encode(candidate)
        if edge not in seen:
            seen.add(edge)
            return candidate
    return parent


def compare(profile, seed, cap):
    groups = cases(profile, seed)
    initial = dict.fromkeys(frontier.FAMILIES, 'off')
    training = {row['id']: row for row in groups['train']}
    allowed = {**training, **{row['id']: row for row in groups['validation']}}
    arms = {}
    for arm in ARMS:
        _, mode, *_ = arm.split('-')
        journal, seen, audit = {}, set(), Counter()
        failure = None

        def observe(program, case):
            if case not in allowed:
                raise ValueError('Search requested a holdout case')
            key = fixture.encode(program), case
            if key not in journal:
                if len(journal) >= cap:
                    raise fixture.BudgetReached
                journal[key] = score(program, allowed[case], profile)
            return journal[key]

        def propose(parent, _slot, _profile):
            audit['proposals'] += 1
            return next_edit(parent, journal, training, seen, mode, audit)

        with patch.object(fixture, 'propose_edit', propose):
            if arm.startswith('cpo-'):
                selected, proposals, merges, _ = fixture.run_cpo(
                    'cpo-ordinary', groups, profile, seed, cap, initial, observe, journal)
            else:
                method = 'gepa-native-merge' if arm.endswith('-merge') else 'gepa'
                try:
                    selected, proposals, merges, _ = fixture.run_gepa(method, groups, profile, seed, cap, initial, observe)
                except ValueError as error:
                    frames = extract_tb(error.__traceback__)
                    if (method != 'gepa-native-merge' or str(error) != 'Total of weights must be greater than zero'
                            or not any(frame.name == 'find_common_ancestor_pair'
                                       and frame.filename.endswith('/gepa/proposer/merge.py') for frame in frames)):
                        raise
                    failure = {'operation': 'find_common_ancestor_pair', 'message': str(error)}
                    selected, merges = None, []
        outcomes = ({row['id']: score(selected, row, profile).passed for row in groups['holdout']}
                    if selected is not None else None)
        arms[arm] = {
            'chosen': fixture.encode(selected) if selected is not None else None, 'outcomes': outcomes,
            'calls': len(journal) + audit['proposals'], 'transferred': audit['transferred'], 'stale': audit['stale'],
            'mergesAccepted': sum(attempt['accepted'] for attempt in merges),
            'searchSha256': digest([(prompt, case, value.passed) for (prompt, case), value in journal.items()]),
        }
        if failure:
            arms[arm]['failure'] = failure
    return {'seed': seed, 'critical': [row['id'] for row in groups['holdout'] if row['critical']], 'arms': arms}


def summarize(trials):
    totals, comparisons = {}, {}
    for arm in ARMS:
        records = [trial['arms'][arm] for trial in trials]
        completed = [record for record in records if record['outcomes'] is not None]
        totals[arm] = {key: sum(record[key] for record in completed)
                       for key in ('calls', 'mergesAccepted')}
        totals[arm]['passes'] = sum(sum(record['outcomes'].values()) for record in completed)
        totals[arm]['scored'] = sum(len(record['outcomes']) for record in completed)
        totals[arm]['transferred'] = sum(record['transferred'] for record in records)
        totals[arm]['stale'] = sum(record['stale'] for record in records)
        totals[arm]['failedSeeds'] = [trial['seed'] for trial in trials if 'failure' in trial['arms'][arm]]
    for control in (arm for arm in ARMS if arm != PRIMARY):
        critical = delta = saved = cost = paired = 0
        for trial in trials:
            primary, reference = (trial['arms'][arm] for arm in (PRIMARY, control))
            selected, baseline = primary['outcomes'], reference['outcomes']
            if baseline is None:
                continue
            paired += 1
            critical += sum(baseline[case] and not selected[case] for case in trial['critical'])
            delta += sum(selected.values()) - sum(baseline.values())
            cost += reference['calls']
            saved += reference['calls'] - primary['calls']
        comparisons[control] = {'passDelta': delta, 'callsSaved': saved, 'criticalLosses': critical,
                                'pairedTrials': paired,
                                'qualified': paired == len(trials) and not critical and saved >= 0 and
                                             (delta > 0 or delta == 0 and 10 * saved >= cost)}
    return {'totals': totals, 'comparisons': comparisons}


def prepare():
    plan = fixture.prepare()
    root = Path(__file__).resolve().parents[1]
    for name in ('benchmarks/component_dependencies.py', 'cpo/evidence.py'):
        plan['sourceSha256'][name] = sha256((root / name).read_bytes()).hexdigest()
    return {**plan, 'protocol': 'cpo-component-dependencies-v1', 'arms': list(ARMS), 'primary': PRIMARY,
            'seeds': list(SEEDS), 'profiles': list(PROFILES),
            'cohortDigests': {profile: digest([cases(profile, seed) for seed in SEEDS]) for profile in PROFILES}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
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
            results[str(cap)][profile] = {**summarize(trials), 'trials': trials}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
