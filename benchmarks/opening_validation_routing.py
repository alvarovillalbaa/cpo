"""Use paid validation misses to route the next staged training probe."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_staged_witness_transfer as witness
from benchmarks.case_difficulty_allocation import checked_file
from benchmarks.opening_probe_robustness import paired
from cpo._contract import digest


REFERENCE = '39e27dfcd2f18f26ca365a237c1562841b3f060fa3ec938e0f5feb34a11af4b6'
FRESH_SEEDS = (64109, 64123, 64151, 64157)
PROBE_LIMIT = 4
PRIMARY = 'validation-routed'
SOURCE = witness.SOURCE


def prepare():
    upstream, development, _, _ = witness.prepare()
    frozen = checked_file('docs/opening-staged-witness-transfer-results-v1.json', REFERENCE)
    if upstream['cohortsSha256'] != frozen['design']['cohortsSha256']:
        raise ValueError('The witnessed development cohort changed')
    with patch.object(witness, 'SEEDS', FRESH_SEEDS):
        new, confirmation, _, _ = witness.prepare()
    if development.keys() & confirmation.keys():
        raise ValueError('The confirmation cannot reuse a development panel')
    design = {'protocol': 'cpo-opening-validation-routing-v1', 'gepaVersion': new['gepaVersion'],
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'referenceReportSha256': REFERENCE, 'confirmationDesignSha256': digest(new),
              'searchCap': new['searchCap'], 'seeds': FRESH_SEEDS, 'primary': PRIMARY, 'maximumRoutedProbes': PROBE_LIMIT,
              'criteria': 'Meet both original GEPA gates across both fresh fault modes.',
              'confirmationCohortsSha256': new['cohortsSha256']}
    return design, {'development': development, 'confirmation': confirmation}, frozen['results']['modes']


def trial(task, profile, seed, groups):
    typed = SOURCE.typed
    record = witness.trial(task, profile, seed, groups)
    with (patch.object(typed, 'FAMILY_FIELD', {key: value[0][0] for key, value in SOURCE.TASKS.items()}),
          patch.object(typed.fixture, 'respond', lambda request: SOURCE.opening(profile, request)),
          patch.object(typed.programs, 'complete', SOURCE.complete), patch.object(typed.feedback, 'observed_repair', SOURCE.repair)):
        features = SOURCE.feature_map(task, groups, True)
        cycle = witness.staged.cycle(features, opening_witness_only=True, validation_probe_limit=PROBE_LIMIT)
        record['arms'][PRIMARY] = SOURCE.diagnostic.rerun_repair(task, groups, seed, SOURCE.CAP, cycle)
    return record


def summarize(trials):
    typed = SOURCE.typed
    arms = (*typed.ARMS, SOURCE.ATOMIC, SOURCE.PRIMARY, witness.staged.PRIMARY, witness.PRIMARY, PRIMARY)
    with patch.object(typed, 'ARMS', arms), patch.object(typed, 'CPO', (PRIMARY, witness.PRIMARY)):
        result = typed.summary(trials)
    result['vsFirstWitness'] = paired(trials, PRIMARY, witness.PRIMARY)
    result['traceSha256'] = digest(trials)
    result['minimumPasses'] = min(sum(record['arms'][PRIMARY]['holdout'].values()) for record in trials)
    result['residualChecks'] = sum(len(event.get('residualChecks', ())) for record in trials
                                   for event in record['arms'][PRIMARY]['events'])
    return result


def measure(cohorts, frozen):
    phases = {}
    for phase, panels in cohorts.items():
        samples = {mode: [] for mode in witness.PHASES}
        for name, (original, alternative, shifted) in panels.items():
            task, profile, seed = name.split('/')
            seed = int(seed)
            samples['held-out'].append(trial(task, profile, seed, original))
            with patch.object(SOURCE, 'FAULTS', shifted):
                samples['shifted-exceptions'].append(trial(task, profile, seed, alternative))
        outcomes = {mode: summarize(trials) for mode, trials in samples.items()}
        if phase == 'development':
            for mode, summary in outcomes.items():
                if any(summary['totals'][arm] != prior for arm, prior in frozen[mode]['totals'].items()):
                    raise ValueError(f'The published control changed for {mode}')
        phases[phase] = outcomes
    gate = all(result['comparisons'][arm]['passed'] for result in phases['confirmation'].values()
               for arm in SOURCE.typed.GEPA)
    return {'confirmationGatePassed': gate, 'phases': phases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    design, cohorts, frozen = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        parser.error('Use GEPA 0.1.4')
    result = measure(cohorts, frozen)
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': result}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
