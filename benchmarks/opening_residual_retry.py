"""Test a bounded training retry after a residual miss and passing routed probes."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_family_qualification as previous
from benchmarks.case_difficulty_allocation import checked_file
from benchmarks.opening_probe_robustness import paired
from cpo import validation_guided_repair
from cpo._contract import digest


REFERENCE = '6914dc8774ebdafdf332c6b774658e4cdfeb261176e423e32439a8105225f30c'
FRESH_SEEDS = (65521, 65537, 65543, 65551)
RETRY_LIMIT = 8
PRIMARY = 'residual-retry'
BASELINE = previous.previous.PRIMARY
SOURCE = previous.SOURCE
TYPED = SOURCE.typed


def prepare():
    prior, old, _ = previous.prepare()
    frozen = checked_file('docs/opening-family-qualification-results-v1.json', REFERENCE)
    if prior['confirmationCohortsSha256'] != frozen['design']['confirmationCohortsSha256']:
        raise ValueError('The previous confirmation inputs changed')
    with patch.object(previous, 'FRESH_SEEDS', FRESH_SEEDS):
        fresh, panels, _ = previous.prepare()
    if old['confirmation'].keys() & panels['confirmation'].keys():
        raise ValueError('The retry confirmation cannot reuse a known panel')
    design = {'protocol': 'cpo-opening-residual-retry-v1', 'gepaVersion': prior['gepaVersion'],
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'referenceReportSha256': REFERENCE, 'confirmationDesignSha256': digest(fresh),
              'confirmationCohortsSha256': fresh['confirmationCohortsSha256'], 'seeds': FRESH_SEEDS,
              'searchCap': prior['searchCap'], 'retryCapPerCycle': RETRY_LIMIT,
              'gate': 'Clear both shared-schedule GEPA gates and preserve baseline holdout passes in both fresh modes.'}
    return design, {'pilot': old['confirmation'], 'confirmation': panels['confirmation']}, frozen['results']['phases']['confirmation']


def retry_cycle(features):
    def run(*args, rounds, train_per_round, **options):
        return validation_guided_repair.run_validation_guided_repair_cycle(
            *args, input_features=lambda row: features[row.id], diagnostic_prompt=SOURCE.repair_api.strip_demonstrations,
            retry_probe_limit=RETRY_LIMIT, **options)
    return run


def compare(task, profile, seed, groups):
    _, baseline = previous.compare(task, profile, seed, groups)
    with (patch.object(TYPED, 'FAMILY_FIELD', {key: value[0][0] for key, value in SOURCE.TASKS.items()}),
          patch.object(TYPED.fixture, 'respond', lambda request: SOURCE.opening(profile, request)),
          patch.object(TYPED.programs, 'complete', SOURCE.complete), patch.object(TYPED.feedback, 'observed_repair', SOURCE.repair)):
        features = SOURCE.feature_map(task, groups, True)
        challenger = SOURCE.diagnostic.rerun_repair(task, groups, seed, SOURCE.CAP, retry_cycle(features))
    return {**baseline, 'arms': {**baseline['arms'], PRIMARY: challenger}}


def summarize(trials):
    with patch.object(TYPED, 'ARMS', (BASELINE, PRIMARY, *TYPED.GEPA)), patch.object(TYPED, 'CPO', (PRIMARY, BASELINE)):
        outcome = TYPED.summary(trials)
    outcome['vsBaseline'] = paired(trials, PRIMARY, BASELINE)
    outcome['traceSha256'] = digest(trials)
    intervention = {}
    for trial in trials:
        arm = trial['arms'][PRIMARY]
        stages = [stage for event in arm['events'] for stage in event.get('stages', ())]
        found = [stage for stage in stages if stage.get('retryRows')]
        if not found:
            continue
        count = sum(len(stage['retryRows']) for stage in found)
        if count > RETRY_LIMIT:
            raise ValueError('A cycle exceeded its retry probe allowance')
        key = f"{trial['task']}/{trial['profile']}/{trial['seed']}"
        intervention[key] = {'extraProbes': count, 'foundFailure': any(stage['failedRows'] for stage in found),
                             'passDelta': sum(arm['holdout'].values()) - sum(trial['arms'][BASELINE]['holdout'].values())}
    outcome['retries'] = intervention
    return outcome


def measure(cohorts, frozen):
    phases = {}
    for phase, panels in cohorts.items():
        modes = {mode: [] for mode in previous.previous.witness.PHASES}
        for name, (original, alternate, shifted) in panels.items():
            task, profile, seed = name.split('/')
            seed = int(seed)
            modes['held-out'].append(compare(task, profile, seed, original))
            with patch.object(SOURCE, 'FAULTS', shifted):
                modes['shifted-exceptions'].append(compare(task, profile, seed, alternate))
        summaries = {}
        for mode, trials in modes.items():
            if phase == 'pilot':
                original = [{**trial, 'arms': {key: value for key, value in trial['arms'].items() if key != PRIMARY}}
                            for trial in trials]
                if digest(original) != frozen[mode]['shared']['traceSha256']:
                    raise ValueError(f'The published baseline trace changed for {mode}')
            summaries[mode] = summarize(trials)
        phases[phase] = summaries
    gate = all(not outcome['vsBaseline']['pairedLosses'] and all(outcome['comparisons'][arm]['passed']
                                                                for arm in TYPED.GEPA)
               for outcome in phases['confirmation'].values())
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
    results = measure(cohorts, frozen)
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
