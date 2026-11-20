"""Transfer the exact family order with a one-gain exception to new panels."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_final_validation_order as order
from cpo import family_ordered_validation as guarded
from cpo._contract import digest


SEEDS = (66863, 66877, 66883, 66919)


def prepare():
    _, pilot = order.prepare()
    with patch.object(order, 'SEEDS', SEEDS):
        underlying, fresh = order.prepare()
    if pilot.keys() & fresh.keys():
        raise ValueError('The confirmation cannot reuse a pilot panel')
    design = {'protocol': 'cpo-opening-family-validation-transfer-v1', 'gepaVersion': underlying['gepaVersion'],
              'sourceDesignSha256': digest(underlying), 'sourceSha256': {
                  Path(path).name: sha256(Path(path).read_bytes()).hexdigest() for path in (__file__, guarded.__file__)},
              'freshSeeds': SEEDS, 'cohortSha256': {'pilot': digest(pilot), 'fresh': digest(fresh)},
              'schedule': 'tight families when more than one net gain remains possible',
              'criteria': 'preserve exact decisions and use fewer reads on both new fault modes'}
    return design, {'pilot': pilot, 'fresh': fresh}


def measure(cohorts):
    with patch.object(order, 'tight_family_certificate', guarded.certify_family_ordered_validation_gain):
        results = {phase: order.measure(groups) for phase, groups in cohorts.items()}
    gate = all(mode['searchReadsSaved'] > 0 for mode in results['fresh']['modes'].values())
    return {'freshCostGatePassed': gate, 'cohorts': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='DESIGN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    design, cohorts = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({**design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != design['gepaVersion']:
        parser.error('Use the current seal, pinned GEPA, and a fresh report path')
    result = {'design': design, 'designSha256': seal, 'results': measure(cohorts)}
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
