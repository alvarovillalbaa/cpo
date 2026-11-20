"""Check the same final-draft certificate with tighter families first."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_validation_certificate_transfer as reference
from cpo import validation_guided_repair as repair
from cpo._contract import digest
from cpo.anchored_validation import certify_validation_gain


SEEDS = (66713, 66721, 66733, 66739)
BASELINE = reference.CERTIFICATE
ORDERED = 'tight-family-certificate'
SOURCE, TYPED = reference.SOURCE, reference.TYPED


def tight_family_certificate(rows, anchor_passes, evaluate, *, known=None):
    rows = tuple(rows)
    prior = {} if known is None else known
    slack = Counter()
    for row in rows:
        slack[row.family] += not anchor_passes[row.id]
        slack[row.family] -= row.id in prior and not prior[row.id]
    order = sorted(rows, key=lambda row: slack[row.family])
    return certify_validation_gain(order, anchor_passes, evaluate, known=known)


def prepare():
    known_seeds = (*SOURCE.SEEDS, *reference.panels.SEEDS, *reference.panels.staged.FRESH_SEEDS,
                   *reference.SEEDS, *reference.retry.FRESH_SEEDS)
    if set(SEEDS).intersection(known_seeds):
        raise ValueError('The final validation comparison must use new panel seeds')
    groups = {}
    distinct_inputs = set()
    for task in SOURCE.TASKS:
        for seed in SEEDS:
            shifted = reference.panels.faults(task, seed)
            for profile in SOURCE.FAULTS:
                original = SOURCE.panel(task, profile, seed)
                for rows in original.values():
                    for row in rows:
                        if row['input'] in distinct_inputs:
                            raise ValueError('The final validation comparison reused an input')
                        distinct_inputs.add(row['input'])
                alternate = {split: [{**row, 'critical': row['critical'] or any(
                    SOURCE.conjunctions(task, row['input'])[field] == key for field, key in shifted[profile])}
                    for row in rows] for split, rows in original.items()}
                groups[f'{task}/{profile}/{seed}'] = (original, alternate, shifted)

    root = Path(__file__).resolve().parents[1]
    paths = [Path(module.__file__) for module in (reference, reference.panels, SOURCE, TYPED, repair)]
    paths.extend(root / name for name in ('cpo/anchored_validation.py', 'cpo/family_qualification.py',
                                          'cpo/opening_screen_cycle.py', 'cpo/optimizer.py', 'requirements-benchmark.txt'))
    paths.append(Path(__file__))
    design = {'protocol': 'cpo-opening-final-validation-order-v1', 'gepaVersion': '0.1.4',
              'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
              'freshCohortSha256': digest(groups), 'freshSeeds': SEEDS, 'searchCap': SOURCE.CAP,
              'schedule': 'preserve known and critical priority, then ascending family upper bound',
              'archivedScheduleBefore': 'original row order within known and critical groups',
              'decision': 'exactly preserve original nomination, admission and holdout replies',
              'costGate': 'use no more reads in either fresh mode and fewer in at least one'}
    return design, groups


def compare(task, profile, seed, groups):
    result = reference.compare(task, profile, seed, groups)
    features = SOURCE.feature_map(task, groups, True)

    def cycle(*args, rounds, train_per_round, **options):
        return repair.run_validation_guided_repair_cycle(
            *args, input_features=lambda row: features[row.id], diagnostic_prompt=SOURCE.repair_api.strip_demonstrations,
            retry_probe_limit=reference.retry.RETRY_LIMIT, certify_final_draft=True, **options)

    with (patch.object(TYPED, 'FAMILY_FIELD', {key: value[0][0] for key, value in SOURCE.TASKS.items()}),
          patch.object(TYPED.fixture, 'respond', lambda request: SOURCE.opening(profile, request)),
          patch.object(TYPED.programs, 'complete', SOURCE.complete),
          patch.object(TYPED.feedback, 'observed_repair', SOURCE.repair),
          patch.object(TYPED, 'certify_paired_qualification', reference.certify_family_qualification),
          patch.object(repair, 'certify_validation_gain', tight_family_certificate)):
        result['arms'][ORDERED] = SOURCE.diagnostic.rerun_repair(task, groups, seed, SOURCE.CAP, cycle)

    def stable(arm):
        return {key: value for key, value in arm.items() if key not in ('searchLookups', 'journalSha256')}
    if stable(result['arms'][BASELINE]) != stable(result['arms'][ORDERED]):
        raise ValueError('A family-order change affected a decision or witnessed outcome')
    return result


def measure(groups):
    modes = {mode: {} for mode in reference.panels.PHASES}
    for name, (original, alternate, shifted) in groups.items():
        task, profile, seed = name.split('/')
        modes['held-out'][name] = compare(task, profile, int(seed), original)
        with patch.object(SOURCE, 'FAULTS', shifted):
            modes['shifted-exceptions'][name] = compare(task, profile, int(seed), alternate)

    outcomes = {}
    for mode, records in modes.items():
        arms = (ORDERED, BASELINE, *TYPED.GEPA)
        with patch.object(TYPED, 'ARMS', arms), patch.object(TYPED, 'CPO', (ORDERED, BASELINE)):
            summary = TYPED.summary(tuple(records.values()))
        deltas = {name: record['arms'][BASELINE]['searchLookups'] - record['arms'][ORDERED]['searchLookups']
                  for name, record in records.items()}
        outcomes[mode] = {**summary, 'panels': len(deltas), 'searchReadsSaved': sum(deltas.values()),
                          'changedByPanel': {key: value for key, value in deltas.items() if value},
                          'traceSha256': digest(records)}
    savings = [row['searchReadsSaved'] for row in outcomes.values()]
    return {'costGatePassed': min(savings) >= 0 and max(savings) > 0, 'modes': outcomes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='DESIGN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    design, groups = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({**design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != design['gepaVersion']:
        parser.error('Use the current seal, pinned GEPA, and a fresh report path')
    result = {'design': design, 'designSha256': seal, 'results': measure(groups)}
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
