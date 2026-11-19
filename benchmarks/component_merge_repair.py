"""Test training-counterexample repairs before guarded component validation."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import component_merge as original, frontier
from cpo._contract import digest


SEEDS = tuple(range(55201, 55505, 19))
PROBES = 4
ARMS = ('cpo-ordinary', 'cpo-merge', 'cpo-probe-reserve', 'cpo-probe-veto', 'cpo-probe-repair',
        'cpo-spare-repair', 'gepa', 'gepa-native-merge')
PRIMARY = 'cpo-probe-repair'


class SkipMerge(Exception):
    """Keep the planned search winner after an unfunded or vetoed merge."""


def repair_from_training(program, probes, observe, *, repair):
    """Guard only components named by a measured training regression."""
    regressed = set()
    for case in probes:
        diagnosis = observe(program, case).feedback['diagnosis']
        if diagnosis == 'The combined repairs conflict on this legacy case':
            return None
        regressed.update(word.removeprefix('regression:') for word in diagnosis.split()
                         if word.startswith('regression:'))
        if regressed and not repair:
            return None
    return {key: 'guarded' if key in regressed and value == 'broad' else value for key, value in program.items()}


def run_cpo(arm, groups, profile, seed, cap, initial, observe, journal):
    if arm in ('cpo-ordinary', 'cpo-merge'):
        return original.run_cpo(arm, groups, profile, seed, cap, initial, observe, journal)
    probes = [row['id'] for row in groups['train'] if row['critical']][:PROBES]
    spare_only = arm == 'cpo-spare-repair'
    search_policy = 'cpo-ordinary' if spare_only else 'cpo-reserved'
    allowance = cap if spare_only else cap - len(probes)
    captured = []

    def capture(*args, **kwargs):
        result = original_search(*args, **kwargs)
        captured.append(result)
        return result

    original_search = original.search
    with patch.object(original, 'search', capture):
        selected, proposals, _, premerge = original.run_cpo(search_policy, groups, profile, seed, allowance,
                                                               initial, observe, journal)
    if arm == 'cpo-probe-reserve':
        return selected, proposals, [], premerge
    validation = [row['id'] for row in groups['validation']]
    evidence = {}
    candidate = None
    before = len(journal)

    def preflight(program, row):
        nonlocal candidate
        if not evidence:
            evidence['originalCandidate'] = original.encode(program)
            if cap - len(journal) < len(validation) + len(probes):
                evidence['status'] = 'unfunded'
                raise SkipMerge
            candidate = repair_from_training(program, probes, observe, repair=arm != 'cpo-probe-veto')
            evidence['trainingLookups'] = len(journal) - before
            if candidate is None:
                evidence['status'] = 'training-veto'
                raise SkipMerge
            evidence['candidate'] = original.encode(candidate)
            evidence['repaired'] = candidate != program
        return observe(candidate, row)

    try:
        _, attempt = original.attempt_merge(captured[0], validation, preflight, journal)
    except SkipMerge:
        attempt = None
    if not evidence:
        return selected, proposals, [], premerge
    if attempt is not None:
        evidence.update(parents=attempt['parents'], preserved=attempt['preserved'],
                        status='accepted' if attempt['preserved'] else 'validation-veto')
        if attempt['preserved']:
            selected = candidate
    evidence['evaluations'] = len(journal) - before
    return selected, proposals, [evidence], premerge


def compare(profile, seed, cap):
    groups = original.cases(profile, seed)
    initial = dict.fromkeys(frontier.FAMILIES, 'off')
    search_rows = {row['id']: row for group in ('train', 'validation') for row in groups[group]}
    arms = {}
    for arm in ARMS:
        journal = {}

        def observe(program, row):
            if row not in search_rows:
                raise ValueError('Search accessed a holdout case')
            key = original.encode(program), row
            if key not in journal:
                if len(journal) >= cap:
                    raise original.BudgetReached
                journal[key] = original.score(program, search_rows[row], profile)
            return journal[key]

        if arm.startswith('cpo'):
            selected, proposals, attempts, premerge = run_cpo(arm, groups, profile, seed, cap, initial, observe, journal)
        else:
            selected, proposals, attempts, premerge = original.run_gepa(arm, groups, profile, seed, cap, initial, observe)
        outcomes = {row['id']: original.score(selected, row, profile).passed for row in groups['holdout']}
        arms[arm] = {'chosen': original.encode(selected), 'beforeMerge': premerge, 'outcomes': outcomes,
                     'evaluations': len(journal), 'reflectedSlots': len(proposals), 'merges': attempts,
                     'searchSha256': digest([(prompt, row, result.passed) for (prompt, row), result in journal.items()])}
    return {'seed': seed, 'critical': [row['id'] for row in groups['holdout'] if row['critical']], 'arms': arms}


def summarize(trials):
    totals, comparisons = {}, {}
    for arm in ARMS:
        results = [trial['arms'][arm] for trial in trials]
        attempts = [attempt for result in results for attempt in result['merges']]
        totals[arm] = {'passes': sum(sum(item['outcomes'].values()) for item in results),
                       'calls': sum(item['evaluations'] + item['reflectedSlots'] for item in results),
                       'mergeCandidates': len(attempts),
                       'mergesAccepted': sum(attempt.get('accepted', attempt.get('preserved', False))
                                             for attempt in attempts),
                       'unfunded': sum(attempt.get('status') == 'unfunded' for attempt in attempts)}
    for contender in (PRIMARY, 'cpo-spare-repair'):
        comparisons[contender] = {}
        for control in (name for name in ARMS if name != contender):
            a, b = (totals[name] for name in (contender, control))
            gain, saved = a['passes'] - b['passes'], b['calls'] - a['calls']
            losses = 0
            for trial in trials:
                current, original_item = (trial['arms'][name]['outcomes'] for name in (contender, control))
                losses += sum(original_item[row] and not current[row] for row in trial['critical'])
            comparisons[contender][control] = {'passDelta': gain, 'callsSaved': saved, 'criticalLosses': losses,
                                               'qualified': not losses and saved >= 0 and
                                                            (gain > 0 or gain == 0 and 10 * saved >= b['calls'])}
    return {'totals': totals, 'comparisons': comparisons}


def prepare():
    base = original.prepare()
    return {**base, 'protocol': 'cpo-component-merge-repair-v1', 'seeds': list(SEEDS), 'arms': list(ARMS),
            'primary': PRIMARY, 'maximumTrainingProbes': PROBES,
            'cohortDigests': {profile: digest([original.cases(profile, seed) for seed in SEEDS])
                              for profile in original.PROFILES},
            'sourceSha256': {**base['sourceSha256'],
                             'benchmarks/component_merge_repair.py': sha256(Path(__file__).read_bytes()).hexdigest()}}


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
