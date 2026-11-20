"""Verify that the bounded stall-recovery option transfers to fresh policy panels."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_probe_robustness as stress
from benchmarks.case_difficulty_allocation import checked_file
from cpo import routed_repair_cycle
from cpo._contract import digest


REFERENCE = '66fc0758fba29b95204ebfa36b3bd2801825f3e20786c61f2a14dd04761356f1'
TRANSFER_SEEDS = (61129, 61141, 61151, 61169)
PRIMARY = 'stall-recovery'


def prepare():
    parent, development = stress.prepare()
    reference = checked_file('docs/opening-probe-robustness-results-v1.json', REFERENCE)
    if reference['design']['datasetSha256'] != parent['datasetSha256']:
        raise ValueError('The development panels changed')
    transfer = stress.panels_for(TRANSFER_SEEDS)
    groups = (*development.values(), *transfer.values())
    inputs = [row['input'] for panel in groups for rows in panel.values() for row in rows]
    if len(set(inputs)) != len(inputs):
        raise ValueError('Transfer and development panels must have disjoint inputs')
    design = {'protocol': 'cpo-opening-stall-recovery-v1', 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'referenceReportSha256': REFERENCE, 'gepaVersion': parent['gepaVersion'], 'searchCap': parent['searchCap'],
              'parentSourceSha256': parent['sourceSha256'], 'developmentDatasetSha256': parent['datasetSha256'],
              'transferDatasetSha256': {name: digest(panel) for name, panel in transfer.items()},
              'transferSeeds': TRANSFER_SEEDS, 'modes': stress.MODES, 'gepaGate': parent['gepaGate'],
              'gate': ('On fresh panels, preserve every baseline holdout pass and clear the original gate against '
                       'both GEPA controls in every feature mode. Report the per-mode result even when the '
                       'full transfer gate fails.')}
    return design, {'development': development, 'transfer': transfer}, reference['results']['modes']


def packaged(features, policy):
    def run(*args, rounds, train_per_round, **options):
        return routed_repair_cycle.run_routed_repair_cycle(
            *args, input_features=lambda row: features[row.id], recover_stalls=policy == PRIMARY,
            diagnostic_prompt=stress.source.api.strip_demonstrations, **options)
    return run


def measure(cohorts, frozen):
    phases = {}
    for phase, panels in cohorts.items():
        with (patch.object(stress, 'POLICIES', ('routed', PRIMARY)),
              patch.object(stress, 'PRIMARY', PRIMARY),
              patch.object(stress, 'packaged', packaged),
              patch.object(stress, 'rank_coverage', routed_repair_cycle._rank_probes)):
            outcomes = stress.measure(panels)['modes']
        for mode, outcome in outcomes.items():
            if phase == 'development':
                for arm in ('routed', *stress.TYPED.GEPA):
                    if outcome['totals'][arm] != frozen[mode]['totals'][arm]:
                        raise ValueError(f'The frozen development control changed for {mode}/{arm}')
            outcome['modeGatePassed'] = (not outcome['vsRouted'][PRIMARY]['pairedLosses']
                                         and all(outcome['comparisons'][arm]['passed'] for arm in stress.TYPED.GEPA))
        phases[phase] = outcomes
    return {'transferGatePassed': all(outcome['modeGatePassed'] for outcome in phases['transfer'].values()),
            'phases': phases}


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
