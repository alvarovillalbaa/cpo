"""Separate uniform score-bound savings from the perfect-score shortcut."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import bounded_uniform_refit as refit
from cpo._contract import digest


SETTING = 'uniform/8/18'


def prepare():
    children = {cohort: refit.perfect.prepare(cohort) for cohort in refit.discovery.COHORTS}
    root = refit.transfer.ROOT
    files = (Path(__file__).resolve(), Path(refit.__file__), root / 'cpo/bounded_uniform_validation.py')
    sources = {str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest() for path in files}
    plan = {'protocol': 'bounded-uniform-price-audit-v1', 'setting': SETTING,
            'gepaVersion': '0.1.4', 'cohortPlanSha256': {cohort: digest(data[0]) for cohort, data in children.items()},
            'sourceSha256': sources,
            'scope': 'Freeze eight-candidate two-row uniform validation in every cohort. Compare the original '
                     'quote, previous perfect-score optimization and general score bounds. Preserve all '
                     'nomination and qualification decisions, and verify the paid lookup subsets.'}
    return plan, children


def compare(plan, panels, models, static, _gepa, _simple, prior_frontier, _old):
    original, optimized = refit.engines(plan, models, static)
    first = original[SETTING]
    middle = refit.perfect.variants(plan)[SETTING]
    last = optimized[SETTING]
    cap = max(limit for _, _, _, limit in plan['controls'])
    paid = Counter()
    for _, _, _, cells, stages, start in refit.previous.episodes(plan, panels):
        current = start
        for stage in stages:
            chosen, eager, interim = refit.perfect.compare_cycle(first, middle, cells, current, stage, cap)
            deployed, checked, final = refit.perfect.compare_cycle(middle, last, cells, current, stage, cap)
            if deployed != chosen or interim != checked:
                raise ValueError('The three measured paths must reconcile')
            paid.update(originalLookups=eager, perfectLookups=interim, boundedLookups=final,
                        cyclesWithAdditionalSaving=int(checked > final))
            current = deployed
        paid.update(episodes=1, holdoutPasses=sum(cells[current][case] for case in stages[0][2][-1]))
    expected = prior_frontier['frontiers'][refit.frontier.COMMON]
    if plan['commonSetting'] == SETTING and (
            paid['holdoutPasses'] != expected['holdoutPasses'] or paid['originalLookups'] != expected['paidLookups']):
        raise ValueError('The original common uniform path must reproduce')
    return {**paid, 'baselineBudget': prior_frontier['budget'],
            'withinBaselineBudget': paid['boundedLookups'] <= prior_frontier['budget'],
            'nativeUpperAtBaselineBudget': prior_frontier['nativeBoundsAtBudget']['subject-tuned-gepa']['upperPasses']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, children = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    result = {cohort: compare(child, *inputs) for cohort, (child, inputs) in children.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': result},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
