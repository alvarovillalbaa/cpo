"""Transfer the frozen two-read CPO selector to different archived tasks and models."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_archive_cycles as archive
from benchmarks import prompteval_bounded_discovery as bounded
from benchmarks import prompteval_lazy_incumbent as deferred
from benchmarks import prompteval_paid_witness as paid
from benchmarks import prompteval_single_finalist as first
from benchmarks import prompteval_transfer as transfer
from benchmarks.prompteval_validation_transfer import CPO, paired
from cpo._contract import digest, unique_object


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'benchmarks/data/bounded-discovery-transfer/outcomes.jsonl'
SOURCES = {
    'mmlu': ('prompt-lazy-screen-v1.json',
             'aada574f115dc1b122a53a8cce001708c6c5fb878fe7613cd99a4a5e1c9f822e', 'MIT', 8),
    'bbh-lmentry': ('cross-benchmark-prompt-outcomes-v1.json',
                    'c190bb16b397945a708f5c5ad93c76ac94bee6aab39f9a19207d76db4dd4db7b', 'CDLA-Permissive-2.0', 12),
    'bbh-lmentry-stress': ('prompt-backup-qualification-v1.json',
                           'dd5c78b8f2e886d800917c6971766923c925071c17b946efdfd65053f79bd516', 'CDLA-Permissive-2.0', 12),
}
METHOD = 'bounded-two-reads'
CONTROLS = (*first.METHODS[1:], 'deferred-first-gain')


def design():
    parent, original, _, _ = bounded.prepare('finalist-transfer')
    if parent['policies']['two-reads'] != {'discoveryLimit': 2, 'sharedPrefix': 1}:
        raise ValueError('The transfer must use the frozen two-read selector')
    return {
        'protocol': 'cpo-bounded-discovery-transfer-v1', 'parentPlanSha256': digest(parent),
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'inputSnapshots': {phase: {'filename': name, 'sha256': sha, 'license': license_name, 'panels': count}
                           for phase, (name, sha, license_name, count) in SOURCES.items()},
        'reusedMmluSubjects': sorted({s for phase in paid.PHASES for s in bounded.prepare(phase)[1]['holdoutCaseIDs']}),
        'selector': parent['policies']['two-reads'], 'gepaVersion': parent['gepaVersion'],
        'validationRowsAndSearchCap': parent['rowsAndCap'], 'trainRows': original['trainRows'],
        'cycles': original['cycles'], 'seeds': original['seeds'],
        'qualificationRowsPerCycle': original['qualificationRowsPerCycle'],
        'allocation': 'Original random-start proposal and qualification schedule. Fixed 30% holdout by subject.',
        'gate': parent['gate'], 'controls': list(CONTROLS),
    }, original


def source_rows(source_dir):
    for phase, (name, expected, license_name, expected_panels) in SOURCES.items():
        raw = (source_dir / name).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError(f'Archived source bytes differ for {phase}')
        source = json.loads(raw, object_pairs_hook=unique_object)
        if len(source['panels']) != expected_panels:
            raise ValueError(f'Unexpected number of panels for {phase}')
        provenance = {key: source[key] for key in (
            'sourceArchiveSha256', 'sourceDirectorySha256', 'observedRepoRevision',
        ) if key in source}
        for panel in source['panels']:
            keys = ('subject', 'model', 'correctness')
            identity = {key: panel[key] for key in ('memberSha256', 'viewerResponseSha256') if key in panel}
            for key in ('caseIDs', 'templateIDs'):
                if key in panel:
                    identity[key + 'Sha256'] = digest(panel[key])
            if not identity:
                raise ValueError('Every panel needs source identifiers')
            yield {
                **{key: panel[key] for key in keys}, 'phase': phase, 'license': license_name,
                'sourceSnapshotSha256': expected,
                'sourceDataset': source['sourceDataset'], 'sourceProvenance': {**provenance, **identity},
            }


def verify_panels(panels, settings):
    known = set(settings['reusedMmluSubjects'])
    by_phase, by_subject = Counter(), Counter()
    sizes, identities, seen = {}, {}, set()
    minimum_cases = settings['validationRowsAndSearchCap'][0] + settings['trainRows'] + (
        settings['cycles'] * settings['qualificationRowsPerCycle'])
    for panel in panels:
        phase, subject, model, matrix = (panel[key] for key in ('phase', 'subject', 'model', 'correctness'))
        key = (subject, model)
        if subject in known or key in seen or phase not in settings['inputSnapshots']:
            raise ValueError('The transfer panel overlaps the prior study or duplicates a task and model')
        seen.add(key)
        by_phase[phase] += 1
        by_subject[subject] += 1
        if len(matrix) != 100 or not isinstance(matrix[0], str):
            raise ValueError('Each panel needs 100 complete template outcomes')
        count = len(matrix[0])
        if count - len(transfer.holdout(subject, count)) < minimum_cases or any(
                not isinstance(line, str) or len(line) != count or set(line) - {'0', '1'} for line in matrix):
            raise ValueError('The binary matrix must be rectangular and fit the disjoint schedule')
        source = settings['inputSnapshots'][phase]
        if panel['sourceSnapshotSha256'] != source['sha256'] or panel['license'] != source['license']:
            raise ValueError('The embedded snapshot provenance differs')
        alignment = (phase, count, *(panel['sourceProvenance'].get(key) for key in ('caseIDsSha256', 'templateIDsSha256')))
        if identities.setdefault(subject, alignment) != alignment:
            raise ValueError('A subject must use the same cases and templates across both models')
        sizes[subject] = count
    if dict(by_phase) != {phase: value['panels'] for phase, value in settings['inputSnapshots'].items()}:
        raise ValueError('The packaged transfer must include every planned panel')
    if any(count != 2 for count in by_subject.values()):
        raise ValueError('Each subject needs two distinct model panels')
    return sizes


def capture(source_dir, settings, target):
    panels = list(source_rows(source_dir))
    verify_panels(panels, settings)
    with target.open('x') as output:
        output.write(json.dumps({'designSha256': digest(settings)}, sort_keys=True, separators=(',', ':')) + '\n')
        for panel in panels:
            output.write(json.dumps(panel, sort_keys=True, separators=(',', ':')) + '\n')


def prepare(phase, settings, original):
    raw = DATA.read_bytes()
    header, *panels = (json.loads(line, object_pairs_hook=unique_object) for line in raw.splitlines())
    if header != {'designSha256': digest(settings)}:
        raise ValueError('The capture design differs from the replay design')
    sizes = verify_panels(panels, settings)
    holdouts = {subject: transfer.holdout(subject, count) for subject, count in sizes.items()}
    selected = [panel for panel in panels if panel['phase'] == phase]
    plan = {**settings, 'phase': phase, 'dataSha256': sha256(raw).hexdigest(),
            'holdoutCaseIDs': {panel['subject']: holdouts[panel['subject']] for panel in selected}}
    return plan, {**original, 'holdoutCaseIDs': holdouts}, selected


def replay(plan, original, data):
    panels = {}
    for panel in data:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held, seeds = original['holdoutCaseIDs'][subject], original['seeds']
        full = [first.screened_episode(matrix, held, seed, original, 'first-gain') for seed in seeds]
        controls = {m: [episode[m] for episode in full] for m in first.METHODS[1:]}
        with patch.object(archive, 'METHODS', archive.METHODS[:1]):
            controls['deferred-first-gain'] = [
                deferred.measured_episode(matrix, held, seed, original, False, False) for seed in seeds]
            audit = Counter()
            candidate = [bounded.measured_episode(matrix, held, seed, original, 'two-reads', audit) for seed in seeds]
        all_arms = {METHOD: candidate, **controls}
        panels[name] = {
            'totals': {m: first.totals(trace) for m, trace in all_arms.items()},
            'traceSha256': {m: digest(trace) for m, trace in all_arms.items()},
            'comparisons': {m: paired(candidate, trace) for m, trace in controls.items()}, 'audit': dict(audit),
        }
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels,
            'panelsClearingBothGates': [name for name, panel in panels.items() if all(
                panel['comparisons'][m]['qualified'] for m in first.METHODS[1:])]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--design', action='store_true')
    mode.add_argument('--capture', type=Path)
    mode.add_argument('--phase', choices=SOURCES)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    settings, original = design()
    seal = digest(settings)
    if args.design:
        if args.execute is not None or args.out is not None:
            parser.error('Design preview takes no execution arguments')
        print(json.dumps({**settings, 'designSha256': seal}, sort_keys=True, indent=2))
        return
    if args.capture is not None:
        if args.execute != seal or args.out is None or args.out.exists():
            parser.error('Capture requires the design seal and a fresh output path')
        capture(args.capture, settings, args.out)
        return
    plan, original, data = prepare(args.phase, settings, original)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the phase seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, original, data)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
