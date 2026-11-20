"""Compare the integrated final validation certificate on disjoint fixture panels."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_residual_retry as retry, opening_staged_witness_transfer as panels
from cpo._contract import digest
from cpo.family_qualification import certify_family_qualification
from cpo.validation_guided_repair import run_validation_guided_repair_cycle


ROOT = Path(__file__).resolve().parents[1]
SEEDS = (66103, 66107, 66109, 66137)
FULL = 'full-validation'
CERTIFICATE = 'exact-certificate'
SOURCE = retry.SOURCE
TYPED = retry.TYPED
REFERENCE = 'baec6f42969cfb15e164bcdfdda88ab0a4a1613943c8dd38ab49de78192c9b40'


def prepare():
    earlier = retry.checked_file('docs/opening-validation-certificate-results-v1.json', REFERENCE)
    _, known, _ = retry.prepare()
    with patch.object(panels, 'SEEDS', SEEDS):
        _, fresh, _, _ = panels.prepare()
    known_inputs = {row['input'] for group in known.values() for rows, _, _ in group.values()
                    for split in rows.values() for row in split}
    if any(row['input'] in known_inputs for rows, _, _ in fresh.values() for split in rows.values() for row in split):
        raise ValueError('Fresh certificate panels overlap the prior proof replay')
    names = ('benchmarks/opening_validation_certificate_transfer.py', 'benchmarks/opening_interaction_transfer.py',
             'benchmarks/opening_staged_witness_transfer.py', 'benchmarks/opening_screen_typed.py',
             'cpo/optimizer.py', 'cpo/validation_guided_repair.py', 'cpo/anchored_validation.py',
             'cpo/family_qualification.py', 'requirements-benchmark.txt')
    cohorts = {**known, 'fresh': fresh}
    design = {'protocol': 'cpo-opening-validation-certificate-transfer-v1', 'gepaVersion': '0.1.4',
              'freshSeeds': SEEDS, 'retryProbeCap': retry.RETRY_LIMIT, 'searchCap': SOURCE.CAP,
              'earlierReplaySha256': REFERENCE, 'cohortSha256': {key: digest(value) for key, value in cohorts.items()},
              'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in names},
              'gate': ('Match full CPO decisions and critical passes. Against both GEPA modes preserve every '
                       'panel, pass at least 14 cases per panel, and gain at least eight passes at no added '
                       'calls or spend at least ten percent fewer calls.')}
    return design, cohorts, earlier['results']


def compare(task, profile, seed, groups):
    traces = {FULL: [], CERTIFICATE: []}

    def cycle(arm):
        def run(incumbent, train, validation, holdout, evaluate, propose, *, rounds, train_per_round, **options):
            def observe(prompt, row):
                answer = evaluate(prompt, row)
                traces[arm].append((prompt, row.id, answer.passed, answer.matched_fields))
                return answer

            return run_validation_guided_repair_cycle(
                incumbent, train, validation, holdout, observe, propose,
                input_features=lambda row: features[row.id], diagnostic_prompt=SOURCE.repair_api.strip_demonstrations,
                retry_probe_limit=retry.RETRY_LIMIT, certify_final_draft=arm == CERTIFICATE, **options)

        return run

    features = SOURCE.feature_map(task, groups, True)
    with (patch.object(TYPED, 'FAMILY_FIELD', {key: value[0][0] for key, value in SOURCE.TASKS.items()}),
          patch.object(TYPED.fixture, 'respond', lambda request: SOURCE.opening(profile, request)),
          patch.object(TYPED.programs, 'complete', SOURCE.complete), patch.object(TYPED.feedback, 'observed_repair', SOURCE.repair),
          patch.object(TYPED, 'certify_paired_qualification', certify_family_qualification)):
        with patch.object(TYPED, 'ARMS', TYPED.GEPA):
            record = TYPED.trial(task, groups, seed, SOURCE.CAP)
        for arm in (FULL, CERTIFICATE):
            record['arms'][arm] = SOURCE.diagnostic.rerun_repair(task, groups, seed, SOURCE.CAP, cycle(arm))

    full, proof = (record['arms'][name] for name in (FULL, CERTIFICATE))
    if {key: value for key, value in proof.items() if key not in ('searchLookups', 'journalSha256')} != {
        key: value for key, value in full.items() if key not in ('searchLookups', 'journalSha256')
    }:
        raise ValueError('The integrated proof changed a repair or qualification decision')
    if len(traces[FULL]) != full['searchLookups'] or len(traces[CERTIFICATE]) != proof['searchLookups']:
        raise ValueError('Reported search costs differ from the executed callbacks')
    if not set(traces[CERTIFICATE]) <= set(traces[FULL]):
        raise ValueError('The certificate requested validation outside the measured policy')
    record['lookupsSaved'] = full['searchLookups'] - proof['searchLookups']
    return record


def measure(cohorts, earlier):
    results = {}
    for phase, groups in cohorts.items():
        modes = {mode: {} for mode in panels.PHASES}
        for name, (original, alternate, shifted) in groups.items():
            task, profile, seed = name.split('/')
            modes['held-out'][name] = compare(task, profile, int(seed), original)
            with patch.object(SOURCE, 'FAULTS', shifted):
                modes['shifted-exceptions'][name] = compare(task, profile, int(seed), alternate)
        results[phase] = {}
        for mode, records in modes.items():
            with patch.object(TYPED, 'ARMS', (CERTIFICATE, FULL, *TYPED.GEPA)), patch.object(TYPED, 'CPO', (CERTIFICATE, FULL)):
                summary = TYPED.summary(tuple(records.values()))
            if phase in earlier:
                reference = earlier[phase][mode]
                expected = {name: entry['originalReads'] - entry['certificateReads']
                            for name, entry in reference['byPanel'].items()}
                if (summary['totals'][FULL] != reference['original'] or any(
                    record['lookupsSaved'] != expected.get(name, 0) for name, record in records.items()
                ) or any(summary['totals'][arm]['countedCalls'] != value for arm, value in reference['gepaCountedCalls'].items())):
                    raise ValueError('Integrated calls do not reproduce the earlier terminal audit')
            results[phase][mode] = {**summary, 'panels': len(records), 'traceSha256': digest(records),
                                    'lookupsSavedByPanel': {name: row['lookupsSaved'] for name, row in records.items()}}
    gate = all(summary['comparisons'][arm]['passed'] for summary in results['fresh'].values() for arm in TYPED.GEPA)
    return {'freshGatePassed': gate, 'cohorts': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    design, cohorts, earlier = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != design['gepaVersion']:
        parser.error('Use the current seal, pinned GEPA, and a fresh output path')
    report = {'design': design, 'designSha256': seal, 'results': measure(cohorts, earlier)}
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
