"""Check final prompt regressions on cases reserved from each archived episode."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import case_difficulty_allocation as parent
from benchmarks import priced_gate_reachability as audit
from benchmarks import routed_score_allocation as route
from cpo import Row
from cpo._contract import digest
from cpo.paired_qualification import certify_paired_qualification


ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REPORT = '310e07b60d42711588a848cd0b348fdf1663f2d7469ca01ff1b9908387ffa3f3'
CONTROL = 'strict'
POLICIES = ('rollback-on-loss', 'require-upgrade')
COMPARATORS = audit.CONTROLS
GUARDED_GEPA = {label: f'{label}/rollback-on-loss' for label in route.PRIMARY}
MIN_CASES = 4
MAX_CASES = 8


def reserve_cases(case_count, held, layouts, seed):
    used = set(held)
    for layout in layouts:
        for role in ('train', 'validation', 'qualify'):
            used.update(layout[role])
    cases = sorted(set(range(case_count)) - used)
    Random(f'cpo-regression-guard/{seed}').shuffle(cases)
    return tuple(cases[:MAX_CASES])


def guard(start, final, cases, evaluate, *, remaining, seed, require_upgrade):
    if start == final:
        return final, (), 'unchanged'
    if len(cases) < MIN_CASES:
        return final, (), 'insufficient-cases'
    if remaining < 2 * len(cases):
        return final, (), 'insufficient-budget'
    incumbent, challenger = (start, final) if require_upgrade else (final, start)
    rows = tuple(Row(str(case), 'task') for case in cases)
    verdict = certify_paired_qualification(incumbent, challenger, rows,
                                           lambda prompt, row, _: evaluate(prompt, int(row.id)), seed=seed)
    if verdict.status == 'undecided':
        raise ValueError('A fully funded guard must have a decision')
    return verdict.prompt, verdict.observations, 'checked'


def prepare():
    prior, inputs = parent.prepare()
    parent.checked_file('docs/final-start-reconciliation-results-v1.json', PREVIOUS_REPORT)
    bound, _ = audit.prepare()
    paths = ('benchmarks/reserved_regression_guard.py', 'benchmarks/priced_gate_reachability.py',
             'benchmarks/prompteval_continuous.py', 'benchmarks/prompteval_validation_size.py',
             'benchmarks/gepa_paid_cap_transfer.py', 'cpo/paired_qualification.py')
    design = {'protocol': 'cpo-reserved-regression-guard-v1', 'parentDesignSha256': digest(prior),
              'costedAuditDesignSha256': digest(bound), 'orderingReportSha256': PREVIOUS_REPORT,
              'minimumCases': MIN_CASES, 'maximumCases': MAX_CASES, 'methods': POLICIES,
              'primary': POLICIES[0], 'controls': COMPARATORS, 'guardedGepa': GUARDED_GEPA,
              'scope': ('Reserve up to eight cases outside the holdout and all four training, validation, '
                        'and qualification assignments without reading outcomes. Fund a complete paired '
                        'check from unused episode allowance. Roll back on a strict loss while accepting a '
                        'tie, or require a strict improvement. Apply the regression check to both GEPA controls.'),
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}}
    return design, inputs


def measure(panels, references, plan):
    labels = (*COMPARATORS, *POLICIES, *GUARDED_GEPA.values())
    totals = {label: Counter() for label in labels}
    results, advantages, matched, held_by_subject = {}, {label: {} for label in POLICIES}, {}, {}
    reserve_sizes = Counter()
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = route.CONFIRMATION.holdout(subject, len(matrix[0]))
        if held_by_subject.setdefault(subject, held) != held:
            raise ValueError('Both models must share the holdout cases')
        counts, finals, traces = ({key: factory() for key in labels} for factory in (Counter, list, list))
        evidence = []
        for seed in plan['schedule']['seeds']:
            start, layouts = audit.gepa.smaller.narrow_schedule(*audit.gepa.continuous.schedule(
                len(matrix[0]), len(matrix), held, seed, plan['schedule']), plan['validationRows'])
            reserve = reserve_cases(len(matrix[0]), held, layouts, seed)
            ceiling = sum(plan['searchCap'] + 2 * len(cycle['qualify']) for cycle in layouts)
            measured, attribution = audit.measure_episode(matrix, held, seed, plan)
            reserve_sizes[len(reserve)] += 1
            episode = {'seed': seed, 'reservedCaseIDs': reserve, 'guards': {}}
            for label, (final, stats, log) in measured.items():
                finals[label].append(int(final))
                traces[label].append(log)
                paid = stats['searchPaid'] + stats['qualificationPaid']
                counts[label].update(holdoutPasses=stats['holdoutPasses'], paidLookups=paid)
                modes = POLICIES if label == CONTROL else (GUARDED_GEPA[label],)
                for mode in modes:
                    selected, reads, status = guard(
                        start, final, reserve, lambda prompt, case: matrix[int(prompt)][case] == '1',
                        remaining=ceiling - paid, seed=seed, require_upgrade=mode == POLICIES[1])
                    total = paid + len(reads)
                    if total > ceiling or any(int(reply.row_id) not in reserve for reply in reads):
                        raise ValueError('The guard must spend only its reserved cases and remaining budget')
                    finals[mode].append(int(selected))
                    observed_score = sum(matrix[int(selected)][case] == '1' for case in held)
                    delta = observed_score - stats['holdoutPasses']
                    recovered = sum(selected != final and bound == audit.RETAIN_START
                                    for bound in attribution['firstBound'].values()) if label == CONTROL else 0
                    counts[mode].update(holdoutPasses=observed_score, paidLookups=total, guardLookups=len(reads),
                                        changedFinal=int(selected != final), improved=int(delta > 0),
                                        regressed=int(delta < 0), matchedStartRecoveries=recovered)
                    counts[mode][status] += 1
                    if status == 'checked':
                        record = {'selected': selected, 'guardLookups': len(reads),
                                  'guardTraceSha256': digest([(r.prompt, r.row_id, r.passed) for r in reads])}
                        episode['guards'][mode] = record
                        traces[mode].append(record)
            evidence.append(episode)

        points = {label: {**count, 'traceSha256': digest(traces[label])} for label, count in counts.items()}
        outcomes = {label: route.CONFIRMATION.uncertainty.case_totals(matrix, held, choices)
                    for label, choices in finals.items()}
        for label, point in points.items():
            if label in COMPARATORS:
                route.ties.frontier.expect_reference(point, references[name][label])
            if sum(outcomes[label].values()) != point['holdoutPasses']:
                raise ValueError('Final prompt vectors differ from the measured totals')
            totals[label].update({key: value for key, value in point.items() if type(value) is int})
        for label, comparisons in advantages.items():
            summary = comparisons.setdefault(subject, {method: [0] * len(held) for method in COMPARATORS})
            for control, values in summary.items():
                for i, case in enumerate(held):
                    values[i] += outcomes[label][case] - outcomes[control][case]
        same = matched.setdefault(subject, {method: [0] * len(held) for method in route.PRIMARY})
        for label, values in same.items():
            for i, case in enumerate(held):
                values[i] += outcomes[POLICIES[0]][case] - outcomes[GUARDED_GEPA[label]][case]
        results[name] = {'methods': points, 'episodes': evidence}

    comparisons = {}
    for label, scores in advantages.items():
        ranges = route.transfer.ranges(scores, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
        cost, limit = totals[label]['paidLookups'], 100 - plan['minimumLookupSavingPercent']
        savings = {m: 1 - cost / totals[m]['paidLookups'] for m in route.PRIMARY}
        enough = all(100 * cost <= limit * totals[m]['paidLookups'] for m in route.PRIMARY)
        low, high = ranges['joint']
        gate = 'failed' if not enough or high < 0 else 'passed' if low >= 0 else 'inconclusive'
        comparisons[label] = {'gate': gate, 'lookupSavings': savings, 'caseRanges': ranges}
    same_ranges = route.transfer.ranges(matched, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
    return {'totals': totals, 'comparisons': comparisons, 'sameGuardPairedRanges': same_ranges,
            'reservedCaseCounts': reserve_sizes, 'panels': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    design, inputs = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for _, _, plan in inputs.values()):
        parser.error('Use pinned GEPA 0.1.4')
    results = {key: measure(*args) for key, args in inputs.items()}
    with args.out.open('x') as stream:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, stream, sort_keys=True,
                  separators=(',', ':'))
        stream.write('\n')


if __name__ == '__main__':
    main()
