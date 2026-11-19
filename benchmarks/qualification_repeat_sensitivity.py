"""Compare qualification coverage and replication under simulated reply noise."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import gepa_paid_cap_transfer as gepa
from benchmarks import independent_mmlu_cost_frontier as frontier
from benchmarks import paid_incumbent_credit as recorded
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
RATES = (0, 1, 5)
SCHEDULES = {'eight-cases': (8, 1), 'four-cases': (4, 1), 'four-repeated': (4, 2)}
METHODS = ('cpo', 'gepa-batched')


def qualification_slots(cases, width, schedule):
    distinct, repeats = SCHEDULES[schedule]
    if len(cases) != 8 or len(set(cases)) != 8 or any(not 0 <= case < width for case in cases):
        raise ValueError('The source must reserve eight distinct cases per qualification panel')
    return [case + repeat * width for case in cases[:distinct] for repeat in range(repeats)]


class ObservedRow:
    def __init__(self, row, width, qualification, key, rate):
        self.row, self.width, self.qualification = row, width, qualification
        self.key, self.rate = key, rate

    def __len__(self):
        return self.width * 2

    def __getitem__(self, index):
        repeat, case = divmod(index, self.width)
        if not 0 <= repeat <= 1 or (repeat and case not in self.qualification):
            raise IndexError('Only reserved qualification cases have a repeated view')
        if not self.rate or case not in self.qualification:
            return self.row[case]
        weight = int.from_bytes(sha256(f'{self.key}/{case}/{repeat}'.encode()).digest()[:8], 'big')
        if 100 * weight < (1 << 64) * self.rate:
            return '0' if self.row[case] == '1' else '1'
        return self.row[case]


def run_episode(matrix, held, seed, panel, original, validation_rows, caps, rate):
    width = len(matrix[0])
    start, base_layouts = archive.continuous.schedule(width, len(matrix), held, seed, original)
    qualification = {case for cycle in base_layouts for case in cycle['qualify']}
    other = set(held) | {case for cycle in base_layouts for role in ('train', 'validation') for case in cycle[role]}
    if qualification & other or len(qualification) != 8 * len(base_layouts):
        raise ValueError('A qualification case intersects another case role or cycle')

    sample_key = f'qualification-repeat-sensitivity-v1/{panel}/{seed}'
    observed = [ObservedRow(row, width, qualification, f'{sample_key}/{prompt}', rate)
                for prompt, row in enumerate(matrix)]
    result = {}
    for schedule in SCHEDULES:
        layouts = [{**layout, 'qualify': qualification_slots(layout['qualify'], width, schedule)}
                   for layout in base_layouts]
        with patch.object(archive.continuous, 'schedule', return_value=(start, layouts)):
            for method, cap in caps.items():
                settings = {'validationRows': validation_rows, 'searchCap': cap}
                if method == 'cpo':
                    totals, trace = archive.episode(observed, held, seed, original, settings, 'recency')
                    trace_rows = [row['decision'] for row in trace]
                else:
                    _, totals, peak, trace = gepa.reinvest_episode(observed, held, seed, original, settings, batched=True)
                    if peak > cap:
                        raise ValueError('The GEPA paid validation cap was exceeded')
                    trace_rows = trace
                final = trace_rows[-1]['selected']
                passes = sum(matrix[int(final)][case] == '1' for case in held)
                if passes != totals['holdoutPasses']:
                    raise ValueError('Final holdout scoring must use the undisturbed source outcomes')
                result[f'{method}/{schedule}'] = totals, trace, final
    return result


def prepare(phase):
    parent, original, panels, prior = recorded.prepare(phase)
    caps = {'cpo': 52, 'gepa-batched': 52 if phase == 'development' else 44}
    if original['qualificationRowsPerCycle'] != 8:
        raise ValueError('The comparison requires eight original qualification cases per cycle')
    plan = {
        'protocol': 'cpo-qualification-repeat-sensitivity-v1', 'phase': phase,
        'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in (
            'benchmarks/qualification_repeat_sensitivity.py', 'benchmarks/paid_incumbent_credit.py',
            'benchmarks/archive_complementarity_transfer.py', 'benchmarks/gepa_paid_cap_transfer.py',
            'cpo/paired_qualification.py')},
        'parentPlanSha256': digest(parent), 'corpusSha256': parent['corpusSha256'],
        'referenceReportSha256': parent['referenceReportSha256'], 'gepaVersion': parent['gepaVersion'],
        'validationRows': parent['validationRows'], 'searchCaps': caps,
        'qualificationSchedules': {name: {'cases': cases, 'repeats': repeats}
                                   for name, (cases, repeats) in SCHEDULES.items()},
        'noisePercent': list(RATES),
        'scope': ('Flip individual qualification replies at the declared synthetic rate. Share the same first '
                  'reply across methods and qualification schedules, with an independently keyed second reply. '
                  'Validation, training, and final holdout keep their archived outcomes.'),
    }
    return plan, original, panels, prior


def summarize_panel(matrix, held, name, original, plan, reference):
    results = {}
    for rate in plan['noisePercent']:
        totals, traces, finals = {}, {}, {}
        for seed in original['seeds']:
            outcome = run_episode(matrix, held, seed, name, original, plan['validationRows'], plan['searchCaps'], rate)
            for strategy, (count, trace, final) in outcome.items():
                totals.setdefault(strategy, Counter()).update(count)
                traces.setdefault(strategy, []).append(trace)
                finals.setdefault(strategy, []).append(final)
        for strategy, total in totals.items():
            total.update(paidLookups=total['searchPaid'] + total['qualificationPaid'])
            totals[strategy] = dict(total, traceSha256=digest(traces[strategy]), finalPromptsSha256=digest(finals[strategy]))
        results[str(rate)] = totals
    if plan['phase'] == 'development':
        expected = {'cpo': reference['cpo']['seeded-52'], 'gepa-batched': reference['gepa'][gepa.METHODS[1]]['52']}
    else:
        expected = {'cpo': reference['methods']['cpo-52'], 'gepa-batched': reference['methods']['gepa-batched-44']}
    for method in METHODS:
        frontier.expect_reference(results['0'][f'{method}/eight-cases'], expected[method])
    return results


def replay(plan, original, panels, prior):
    report, aggregate = {}, {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        reference = prior[name]
        held = (original['holdoutCaseIDs'][subject] if plan['phase'] == 'development' else reference['holdoutCaseIDs'])
        report[name] = summarize_panel(matrix, held, name, original, plan, reference)
        for rate, methods in report[name].items():
            for method, point in methods.items():
                fields = {key: point[key] for key in ('holdoutPasses', 'paidLookups', 'searchPaid', 'qualificationPaid')}
                aggregate.setdefault(rate, {}).setdefault(method, Counter()).update(fields)
    return {'plan': plan, 'planSha256': digest(plan), 'panels': report, 'totals': aggregate}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--phase', choices=recorded.SOURCES, required=True)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Execution requires the current seal and a fresh report path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
