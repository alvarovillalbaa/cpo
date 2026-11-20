"""Compare funded fallback probes when feature routing fails to find a training error."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_stall_recovery as parent
from benchmarks.case_difficulty_allocation import checked_file
from cpo import routed_repair_cycle
from cpo._contract import digest


REFERENCE = '51a78ed880c4c0aa2c6f5a383d0104a603187527db94f440cdfeb031cdc6b8cc'
FRESH_SEEDS = (61967, 61981, 62003, 62011)
LIMITS = {'routed': 0, 'fallback-4': 4, 'fallback-12': 12}
PRIMARY = 'fallback-12'
STRESS = parent.stress
MODES = (*STRESS.MODES, 'featureless')
EXTRACT = STRESS.feature_map


def prepare():
    upstream, cohorts, _ = parent.prepare()
    reference = checked_file('docs/opening-stall-recovery-results-v1.json', REFERENCE)
    for name in ('developmentDatasetSha256', 'transferDatasetSha256'):
        if upstream[name] != reference['design'][name]:
            raise ValueError('The prior panels changed')
    cohorts['confirmation'] = STRESS.panels_for(FRESH_SEEDS)
    inputs = [row['input'] for panels in cohorts.values() for panel in panels.values()
              for rows in panel.values() for row in rows]
    if len(set(inputs)) != len(inputs):
        raise ValueError('Confirmation inputs must be disjoint from prior inputs')
    design = {'protocol': 'cpo-opening-probe-fallback-v1', 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'referenceReportSha256': REFERENCE, 'parentDesignSha256': digest(upstream),
              'gepaVersion': upstream['gepaVersion'], 'searchCap': upstream['searchCap'],
              'modes': MODES, 'fallbackProbeLimits': LIMITS, 'primary': PRIMARY,
              'confirmationSeeds': FRESH_SEEDS, 'gepaGate': upstream['gepaGate'],
              'gate': ('Preserve every baseline holdout pass and clear both GEPA gates in each confirmation '
                       'feature mode, including the featureless test.'),
              'confirmationDatasetSha256': {name: digest(panel) for name, panel in cohorts['confirmation'].items()}}
    return design, cohorts, reference['results']['phases']


def feature_map(task, groups, mode):
    if mode == 'featureless':
        return {row['id']: {} for split in ('train', 'validation') for row in groups[split]}
    return EXTRACT(task, groups, mode)


def packaged(features, policy):
    def run(*args, rounds, train_per_round, **options):
        return routed_repair_cycle.run_routed_repair_cycle(
            *args, input_features=lambda row: features[row.id], recover_stalls=True,
            fallback_probe_limit=LIMITS[policy], diagnostic_prompt=STRESS.source.api.strip_demonstrations, **options)
    return run


def measure(cohorts, frozen):
    phases = {}
    summarize = STRESS.TYPED.summary
    for phase, panels in cohorts.items():
        fallback_receipts = []

        def summarize_with_probes(trials):
            counts = {}
            for policy, limit in LIMITS.items():
                count, stopped, used = 0, 0, 0
                for trial in trials:
                    events = trial['arms'][policy]['events']
                    probes = sum(len(event.get('fallbackRows', ())) for event in events)
                    if probes > limit:
                        raise ValueError('The cycle exceeded its fallback probe limit')
                    count += probes
                    used += probes > 0
                    stopped += any(event.get('fallbackRows') and event['status'] == 'accepted' for event in events)
                counts[policy] = {'fallbackLookups': count, 'panelsWithFallback': used, 'panelsWithAcceptedRepair': stopped}
            fallback_receipts.append(counts)
            return summarize(trials)

        with (patch.object(STRESS, 'POLICIES', tuple(LIMITS)), patch.object(STRESS, 'PRIMARY', PRIMARY),
              patch.object(STRESS, 'MODES', MODES), patch.object(STRESS, 'feature_map', feature_map),
              patch.object(STRESS, 'packaged', packaged),
              patch.object(STRESS, 'rank_coverage', routed_repair_cycle._rank_probes),
              patch.object(STRESS.TYPED, 'summary', summarize_with_probes)):
            outcomes = STRESS.measure(panels)['modes']
        for (mode, outcome), receipts in zip(outcomes.items(), fallback_receipts, strict=True):
            if mode in frozen.get(phase, {}):
                previous = frozen[phase][mode]['totals']
                if (outcome['totals']['routed'] != previous[parent.PRIMARY]
                        or any(outcome['totals'][arm] != previous[arm] for arm in STRESS.TYPED.GEPA)):
                    raise ValueError(f'The frozen control changed for {phase}/{mode}')
            outcome['fallback'] = receipts
            outcome['passed'] = (not outcome['vsRouted'][PRIMARY]['pairedLosses']
                                 and all(outcome['comparisons'][arm]['passed'] for arm in STRESS.TYPED.GEPA))
        phases[phase] = outcomes
    return {'confirmationGatePassed': all(mode['passed'] for mode in phases['confirmation'].values()), 'phases': phases}


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
