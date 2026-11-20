"""Transfer the shared-probe challenger screen to recorded ARC and AIME outcomes."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_coverage_window as window
from benchmarks import recorded_score_allocation as source
from cpo._contract import digest
from cpo.covered_pool import select_covered_pool


ROOT = Path(__file__).resolve().parents[1]
PARENT_SHA256 = 'af81c8074ccc492559056dab2550bad034c25ae7e0e82f9b11f4c3114157b72f'
ORDERED = 'covered-ordered'
SCREENED = 'binary-window'
VARIANTS = (ORDERED, SCREENED)


def prepare():
    previous, data = source.prepare()
    raw = (ROOT / 'docs/recorded-score-allocation-results-v1.json').read_bytes()
    archived = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_SHA256 or digest(previous) != archived['planSha256']:
        raise ValueError('The archived allocation comparison differs from its seal')
    paths = ('benchmarks/recorded_window_transfer.py', 'benchmarks/recorded_coverage_window.py',
             'cpo/covered_pool.py', 'cpo/coverage_confirmation.py')
    plan = {**previous, 'protocol': 'cpo-recorded-window-transfer-v1',
            'methods': (*source.METHODS, *VARIANTS), 'primary': SCREENED,
            'windowWidth': window.WIDTH, 'parentPlanSha256': digest(previous), 'parentReportSha256': PARENT_SHA256,
            'sourceSha256': {**previous['sourceSha256'], **{path: sha256((ROOT / path).read_bytes()).hexdigest()
                                                           for path in paths}},
            'witnessAudit': ('After replay, count candidates with a fully scored validation gain by their outcome '
                             'on the shared probe. Only include rosters where the incumbent precheck admits search.'),
            'transfer': ('Transfer the binary window rule without tuning. Both mathematical archives lack critical '
                         'strata. Compare to the same confirmation without the window, the earlier strict and posterior '
                         'policies, the fixed-pool alternatives, and both GEPA modes.')}
    return plan, data, archived['results']


def select(initial, roster, rows, observe, journal, *, policy, cap, width):
    """Adapt archived boolean observations to the original window callback."""
    if any(row.critical for row in rows):
        raise ValueError('These archives lack declared critical strata')
    if policy == ORDERED:
        result = select_covered_pool((initial, *roster), rows, observe, metric_limit=cap, critical_strata={})
        if result.evaluations != len(journal):
            raise ValueError('Unscreened selector did not account for every lookup')
        return result.prompt
    by_id = {row.id: row for row in rows}

    def read(prompt, row_id):
        value = observe(prompt, by_id[row_id])
        return value.passed, value.matched_fields

    return window.screen(initial, roster, tuple(by_id), {}, read, lambda: len(journal),
                         cap=cap, width=width, fields=False)[0]


def measure(cells, settings, cap, plan, reference):
    original_trial, paired = source.run_trial, source.math.paired_ranges
    math, backup = source.math, source.backup
    vectors = None

    def run(cells, start, roster, cohorts, seed, policy, cap):
        if policy not in VARIANTS:
            return original_trial(cells, start, roster, cohorts, seed, policy, cap)

        def choose(incumbent, candidates, rows, observe, journal, *, method, cap):
            return select(incumbent, candidates, rows, observe, journal, policy=policy,
                          cap=cap, width=plan['windowWidth']), False

        with (patch.object(math, 'select', choose), patch.dict(backup.PRECHECKED, {'strict-precheck': 'strict'})):
            return backup.run_prechecked(cells, start, roster, cohorts, seed, 'strict-precheck', cap)

    def capture(outcomes, candidate, controls, settings):
        nonlocal vectors
        vectors = outcomes
        return paired(outcomes, candidate, controls, settings)

    with (patch.object(source, 'run_trial', run), patch.object(source, 'METHODS', plan['methods']),
          patch.object(math, 'paired_ranges', capture)):
        result = source.measure(cells, settings, cap, plan)
    baselines = {**result, 'totals': {arm: value for arm, value in result['totals'].items() if arm not in VARIANTS}}
    if baselines != reference or vectors is None:
        raise ValueError('Earlier trace hashes, costs and paired comparisons did not reproduce')
    matched = {**result['totals'], **{control: result['totals'][arm]
                                    for control, arm in source.prior.QUALIFICATION_PRECHECK.items()}}
    controls = (*math.GEPA, 'strict-precheck', 'posterior-allocation', 'successive-halving',
                'full-score-history', 'retain-start')
    result['windowComparison'] = {
        arm: math.comparison(arm, matched, paired(vectors, arm, (*controls, ORDERED) if arm == SCREENED else controls,
                                                 plan), plan)
        for arm in VARIANTS
    }
    return result


def audit_witness(cells, settings, width):
    """Measure how much an incumbent miss predicts strict gain in the observed archive."""
    total = Counter(witnessPass=0, witnessFail=0, eligiblePass=0, eligibleFail=0)
    size = len(next(iter(cells.values())))
    for seed in settings['seeds']:
        _, validation, qualification, _ = source.math.split_cases(size, seed, settings['cohorts'])
        for start in tuple(cells)[1:]:
            if all(cells[start][case][0] for case in qualification):
                continue
            baseline = sum(cells[start][case][0] for case in validation)
            witness = next((case for case in validation if not cells[start][case][0]), None)
            if witness is None:
                continue
            others = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(others, len(others))[:width]
            for prompt in roster:
                passed = cells[prompt][witness][0]
                eligible = sum(cells[prompt][case][0] for case in validation) > baseline
                total.update(witnessPass=int(bool(passed)), witnessFail=int(not passed),
                             eligiblePass=int(bool(passed) and eligible), eligibleFail=int(not passed and eligible))
    return total


def replay(plan, data, archive):
    results, support = {}, {}
    for name, settings in plan['datasets'].items():
        cells = source.math.load_cells(name, data[name]['record'])
        results[name] = {str(cap): measure(cells, settings, cap, plan, archive[name][str(cap)])
                         for cap in plan['searchCaps']}
        support[name] = audit_witness(cells, settings, plan['challengers'])
    return {'plan': plan, 'planSha256': digest(plan), 'results': results, 'witnessSupport': support}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, archive = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, data, archive)
    with args.out.open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
