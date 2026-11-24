"""Price terminal backup capacity at the original strict math lookup budget."""

import argparse
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import recorded_math_router_transfer as transfer
from cpo._contract import digest


allocation = transfer.allocation


def prepare():
    entries = {}
    for group, width in product(('root', 'rotated'), (4, 8)):
        base, *inputs = transfer.prepare(group, width)
        entries[f'{group}/{width}'] = (base, inputs)
    plan = {'protocol': 'recorded-math-backup-capacity-v1', 'gepaVersion': '0.1.4',
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'transferPlans': {key: digest(base) for key, (base, _) in entries.items()},
            'scope': 'Fund only terminal backups after the frozen joint-proof router. Use the difference '
                     'between the measured strict math CPO and joint-proof lookup budget across both archives. '
                     'Verify the strict archive results. Measure realized outcomes and separately bound '
                     'hindsight capacity on the same evidence, allowing at most one backup per episode.'}
    return plan, entries


def measure(base, data, models, static, fit, reference):
    priors = allocation.witness.previous.priors_of(fit)
    episodes, prices = [], {}
    for subject, layout in base['datasets'].items():
        cells = transfer.prior.math.load_cells(subject, data[subject]['record'])
        trials = list(transfer.prior.trials(cells, layout, base['group'], base['rosterWidth']))
        paths, points, _ = transfer.cpo_and_simple(base, subject, cells, trials, models, static, priors)
        locked = reference[subject][f'{base["group"]}/{base["rosterWidth"]}']['totals']['strict']
        if any(points[transfer.STRICT][key] != locked[key] for key in transfer.METRICS):
            raise ValueError('The strict math budget and score must reproduce')
        prices[subject] = {name: dict(points[name]) for name in (transfer.PAIRED, transfer.STRICT)}
        episodes.extend(paths)
    funding = sum(points[transfer.STRICT]['paidLookups'] - points[transfer.PAIRED]['paidLookups']
                  for points in prices.values())
    if funding < 0:
        raise ValueError('The archived strict budget cannot fund the measured joint-proof router')
    offers = allocation.offers_for(transfer.backup.PROBE, episodes, priors)
    deployments, stats = allocation.rollout(allocation.PROPORTIONAL, episodes, offers, funding, priors)
    menus = allocation.positive_menus(episodes, offers, funding, priors)
    for subject, points in prices.items():
        final = sum(episode.cells[deployments.get(index, episode.deployed)][case]
                    for index, episode in enumerate(episodes) if episode.subject == subject
                    for case in episode.held)
        points['reserved-backup'] = {'holdoutPasses': final, 'paidLookups': points[transfer.PAIRED]['paidLookups']
                                     + stats['lookupsByTask'][subject]}
        points['settledChargeGainUpperBound'] = allocation.witness.priced_bounds(
            menus.get(subject, []), funding)['settledChargeUpperBound']
    return {'funding': funding, 'backup': stats, 'archives': prices}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, entries = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
              'results': {key: measure(base, *inputs) for key, (base, inputs) in entries.items()}}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
