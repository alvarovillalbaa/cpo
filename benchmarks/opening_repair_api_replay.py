"""Verify the public repair cycle against the sealed instruction-only diagnostic."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from benchmarks import alternative_controls as programs
from benchmarks import grounded, opening_repair_diagnostic as source
from benchmarks.case_difficulty_allocation import checked_file
from cpo import opening_repair_cycle
from cpo._contract import digest


REFERENCE = '72b3e921ab82c5d6f5e16a0c4576580046493855e424455aed919700a98ab8e3'


def strip_demonstrations(program):
    return programs.encode(grounded.load_json(program)['instruction'])


def packaged_cycle(*args, rounds, train_per_round, **options):
    return opening_repair_cycle.run_opening_repair_cycle(
        *args, diagnostic_prompt=strip_demonstrations, max_training_probes=source.PROBES, **options)


def prepare():
    parent, _, previous, _, _, fresh = source.prepare()
    frozen = checked_file('docs/opening-repair-diagnostic-results-v1.json', REFERENCE)
    if digest(parent) != frozen['designSha256']:
        raise ValueError('The instruction-only diagnostic design changed')
    design = {'protocol': 'cpo-opening-repair-api-v1', 'referenceReportSha256': REFERENCE,
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'packageSourceSha256': sha256(Path(opening_repair_cycle.__file__).read_bytes()).hexdigest()}
    return design, {'prior-seeds': previous, 'fresh-seeds': fresh}, frozen['results']


def comparable(expected):
    events = expected['events'][:-1]
    diagnostic = expected['events'][-1]
    if events[-1]['kind'] == 'targeted-repair':
        probes = [{'row_id': probe['row_id'], 'passed': probe['instruction_only_passed']}
                  for probe in diagnostic['probes']]
        event = {**events[-1], 'probes': probes}
        if event['status'] == 'duplicate':
            event['status'] = 'no-repair'
        events[-1] = event
    return {**expected, 'events': events}


def replay(cohorts, previous):
    matched = {}
    for phase, phase_result in previous.items():
        for cap, selected in phase_result.items():
            for trial in selected['diagnosticTrials']:
                seed, task = trial['seed'], trial['task']
                measured = source.rerun_repair(task, cohorts[phase][seed][task], seed, int(cap), packaged_cycle)
                expected = comparable(trial['arms'][source.PRIMARY])
                if expected != measured:
                    raise ValueError(f'The installed API changed the published trace for {phase}/{cap}/{seed}/{task}')
                matched[f'{phase}/{cap}/{seed}/{task}'] = measured['journalSha256']
    return matched


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, cohorts, previous = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    matched = replay(cohorts, previous)
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'matchedPanelTraces': matched},
                  output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
