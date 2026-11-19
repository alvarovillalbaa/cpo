"""Measure the realized cost frontier on the independent archived MMLU panels."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import independent_mmlu_transfer as independent
from benchmarks import paid_budget_frontier as frontier
from benchmarks import single_wide_cycle as wide
from benchmarks import starting_prompt_margin as attribution
from cpo._contract import digest


WIDE_REPORT_SHA256 = '36c3683014f44dc6f2e4ac1d2f4fb62a38bfb6fc22df1f7051bf0040fe179cbf'
CAPS = tuple(range(20, 69))
CPO_CAPS = frontier.CPO_CAPS
FIELDS = ('holdoutPasses', 'paidLookups')


def prepare():
    parent, original, panels, gepa_52, _ = wide.prepare('independent')
    previous = archive.checked_report('single-wide-cycle-results-v1.json', WIDE_REPORT_SHA256, 'independent')
    if previous['planSha256'] != digest(parent):
        raise ValueError('The original single-cycle replay differs from its sealed plan')
    baseline = independent.read_json(attribution.INDEPENDENT_REPORT.read_bytes())
    if min(CAPS) < parent['validationRows'] + original['qualificationRowsPerCycle']:
        raise ValueError('The sweep must fund incumbent validation after any archive charge')
    plan = {
        'protocol': 'cpo-independent-mmlu-cost-frontier-v1',
        'singleWidePlanSha256': digest(parent), 'singleWideReportSha256': WIDE_REPORT_SHA256,
        'originalIndependentReportSha256': attribution.INDEPENDENT_SHA256,
        'corpusSha256': baseline['corpusSha256'], 'gepaVersion': parent['gepaVersion'],
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'frontierSourceSha256': sha256(Path(frontier.__file__).read_bytes()).hexdigest(),
        'validationRows': parent['validationRows'], 'gepaCaps': list(CAPS), 'cpoCaps': list(CPO_CAPS),
        'gepaMethods': list(independent.gepa.METHODS), 'cpoWideSchedules': list(wide.METHODS[1:]),
        'scope': ('Measure all integer GEPA caps in the declared interval. Compare realized costs including '
                  'qualification. Fixed and task-specific comparisons may select from measured scores with hindsight.'),
    }
    return plan, original, panels, gepa_52, previous['panels'], baseline['panels']


def expect_reference(measured, stored):
    if any(measured[k] != stored[k] for k in (*FIELDS, 'traceSha256')):
        raise ValueError('A cap-52 replay differs from its published trace, score or lookup cost')


def measured_panel(panel, original, plan, archived_gepa, archived_wide, baseline):
    matrix, subject = panel['correctness'], panel['subject']
    held = original['holdoutCaseIDs'][subject]
    result = {'gepa': {}, 'cpo': {}, 'retainStart': baseline['methods']['retain-start']['holdoutPasses'],
              'holdoutDecisions': baseline['holdoutDecisions']}
    for method in plan['gepaMethods']:
        by_cap = {str(cap): frontier.measure(matrix, held, original, plan['validationRows'], method, cap)
                  for cap in plan['gepaCaps']}
        expect_reference(by_cap['52'], archived_gepa[method])
        result['gepa'][method] = by_cap
    for cap in plan['cpoCaps']:
        point = frontier.measure(matrix, held, original, plan['validationRows'], independent.gepa.CPO, cap)
        if cap == 52:
            expect_reference(point, archived_wide['methods']['seeded'])
        result['cpo'][f'seeded-{cap}'] = point
    for method in plan['cpoWideSchedules']:
        total, traces = Counter(), []
        for seed in original['seeds']:
            measured, trace, _ = wide.run_episode(matrix, held, seed, original, {'searchCap': 52,
                                                      'validationRows': plan['validationRows']}, method)
            total.update(measured)
            traces.append(trace)
        point = {'holdoutPasses': total['holdoutPasses'], 'paidLookups': total['searchPaid'] + total['qualificationPaid'],
                 'traceSha256': digest(traces)}
        expect_reference(point, archived_wide['methods'][method])
        result['cpo'][method] = point
    return result


def compare_cost(point, all_gepa, by_subject):
    budget, passes = point['paidLookups'], point['holdoutPasses']
    fixed = frontier.best_fixed_gepa(all_gepa, budget)
    task_oracle = frontier.best_subject_allocation(by_subject, budget)
    matching = min(({'method': method, 'cap': int(cap), **row}
                    for method, caps in all_gepa.items() for cap, row in caps.items()
                    if row['holdoutPasses'] >= passes), key=lambda x: (x['paidLookups'], -x['holdoutPasses']), default=None)
    return {'bestFixedGepaWithinCost': fixed, 'taskGepaWithRetainStartWithinCost': task_oracle,
            'cheapestFixedGepaMatchingPasses': matching}


def summarize(panels):
    gepa = frontier.aggregate({name: row['gepa'] for name, row in panels.items()})
    cpo, subjects, retained = {}, {}, Counter()
    for name, row in panels.items():
        subject = name.split('/')[0]
        subjects.setdefault(subject, {})[name] = row['gepa']
        retained[subject] += row['retainStart']
        for method, point in row['cpo'].items():
            cpo.setdefault(method, Counter()).update({k: point[k] for k in FIELDS})
    by_subject = {subject: [
        {'method': method, 'cap': int(cap), **point}
        for method, caps in frontier.aggregate(group).items() for cap, point in caps.items()
    ] + [{'method': 'retain-start', 'cap': 0, 'holdoutPasses': retained[subject], 'paidLookups': 0}]
        for subject, group in subjects.items()}
    comparison = {method: compare_cost(point, gepa, by_subject) for method, point in cpo.items()}
    by_panel = {
        method: dict(Counter(
            'unavailable' if (choice := frontier.best_fixed_gepa(row['gepa'], row['cpo'][method]['paidLookups'])) is None
            else 'higher' if row['cpo'][method]['holdoutPasses'] > choice['holdoutPasses']
            else 'lower' if row['cpo'][method]['holdoutPasses'] < choice['holdoutPasses'] else 'tied'
            for row in panels.values()))
        for method in cpo
    }
    return {'gepaTotals': gepa, 'cpoTotals': cpo, 'retainStartPasses': sum(retained.values()),
            'matchedCostComparisons': comparison, 'perPanelAgainstBestAffordableFixedGepa': by_panel}


def replay(plan, original, panels, archived_gepa, archived_wide, baseline):
    result = {}
    for panel in panels:
        name = f"{panel['subject']}/{panel['model']}"
        result[name] = measured_panel(
            panel, original, plan, archived_gepa[name], archived_wide[name], baseline[name])
    return {'plan': plan, 'planSha256': digest(plan), 'panels': result, **summarize(result)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
