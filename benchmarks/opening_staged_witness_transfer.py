"""Transfer the shorter opening probe batch to disjoint interaction panels."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import opening_staged_repairs as staged
from benchmarks.case_difficulty_allocation import checked_file
from benchmarks.opening_probe_robustness import paired
from cpo._contract import digest


REFERENCE = '6bcaa61e08d1b2c32010ccc99ef37e30a574c87e3219aa07909d95551f465189'
SEEDS = (63311, 63317, 63331, 63347)
PHASES = ('held-out', 'shifted-exceptions')
PRIMARY = 'single-opening-witness'
SOURCE = staged.previous


def faults(task, seed):
    rng = Random(f'fault-location/{task}/{seed}')
    locations = tuple(SOURCE.feature_key((rng.randrange(3), rng.randrange(3))) for _ in range(3))
    return {profile: tuple((field, locations[field]) for field, _ in entries)
            for profile, entries in SOURCE.FAULTS.items()}


def prepare():
    upstream, previous, _ = staged.prepare()
    frozen = checked_file('docs/opening-staged-repairs-results-v1.json', REFERENCE)
    if upstream['datasetSha256'] != frozen['design']['datasetSha256']:
        raise ValueError('The prior staged transfer cohort changed')
    panels = {}
    for task in SOURCE.TASKS:
        for seed in SEEDS:
            shifted = faults(task, seed)
            for profile in SOURCE.FAULTS:
                original = SOURCE.panel(task, profile, seed)
                alternative = {split: [{**row, 'critical': row['critical'] or any(
                    SOURCE.conjunctions(task, row['input'])[field] == key for field, key in shifted[profile])}
                    for row in rows] for split, rows in original.items()}
                panels[f'{task}/{profile}/{seed}'] = (original, alternative, shifted)
    prior_inputs = {row['input'] for cohort in previous.values() for groups in cohort.values()
                    for rows in groups.values() for row in rows}
    inputs = [row['input'] for groups, _, _ in panels.values() for rows in groups.values() for row in rows]
    if len(set(inputs)) != len(inputs) or prior_inputs.intersection(inputs):
        raise ValueError('The confirmation needs distinct inputs outside the prior cohorts')
    design = {'protocol': 'cpo-opening-staged-witness-transfer-v1', 'gepaVersion': upstream['gepaVersion'],
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'stagedDesignSha256': digest(upstream), 'referenceReportSha256': REFERENCE,
              'primary': PRIMARY, 'seeds': SEEDS, 'modes': PHASES, 'searchCap': upstream['searchCap'],
              'criteria': 'The single opening witness arm must clear both existing GEPA gates in each mode.',
              'cohortsSha256': {name: digest(panel) for name, panel in panels.items()}}
    return design, panels, previous['transfer'], frozen['results']['transfer']


def trial(task, profile, seed, groups):
    typed = SOURCE.typed
    baseline = staged.compare(task, profile, seed, groups)
    with (patch.object(typed, 'FAMILY_FIELD', {key: value[0][0] for key, value in SOURCE.TASKS.items()}),
          patch.object(typed.fixture, 'respond', lambda request: SOURCE.opening(profile, request)),
          patch.object(typed.programs, 'complete', SOURCE.complete), patch.object(typed.feedback, 'observed_repair', SOURCE.repair)):
        features = SOURCE.feature_map(task, groups, True)
        baseline['arms'][PRIMARY] = SOURCE.diagnostic.rerun_repair(
            task, groups, seed, SOURCE.CAP, staged.cycle(features, opening_witness_only=True))
    return baseline


def summarize(trials):
    typed = SOURCE.typed
    with (patch.object(typed, 'ARMS', (*typed.ARMS, SOURCE.ATOMIC, SOURCE.PRIMARY, staged.PRIMARY, PRIMARY)),
          patch.object(typed, 'CPO', (PRIMARY, staged.PRIMARY))):
        result = typed.summary(trials)
        result['profiles'] = {profile: typed.summary([record for record in trials if record['profile'] == profile])
                              for profile in SOURCE.FAULTS}
    result['vsStaged'] = paired(trials, PRIMARY, staged.PRIMARY)
    result['traceSha256'] = digest(trials)
    result['minimumPasses'] = min(sum(record['arms'][PRIMARY]['holdout'].values()) for record in trials)
    return result


def measure(panels, previous_panels, frozen):
    samples = {mode: [] for mode in (*PHASES, 'observed-transfer')}
    for name, (original, alternate, shifted) in panels.items():
        task, profile, seed = name.split('/')
        seed = int(seed)
        samples['held-out'].append(trial(task, profile, seed, original))
        with patch.object(SOURCE, 'FAULTS', shifted):
            samples['shifted-exceptions'].append(trial(task, profile, seed, alternate))
    for name, groups in previous_panels.items():
        task, profile, seed = name.split('/')
        samples['observed-transfer'].append(trial(task, profile, int(seed), groups))
    results = {mode: summarize(records) for mode, records in samples.items()}
    if any(results['observed-transfer']['totals'][arm] != value for arm, value in frozen['totals'].items()):
        raise ValueError('A published transfer control changed')
    gate = all(results[mode]['comparisons'][arm]['passed'] for mode in PHASES for arm in SOURCE.typed.GEPA)
    return {'confirmationGatePassed': gate, 'modes': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    design, panels, previous, frozen = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        parser.error('Use GEPA 0.1.4')
    result = measure(panels, previous, frozen)
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': result}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
