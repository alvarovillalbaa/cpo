"""Race validation challengers that preserve the incumbent's measured gains."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_math_validation_ties as math
from benchmarks import recorded_training_backup as prior
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
PARENT_SHA256 = 'e5c74e67ab56d98935056ffb31ca8a85df10f222ff9f65cc20f98b20e50c74b0'
QUALIFICATION_PRECHECK = {name: f'{name}-precheck' for name in math.GEPA}
CONTROLS = ('retain-start', 'strict', 'certified-precheck', *QUALIFICATION_PRECHECK.values())
POLICIES = ('strict-precheck', 'split-veto', 'split-race', 'row-race')
METHODS = (*CONTROLS, *POLICIES)


def groups(rows, *, individual):
    if individual:
        return {row.id: index for index, row in enumerate(rows)}
    half = len(rows) // 2
    return {row.id: int(index >= half) for index, row in enumerate(rows)}


def guarded_race(incumbent, roster, rows, observe, ledger, *, cap, individual):
    """Rank eligible exact-score winners and reject only impossible challenges."""
    group = groups(rows, individual=individual)
    successes, counts = Counter(), Counter()

    def read(prompt, row):
        passed = observe(prompt, row).passed
        if type(passed) is not bool:
            raise ValueError('Validation requires an exact boolean outcome')
        successes[row.id] += passed
        counts[row.id] += 1
        return passed

    start = {row.id: read(incumbent, row) for row in rows}
    minima = Counter(group[row_id] for row_id, passed in start.items() if passed)
    protected = {row.id for row in rows if row.critical and start[row.id]}
    maximum = Counter(group.values())
    leader, best = incumbent, sum(start.values())
    for prompt in roster:
        if best == len(rows) or cap - len(ledger) < len(rows):
            break
        upper = maximum.copy()
        passes = 0
        order = sorted(rows, key=lambda row: (
            row.id not in protected, Fraction(successes[row.id] + 1, counts[row.id] + 2)))
        for index, row in enumerate(order, 1):
            if read(prompt, row):
                passes += 1
            else:
                bucket = group[row.id]
                upper[bucket] -= 1
                if row.id in protected or upper[bucket] < minima[bucket]:
                    break
            if passes + len(rows) - index <= best:
                break
        else:
            leader, best = prompt, passes
    return leader


def run_trial(cells, start, roster, cohorts, seed, arm, cap):
    if arm in CONTROLS:
        return prior.run_trial(cells, start, roster, cohorts, seed, arm, cap)

    original = math.select

    def select(incumbent, candidates, rows, observe, journal, *, method, cap):
        if arm in ('split-race', 'row-race'):
            return guarded_race(incumbent, candidates, rows, observe, journal,
                                cap=cap, individual=arm == 'row-race'), False
        nominee, tied = original(incumbent, candidates, rows, observe, journal, method=method, cap=cap)
        if arm == 'split-veto' and nominee != incumbent:
            margins = Counter()
            for row_id, group in groups(rows, individual=False).items():
                margins[group] += journal[nominee, row_id].passed - journal[incumbent, row_id].passed
            if min(margins.values()) < 0:
                return incumbent, False
        return nominee, tied

    with (patch.object(math, 'select', select),
          patch.dict(prior.PRECHECKED, {'strict-precheck': 'strict'})):
        return prior.run_prechecked(cells, start, roster, cohorts, seed, 'strict-precheck', cap)


def prepare():
    parent, data, _ = prior.prepare()
    raw = (ROOT / 'docs/recorded-training-backup-results-v1.json').read_bytes()
    report = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_SHA256 or report['planSha256'] != digest(parent):
        raise ValueError('The published training backup comparison does not match its seal')
    paths = ('benchmarks/recorded_validation_stability.py', *parent['sourceSha256'])
    plan = {**{key: parent[key] for key in ('gepaVersion', 'datasets', 'challengerCounts', 'incumbentGroups',
                                           'searchCap', 'bootstrapSeed', 'bootstrapDraws',
                                           'minimumLookupSavingPercent')},
            'protocol': 'cpo-recorded-validation-stability-v1', 'priorPlanSha256': digest(parent),
            'priorReportSha256': PARENT_SHA256, 'methods': METHODS,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'scope': ('Require strict validation gain with nonnegative margin in each seeded half or '
                      'preserve every incumbent validation pass. Compare a post-selection veto and an '
                      'eligibility-aware race. Apply the same paid qualification precheck as GEPA.')}
    return plan, data, report['results']


def measure(cells, settings, group, width, plan, reference):
    size = len(next(iter(cells.values())))
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    totals, traces = {m: Counter() for m in METHODS}, {m: [] for m in METHODS}
    vectors = {m: [0] * size for m in METHODS}
    changes = {m: Counter() for m in POLICIES}
    for seed in settings['seeds']:
        cohorts = math.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            available = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(available, len(available))[:width]
            for arm in METHODS:
                point, trace, passed = run_trial(cells, start, roster, cohorts, seed, arm, plan['searchCap'])
                totals[arm].update(point)
                traces[arm].append(trace)
                if arm in POLICIES:
                    strict = traces['strict'][-1]
                    delta = point['holdoutPasses'] - sum(cells[strict[3]][case][0] for case in cohorts[-1])
                    changes[arm].update(nominations=int(trace[2] != start), promotions=int(trace[3] != start),
                                        trialsImproved=int(delta > 0), trialsRegressed=int(delta < 0))
                for case, outcome in zip(cohorts[-1], passed, strict=True):
                    vectors[arm][case] += outcome
            if traces['strict-precheck'][-1][3] != traces['strict'][-1][3]:
                raise ValueError('The incumbent precheck changed the strict deployment')
    points = {arm: {**total, 'traceSha256': digest(traces[arm])} for arm, total in totals.items()}
    if any(points[arm] != reference['totals'][arm] for arm in CONTROLS):
        raise ValueError('A published control decision or paid trace differs')
    if any(sum(vector) != totals[arm]['holdoutPasses'] for arm, vector in vectors.items()):
        raise ValueError('The case vectors differ from recorded holdout passes')
    matched_totals = {**totals, **{rival: totals[arm] for rival, arm in QUALIFICATION_PRECHECK.items()}}
    matched_vectors = {**vectors, **{rival: vectors[arm] for rival, arm in QUALIFICATION_PRECHECK.items()}}
    policies = ('certified-precheck', *POLICIES)
    comparisons = {}
    for arm in policies:
        controls = tuple(math.GEPA) if arm == 'strict-precheck' else ('strict-precheck', *math.GEPA)
        ranges = math.paired_ranges(matched_vectors, arm, controls, plan)
        comparisons[arm] = math.comparison(arm, matched_totals, ranges, plan)
    return {'totals': points, 'comparisons': comparisons, 'changesFromStrict': changes,
            'trialsPerMethod': reference['trialsPerMethod']}


def replay(plan, sources, reference):
    report = {}
    for name, settings in plan['datasets'].items():
        cells = math.load_cells(name, sources[name]['record'])
        report[name] = {f'{group}/{width}': measure(cells, settings, group, width, plan,
                                                   reference[name][f'{group}/{width}'])
                        for group in plan['incumbentGroups'] for width in plan['challengerCounts']}
    return {'plan': plan, 'planSha256': digest(plan), 'results': report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, sources, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, sources, reference)
    with args.out.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
