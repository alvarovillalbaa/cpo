"""Test reuse of paid training diagnostics across compatible prompt edits."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import component_merge as fixture, frontier
from cpo._contract import digest


SEEDS = tuple(range(57101, 57405, 19))
SAMPLES = (2, 6)
ARMS = ('cpo-rotate', 'cpo-guarded', 'cpo-parent', 'cpo-archive',
        'gepa-guarded', 'gepa-parent', 'gepa-archive', 'gepa-archive-merge')
PRIMARY = 'cpo-archive'


def rank_edits(parent, journal, training, *, archive):
    """Vote from distinct measured examples; keep interaction evidence on its exact parent."""
    current = fixture.encode(parent)
    votes = {}
    for (source, case), outcome in journal.items():
        if case not in training or (not archive and source != current):
            continue
        program = json.loads(source)
        diagnosis = outcome.feedback['diagnosis']
        actions = []
        if source == current and diagnosis == 'The combined repairs conflict on this legacy case':
            actions.extend((family, 'off', 3) for family in ('aggregate', 'precedence'))
        for word in diagnosis.split():
            kind, separator, family = word.partition(':')
            if not separator or family not in parent or program[family] != parent[family]:
                continue
            if kind == 'missing' and parent[family] == 'off':
                actions.extend(((family, 'guarded', 0), (family, 'broad', 0)))
            elif kind == 'regression' and parent[family] == 'broad':
                actions.append((family, 'guarded', 2))
        for action in actions:
            votes.setdefault(action, {})[case] = 1 + int(training[case]['critical'])
    order = {name: index for index, name in enumerate(frontier.FAMILIES)}
    return sorted(votes, key=lambda action: (
        -action[2], -sum(votes[action].values()), order[action[0]], action[1] != 'guarded'))


def next_edit(parent, journal, training, seen, *, archive):
    for family, value, _ in rank_edits(parent, journal, training, archive=archive):
        candidate = {**parent, family: value}
        edge = fixture.encode(parent), fixture.encode(candidate)
        if edge not in seen:
            seen.add(edge)
            return candidate
    return parent


def compare(profile, seed, cap, samples):
    groups = fixture.cases(profile, seed)
    initial = dict.fromkeys(frontier.FAMILIES, 'off')
    training = {row['id']: row for row in groups['train']}
    allowed = {**training, **{row['id']: row for row in groups['validation']}}
    original_proposer = fixture.propose_edit
    results = {}
    for arm in ARMS:
        journal, seen = {}, set()

        def observe(program, case):
            if case not in allowed:
                raise ValueError('Search asked for a holdout case')
            key = fixture.encode(program), case
            if key not in journal:
                if len(journal) >= cap:
                    raise fixture.BudgetReached
                journal[key] = fixture.score(program, allowed[case], profile)
            return journal[key]

        def proposer(parent, slot, phase):
            if arm == 'cpo-rotate':
                return original_proposer(parent, slot, phase)
            if arm.endswith('-guarded'):
                return original_proposer(parent, slot, 'reverse-precedence')
            return next_edit(parent, journal, training, seen, archive='archive' in arm)

        with patch.object(fixture, 'propose_edit', proposer), patch.object(fixture, 'MINIBATCH', samples):
            if arm.startswith('cpo'):
                selected, proposals, attempts, _ = fixture.run_cpo(
                    'cpo-ordinary', groups, profile, seed, cap, initial, observe, journal)
            else:
                method = 'gepa-native-merge' if arm.endswith('-merge') else 'gepa'
                selected, proposals, attempts, _ = fixture.run_gepa(
                    method, groups, profile, seed, cap, initial, observe)
        outcomes = {row['id']: fixture.score(selected, row, profile).passed for row in groups['holdout']}
        results[arm] = {'chosen': fixture.encode(selected), 'outcomes': outcomes,
                        'evaluations': len(journal), 'trainingLookups': sum(case in training for _, case in journal),
                        'reflectedSlots': len(proposals), 'merges': attempts,
                        'searchSha256': digest([(prompt, case, value.passed) for (prompt, case), value in journal.items()])}
    return {'seed': seed, 'critical': [row['id'] for row in groups['holdout'] if row['critical']], 'arms': results}


def summarize(trials):
    totals, comparisons = {}, {}
    for arm in ARMS:
        samples = [trial['arms'][arm] for trial in trials]
        totals[arm] = {'passes': sum(sum(item['outcomes'].values()) for item in samples),
                       'calls': sum(item['evaluations'] + item['reflectedSlots'] for item in samples),
                       'trainingLookups': sum(item['trainingLookups'] for item in samples),
                       'mergesAccepted': sum(merge['accepted'] for item in samples for merge in item['merges'])}
    primary = totals[PRIMARY]
    for control in (name for name in ARMS if name != PRIMARY):
        baseline = totals[control]
        gain, saved = primary['passes'] - baseline['passes'], baseline['calls'] - primary['calls']
        critical = 0
        for trial in trials:
            new, old = (trial['arms'][arm]['outcomes'] for arm in (PRIMARY, control))
            critical += sum(old[case] and not new[case] for case in trial['critical'])
        comparisons[control] = {'passDelta': gain, 'callsSaved': saved, 'criticalLosses': critical,
                                'qualified': not critical and saved >= 0 and
                                             (gain > 0 or gain == 0 and 10 * saved >= baseline['calls'])}
    return {'totals': totals, 'comparisons': comparisons}


def prepare():
    base = fixture.prepare()
    del base['reflectionMinibatch']
    return {**base, 'protocol': 'cpo-component-feedback-v1', 'seeds': list(SEEDS), 'arms': list(ARMS),
            'primary': PRIMARY, 'reflectionMinibatches': list(SAMPLES),
            'cohortDigests': {profile: digest([fixture.cases(profile, seed) for seed in SEEDS])
                              for profile in fixture.PROFILES},
            'sourceSha256': {**base['sourceSha256'],
                             'benchmarks/component_feedback.py': sha256(Path(__file__).read_bytes()).hexdigest()}}


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
    for samples in plan['reflectionMinibatches']:
        caps = results[str(samples)] = {}
        for cap in plan['caps']:
            profiles = caps[str(cap)] = {}
            for profile in plan['profiles']:
                trials = [compare(profile, seed, cap, samples) for seed in plan['seeds']]
                profiles[profile] = {**summarize(trials), 'trials': trials}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
