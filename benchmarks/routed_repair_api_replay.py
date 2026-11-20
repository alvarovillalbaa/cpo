"""Replay the published routed-probe comparison through the packaged API."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_repair_probe_routing as source
from benchmarks.case_difficulty_allocation import checked_file
from cpo import routed_repair_cycle
from cpo._contract import digest


REFERENCE = '1c9bd99c31666c17d6173f51494ed472ef682d7587c70f6791f270fb6d86c38c'


def packaged_cycle(features):
    def run(*args, rounds, train_per_round, **options):
        return routed_repair_cycle.run_routed_repair_cycle(
            *args, input_features=lambda row: dict(features[row.id]),
            diagnostic_prompt=source.SOURCE.api.strip_demonstrations, **options)
    return run


def prepare():
    parent, cohorts, previous, control = source.prepare()
    frozen = checked_file('docs/opening-repair-probe-routing-results-v1.json', REFERENCE)
    if digest(parent) != frozen['designSha256']:
        raise ValueError('The published routing benchmark changed')
    design = {'protocol': 'cpo-routed-repair-api-v1', 'referenceReportSha256': REFERENCE,
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'packageSourceSha256': sha256(Path(routed_repair_cycle.__file__).read_bytes()).hexdigest(),
              'gepaVersion': parent['gepaVersion']}
    return design, cohorts, previous, control, frozen['results']


def replay(cohorts, previous, control, expected):
    matched = {}
    with patch.object(source, 'repaired_cycle', packaged_cycle):
        for name, panels in cohorts.items():
            result = source.measure(panels, frozen=previous if name == 'prior-panels' else None,
                                    reference=control.get(name))
            if result != expected[name]:
                raise ValueError(f'The packaged API changed the benchmark result or trace for {name}')
            matched[name] = {'panels': len(panels), 'traceSha256': result['traceSha256']}
    return matched


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, cohorts, previous, control, expected = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        cli.error('Use GEPA 0.1.4')
    matched = replay(cohorts, previous, control, expected)
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'matchedCohortTraces': matched,
                   'matchedPanels': sum(cohort['panels'] for cohort in matched.values())},
                  output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
