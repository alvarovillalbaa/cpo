"""Compare routed repair under missing and redundant input features."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import groupby
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_repair_policy_transfer as source
from cpo import routed_repair_cycle
from cpo._contract import digest


TYPED = source.typed
ROOT = Path(__file__).resolve().parents[1]
SEEDS = (60317, 60343, 60373, 60383)
MODES = ('clean', 'missing-field', 'redundant-metadata')
PRIMARY = 'deduplicated-coverage'
POLICIES = ('routed', 'deduplicated', 'coverage', PRIMARY)


def feature_map(task, groups, mode):
    keys = source.TASKS[task][0]
    mapped = {}
    for split in ('train', 'validation'):
        for row in groups[split]:
            inputs = TYPED.fixture.facts(row['input'])
            features = {key: inputs[key] for key in (keys[:-1] if mode == 'missing-field' else keys)}
            if mode == 'redundant-metadata':
                bucket = str(int(digest(row['id']), 16) % 3)
                features.update({f'export_bucket_{column}': bucket for column in range(6)})
            mapped[row['id']] = features
    return mapped


def deduplicate_features(features):
    """Give identical input-column partitions a single vote, even when recoded."""
    names = tuple(dict.fromkeys(name for row in features.values() for name in row))
    seen, kept = set(), []
    missing = object()
    for name in names:
        groups = {}
        column = []
        for row in features.values():
            value = row.get(name, missing)
            if value is missing:
                column.append(-1)
            else:
                column.append(groups.setdefault((type(value), value), len(groups)))
        partition = tuple(column)
        if partition not in seen:
            seen.add(partition)
            kept.append(name)
    return {row_id: {key: row[key] for key in kept if key in row} for row_id, row in features.items()}


def rank_coverage(training, validation, passed, features):
    failed, succeeded = Counter(), Counter()
    for row, outcome in zip(validation, passed, strict=True):
        (succeeded if outcome else failed).update(features(row))
    successes = sum(passed)
    misses = len(passed) - successes
    weights = {key: max(0, count * successes - succeeded[key] * misses) for key, count in failed.items()}
    if not any(weights.values()):
        weights = failed

    remaining = [(row, features(row)) for row in training]
    ranked, covered = [], set()
    while remaining:
        index = max(range(len(remaining)), key=lambda i: sum(weights.get(key, 0) for key in remaining[i][1]
                                                             if key not in covered))
        row, vector = remaining.pop(index)
        ranked.append(row)
        covered.update(vector)
    return ranked


def packaged(features, policy):
    if policy in ('deduplicated', PRIMARY):
        features = deduplicate_features(features)

    def run(*args, rounds, train_per_round, **options):
        return routed_repair_cycle.run_routed_repair_cycle(
            *args, input_features=lambda row: features[row.id],
            diagnostic_prompt=source.api.strip_demonstrations, **options)
    return run


def panels_for(seeds):
    return {f'{task}/{profile}/{seed}': source.make_panel(task, profile, seed)
            for task in source.TASKS for profile in source.PROFILES for seed in seeds}


def prepare():
    prior_seeds = (57143, 57221, 57803, 57839, 58211, 58229, 59107, 59141)
    if set(SEEDS) & set(prior_seeds):
        raise ValueError('This comparison requires disjoint panel seeds')
    panels = panels_for(SEEDS)
    inputs = [row['input'] for all_groups in panels.values() for rows in all_groups.values() for row in rows]
    if len(set(inputs)) != len(inputs):
        raise ValueError('This comparison requires disjoint complete inputs')
    upstream, _ = source.prepare()
    files = {*upstream['sourceSha256'], 'cpo/routed_repair_cycle.py', 'cpo/expected_qualification.py',
             'benchmarks/opening_probe_robustness.py'}
    design = {'protocol': 'cpo-opening-probe-robustness-v1', 'gepaVersion': upstream['gepaVersion'],
              'searchCap': source.CAP, 'seeds': SEEDS, 'modes': MODES, 'policies': POLICIES,
              'primary': PRIMARY, 'gepaGate': upstream['gate'],
              'adoptionGate': ('Preserve every raw-router holdout pass in clean mode and its paired critical passes '
                               'in both stress modes. Beat both GEPA controls on the existing panel gate in every '
                               'mode. In each stress mode, either gain at least eight passes at no added calls or '
                               'match accuracy with at least ten percent fewer calls than raw routing.'),
              'datasetSha256': {name: digest(groups) for name, groups in panels.items()},
              'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(files)}}
    return design, panels


def paired(trials, candidate, control):
    delta = Counter(passDelta=0, criticalLosses=0, pairedLosses=0, panelsWithLoss=0, callDelta=0)
    for trial in trials:
        left, right = (trial['arms'][name] for name in (candidate, control))
        a, b = left['holdout'], right['holdout']
        losses = {key for key, passed in b.items() if passed and not a[key]}
        gain = sum(a.values()) - sum(b.values())
        delta.update(passDelta=gain, criticalLosses=len(losses.intersection(trial['criticalHoldoutIDs'])),
                     pairedLosses=len(losses), panelsWithLoss=int(gain < 0),
                     callDelta=sum(left[key] - right[key] for key in
                                   ('searchLookups', 'qualificationLookups', 'proposalCalls')))
    return dict(delta)


def measure(panels):
    by_mode = {mode: [] for mode in MODES}
    for name, groups in panels.items():
        task, profile, seed = name.split('/')
        seed = int(seed)
        with (patch.object(TYPED, 'FAMILY_FIELD', {key: item[0][0] for key, item in source.TASKS.items()}),
              patch.object(TYPED.fixture, 'respond', source.opening_response(profile)),
              patch.object(TYPED.programs, 'complete', source.complete),
              patch.object(TYPED.feedback, 'observed_repair', source.repair_response)):
            control = TYPED.trial(task, groups, seed, source.CAP)
            for mode in MODES:
                arms = dict(control['arms'])
                features = feature_map(task, groups, mode)
                for policy in POLICIES:
                    rank = rank_coverage if policy in ('coverage', PRIMARY) else routed_repair_cycle._rank_probes
                    with patch.object(routed_repair_cycle, '_rank_probes', rank):
                        arms[policy] = source.diagnostic.rerun_repair(task, groups, seed, source.CAP,
                                                                     packaged(features, policy))
                by_mode[mode].append({**control, 'arms': arms, 'profile': profile})

    results = {}
    for mode, trials in by_mode.items():
        with (patch.object(TYPED, 'ARMS', (*TYPED.ARMS, *POLICIES)),
              patch.object(TYPED, 'CPO', (PRIMARY, 'cpo-adaptive'))):
            results[mode] = TYPED.summary(trials)
        result = results[mode]
        result['vsRouted'] = {policy: paired(trials, policy, 'routed') for policy in POLICIES[1:]}
        result['probeOutcomes'] = {
            policy: dict(Counter(event['status'] for trial in trials for event in trial['arms'][policy]['events']
                                 if event['kind'] == 'routed-probes')) for policy in POLICIES}
        result['traceSha256'] = digest(trials)

    def stress_gate(result):
        scores = result['vsRouted'][PRIMARY]
        totals = result['totals']
        return not scores['criticalLosses'] and (
            (scores['passDelta'] >= 8 and scores['callDelta'] <= 0)
            or (scores['passDelta'] >= 0 and 10 * totals[PRIMARY]['countedCalls']
                <= 9 * totals['routed']['countedCalls']))

    passed = (not results['clean']['vsRouted'][PRIMARY]['pairedLosses']
              and all(stress_gate(results[mode]) for mode in MODES[1:])
              and all(result['comparisons'][arm]['passed'] for result in results.values() for arm in TYPED.GEPA))
    return {'panelsPerMode': len(panels), 'adoptionGatePassed': passed, 'modes': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    design, panels = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        parser.error('Use GEPA 0.1.4')
    results = measure(panels)
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
