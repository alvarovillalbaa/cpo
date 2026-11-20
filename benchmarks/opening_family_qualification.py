"""Compare packaged validation-guided repair under a shared adaptive qualification schedule."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_validation_routing as previous
from benchmarks.case_difficulty_allocation import checked_file
from cpo import family_qualification, validation_guided_repair
from cpo._contract import digest


REFERENCE = 'a701ee0d22cfe408d1eec002c020a30d14643175a4d5dff606e20f14fcb804b6'
FRESH_SEEDS = (64951, 64969, 64997, 65003)
SOURCE = previous.SOURCE
TYPED = SOURCE.typed
ARMS = (*TYPED.GEPA, previous.PRIMARY)
INVARIANTS = ('selectedSha256', 'searchLookups', 'proposalCalls', 'nominated', 'promoted', 'holdout')


def prepare():
    upstream, earlier, _ = previous.prepare()
    frozen = checked_file('docs/opening-validation-routing-results-v1.json', REFERENCE)
    if digest(upstream) != frozen['designSha256']:
        raise ValueError('The prior validation routing design changed')
    with patch.object(previous, 'FRESH_SEEDS', FRESH_SEEDS):
        fresh, cohorts, _ = previous.prepare()
    if earlier['confirmation'].keys() & cohorts['confirmation'].keys():
        raise ValueError('The qualification confirmation must use new panels')
    files = {'runner': __file__, 'packageCycle': validation_guided_repair.__file__,
             'packageCertificate': family_qualification.__file__}
    design = {'protocol': 'cpo-opening-family-qualification-v1', 'gepaVersion': upstream['gepaVersion'],
              'sourceSha256': {name: sha256(Path(path).read_bytes()).hexdigest() for name, path in files.items()},
              'referenceReportSha256': REFERENCE, 'confirmationDesignSha256': digest(fresh),
              'confirmationCohortsSha256': fresh['confirmationCohortsSha256'], 'seeds': FRESH_SEEDS,
              'searchCap': upstream['searchCap'], 'gate': upstream['criteria']}
    panels = {'pilot': earlier['confirmation'], 'confirmation': cohorts['confirmation']}
    return design, panels, frozen['results']['phases']['confirmation']


def packaged_cycle(features):
    def run(*args, rounds, train_per_round, **options):
        if train_per_round != 2:
            raise ValueError('The packaged opening uses two probes before fallback')
        return validation_guided_repair.run_validation_guided_repair_cycle(
            *args, input_features=lambda row: features[row.id],
            diagnostic_prompt=SOURCE.repair_api.strip_demonstrations, **options)
    return run


def compare(task, profile, seed, groups):
    seeded = previous.trial(task, profile, seed, groups)
    scheduler = family_qualification.certify_family_qualification
    with (patch.object(TYPED, 'certify_paired_qualification', scheduler),
          patch.object(previous.witness.staged, 'certify_paired_qualification', scheduler)):
        scheduled = previous.trial(task, profile, seed, groups)
    for arm in ARMS:
        if any(seeded['arms'][arm][field] != scheduled['arms'][arm][field] for field in INVARIANTS):
            raise ValueError(f'Changing qualification order altered a decision or search path for {arm}')
    with (patch.object(TYPED, 'FAMILY_FIELD', {key: value[0][0] for key, value in SOURCE.TASKS.items()}),
          patch.object(TYPED.fixture, 'respond', lambda request: SOURCE.opening(profile, request)),
          patch.object(TYPED.programs, 'complete', SOURCE.complete), patch.object(TYPED.feedback, 'observed_repair', SOURCE.repair)):
        features = SOURCE.feature_map(task, groups, True)
        packaged = SOURCE.diagnostic.rerun_repair(task, groups, seed, SOURCE.CAP, packaged_cycle(features))
    if packaged != scheduled['arms'][previous.PRIMARY]:
        raise ValueError('The package changed the scripted candidate or its exact request trace')
    return seeded, scheduled


def measure(cohorts, frozen):
    phases = {}
    for phase, panels in cohorts.items():
        samples = {mode: [] for mode in previous.witness.PHASES}
        for name, (original, alternate, shifted) in panels.items():
            task, profile, seed = name.split('/')
            seed = int(seed)
            samples['held-out'].append(compare(task, profile, seed, original))
            with patch.object(SOURCE, 'FAULTS', shifted):
                samples['shifted-exceptions'].append(compare(task, profile, seed, alternate))
        outcomes = {}
        for mode, pairs in samples.items():
            seeded, scheduled = map(list, zip(*pairs, strict=True))
            control = previous.summarize(seeded)
            if phase == 'pilot' and control != frozen[mode]:
                raise ValueError(f'The published seeded trace changed for {mode}')
            measured = previous.summarize(scheduled)
            outcomes[mode] = {'seeded': {arm: control['totals'][arm] for arm in ARMS}, 'shared': measured,
                              'matchedSelections': {arm: len(pairs) for arm in ARMS}}
        phases[phase] = outcomes
    gate = all(outcome['shared']['comparisons'][arm]['passed'] for outcome in phases['confirmation'].values()
               for arm in TYPED.GEPA)
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
