"""Test independent evidence before leaving, or returning to, the starting prompt."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import independent_mmlu_cost_frontier as frontier
from benchmarks import independent_mmlu_cost_uncertainty as uncertainty
from benchmarks import routed_model_cost_frontier as cost_frontier
from benchmarks import routed_witness_split as split
from benchmarks import starting_prompt_margin as margin
from cpo import Row, fixed_pool_cycle
from cpo._contract import digest
from cpo.paired_qualification import certify_paired_qualification


ROOT = Path(__file__).resolve().parents[1]
SPLIT_SHA256 = '859091e953d3a0f81c8b375564f2c22acd68c87d6571906ef942683fec095e57'
FRONTIER_SHA256 = '69cc1650905bf10040487651036e603c570b08c7b0a4ae0762e8d5afbadbc761'
ROUTES = ('wide-on-third-pass', 'wide-on-third-miss')
POLICIES = ('ordinary', 'two-at-start', 'split-departure', 'recall-start', 'split-and-recall',
            'reserve-start-for-final', 'split-and-reserve')
GEPA_ANCHOR = 'gepa-sequential.runner-up', 35
AUDITED = 'wide-on-third-miss/split-and-reserve'
FIXED_CONTROLS = ('sequential-35', 'sequential-40', 'sequential-52', 'batched-52')


def halves(rows):
    rows = tuple(rows)
    if len(rows) < 2 or len(rows) % 2:
        raise ValueError('Start protection requires two equally sized qualification groups')
    return tuple(replace(row, family=str(index // (len(rows) // 2))) for index, row in enumerate(rows))


def qualify_archive_halves(incumbent, challenger, cases, evaluate):
    """Use the archive's incumbent-first read order and the two-group gate."""
    rows = halves(Row(str(case), 'qualification') for case in cases)
    if len({row.id for row in rows}) != len(rows):
        raise ValueError('Archive qualification requires distinct cases')
    evidence = [(incumbent, int(row.id), evaluate(incumbent, int(row.id))) for row in rows]
    low, high = Counter(), Counter()
    for row, (_, _, passed) in zip(rows, evidence, strict=True):
        if type(passed) is not bool:
            raise ValueError('Qualification requires exact boolean replies')
        low[row.family] -= passed
        high[row.family] += not passed
    calls = 0
    for row in rows:
        if min(high.values()) < 0 or sum(high.values()) < 1:
            break
        if min(low.values()) >= 0 and sum(low.values()) >= 1:
            break
        case = int(row.id)
        passed = evaluate(challenger, case)
        if type(passed) is not bool:
            raise ValueError('Qualification requires exact boolean replies')
        low[row.family] += passed
        high[row.family] -= not passed
        calls += 1
        evidence.append((challenger, case, passed))
    return min(low.values()) >= 0 and sum(low.values()) >= 1, calls, evidence


def run(matrix, held, seed, plan, route, policy, start):
    if policy == 'ordinary':
        return split.run(matrix, held, seed, plan, route)
    guard_halves = policy in ('split-departure', 'split-and-recall', 'split-and-reserve')
    reserve = policy in ('reserve-start-for-final', 'split-and-reserve')
    recall = reserve or policy in ('recall-start', 'split-and-recall')
    two = policy == 'two-at-start'
    audit = Counter()
    original_nominate, original_archive = archive.archive.nominate, archive.archive.qualify_archived

    def fresh(incumbent, challenger, rows, qualify, *, repeats, minimum_gain, seed, evaluation_limit):
        if incumbent == start:
            if guard_halves:
                rows = halves(rows)
            if two:
                minimum_gain = 2
        return certify_paired_qualification(incumbent, challenger, rows, qualify, repeats=repeats,
                                           minimum_gain=minimum_gain, seed=seed, evaluation_limit=evaluation_limit)

    def archived(incumbent, challenger, cases, qualify):
        if incumbent == start and guard_halves:
            return qualify_archive_halves(incumbent, challenger, cases, qualify)
        if incumbent == start and two:
            return margin.qualify_archive_margin(incumbent, challenger, cases, qualify, 2)
        return original_archive(incumbent, challenger, cases, qualify)

    def nominate(incumbent, history, attempted, role):
        previous = original_nominate(incumbent, history, attempted, role)
        final = len(history) == plan['schedule']['cycles'] - 1
        if reserve and not final and previous == start:
            audit.update(deferredStartNominations=1)
            return original_nominate(incumbent, history, attempted | {(incumbent, start)}, role)
        if recall and final and incumbent != start and (incumbent, start) not in attempted:
            audit.update(finalStartNominations=1, changedFinalNominations=int(previous != start))
            return start
        return previous

    with (patch.object(fixed_pool_cycle, 'certify_paired_qualification', fresh),
          patch.object(archive.archive, 'qualify_archived', archived),
          patch.object(archive.archive, 'nominate', nominate)):
        count, trace = split.run(matrix, held, seed, plan, route)
    if audit['finalStartNominations']:
        last = trace[-1]['decision']
        if last['archiveNominee'] != start:
            raise ValueError('The reserved start was not nominated on the final cycle')
        audit.update(finalStartPromotions=int(last['archivePromoted']))
    count.update(audit)
    return count, trace


def checked_report(name, expected):
    raw = (ROOT / 'docs' / f'{name}-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError(f'The archived {name} report differs from its published receipt')
    return split.read_json(raw)


def prepare(phase):
    parent, panels, references, _ = split.prepare(phase)
    stored = checked_report('routed-witness-split', SPLIT_SHA256)[phase]
    if stored['planSha256'] != digest(parent):
        raise ValueError('The routed source plan differs from the verified report')
    costs = checked_report('routed-model-cost-frontier', FRONTIER_SHA256) if phase == cost_frontier.PHASE else {}
    paths = ('benchmarks/routed_start_protection.py', 'benchmarks/routed_witness_split.py',
             'benchmarks/starting_prompt_margin.py', 'benchmarks/prompteval_archive_cycles.py',
             'cpo/paired_qualification.py')
    plan = {**{k: parent[k] for k in ('phase', 'schedule', 'searchCap', 'gepaVersion', 'validationRows')},
            'protocol': 'cpo-routed-start-protection-v1', 'parentPlanSha256': digest(parent),
            'splitReportSha256': SPLIT_SHA256, 'frontierReportSha256': FRONTIER_SHA256 if costs else None,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'routes': ROUTES, 'policies': POLICIES, 'matchedLossControl': GEPA_ANCHOR,
            'caseSensitivity': {'candidate': AUDITED, 'controls': FIXED_CONTROLS, 'draws': 4096, 'seed': 20261124},
            'scope': ('Compare a flat two-pass margin with nonnegative gain on both halves of the original '
                      'eight-case qualification while leaving the start. Recall the start on the final cycle '
                      'and test holding earlier archive opportunities for that cycle. Keep the original budgets '
                      'and separate holdout.')}
    return plan, panels, references, stored['panels'], costs.get('panels')


def start_metrics(matrix, held, start, final):
    retained = matrix[int(start)]
    selected = matrix[int(final)]
    gains = sum(retained[row] == '0' and selected[row] == '1' for row in held)
    losses = sum(retained[row] == '1' and selected[row] == '0' for row in held)
    return {'startPassesLost': losses, 'startPassesGained': gains, 'endsBelowStart': int(losses > gains),
            'endsAboveStart': int(gains > losses)}


def measure_panel(plan, matrix, held, expected, costs):
    methods = [(route, policy) for route in ROUTES for policy in POLICIES]
    points = {f'{route}/{policy}': Counter() for route, policy in methods}
    journals = {key: [] for key in points}
    affected = Counter()
    starts = cost_frontier.retained_prompts(matrix, held, plan['schedule'])
    control_finals = {}
    for label in FIXED_CONTROLS if costs else ():
        family, cap = label.split('-')
        mode = f'gepa-{family}.runner-up'
        control_finals[label], observed = uncertainty.final_prompts(
            matrix, held, plan['schedule'], plan, mode, int(cap))
        frontier.expect_reference(observed, costs['gepa'][mode][cap])
    gepa = control_finals.get('sequential-35', [None] * len(starts))
    audited_finals = []
    for seed, start, gepa_final in zip(plan['schedule']['seeds'], starts, gepa, strict=True):
        previous = {}
        retained = str(start)
        for route, policy in methods:
            key = f'{route}/{policy}'
            count, trace = run(matrix, held, seed, plan, route, policy, retained)
            points[key].update(count)
            journals[key].append(trace)
            chosen = trace[-1]['decision']['selected']
            if key == AUDITED:
                audited_finals.append(int(chosen))
            metrics = start_metrics(matrix, held, retained, chosen)
            points[key].update(metrics)
            delta = metrics['startPassesGained'] - metrics['startPassesLost']
            if policy == 'ordinary':
                previous[route] = delta
                if gepa_final == start and delta < 0 and route == ROUTES[0]:
                    affected.update(lossEpisodes=1, passDeficit=-delta)
            else:
                change = delta - previous[route]
                points[key].update(episodesGaining=int(change > 0), episodesLosing=int(change < 0))
                if gepa_final == start and previous[route] < 0 and route == ROUTES[0]:
                    points[key].update(originalStartLossPassesRecovered=change,
                                       originalStartLossEpisodesMatched=int(delta >= 0))
    results = {key: dict(count, paidLookups=count['searchPaid'] + count['qualificationPaid'],
                         traceSha256=digest(journals[key])) for key, count in points.items()}
    for route in ROUTES:
        frontier.expect_reference(results[f'{route}/ordinary'], expected[route])
    margins = {}
    if costs:
        case_counts = uncertainty.case_totals(matrix, held, audited_finals)
        if sum(case_counts.values()) != results[AUDITED]['holdoutPasses']:
            raise ValueError('The candidate holdout vectors differ from the replay')
        for label, finals in control_finals.items():
            control = uncertainty.case_totals(matrix, held, finals)
            margins[label] = [case_counts[case] - control[case] for case in held]
    return results, affected, margins


def case_ranges(subjects, settings):
    rng = Random(settings['seed'])
    samples = {label: [] for label in (*FIXED_CONTROLS, 'joint-cap-52')}
    for _ in range(settings['draws']):
        margins = Counter()
        for vectors in subjects.values():
            size = len(vectors[FIXED_CONTROLS[0]])
            indices = rng.choices(range(size), k=size)
            margins.update({label: sum(values[i] for i in indices) for label, values in vectors.items()})
        margins['joint-cap-52'] = min(margins['batched-52'], margins['sequential-52'])
        for label, scores in samples.items():
            scores.append(margins[label])
    return {label: [sorted(scores)[(len(scores) - 1) * q // 1000] for q in (25, 975)]
            for label, scores in samples.items()}


def replay(plan, panels, references, stored, costs):
    points, totals, affected, subjects = {}, {}, Counter(), {}
    for row in panels:
        subject, model, matrix = (row[k] for k in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = split.holdout(subject, len(matrix[0]))
        current, initial_losses, margins = measure_panel(plan, matrix, held, stored[name], costs[name] if costs else None)
        points[name] = {'methods': current, 'controls': {label: {k: references[name][label][k] for k in frontier.FIELDS}
                                                        for label in split.CONTROLS}}
        affected.update(initial_losses)
        if margins:
            cumulative = subjects.setdefault(subject, {label: [0] * len(held) for label in FIXED_CONTROLS})
            for label in margins:
                cumulative[label] = [a + b for a, b in zip(cumulative[label], margins[label], strict=True)]
        for method, result in {**current, **points[name]['controls']}.items():
            totals.setdefault(method, Counter()).update({k: v for k, v in result.items() if type(v) is int})
    comparison = {}
    if costs:
        comparison = frontier.summarize({name: {**row, 'cpo': points[name]['methods']} for name, row in costs.items()})
        if affected != {'lossEpisodes': 46, 'passDeficit': 90}:
            raise ValueError('The original matched losses from keeping the start differ')
    return {'plan': plan, 'planSha256': digest(plan), 'totals': totals, 'panels': points,
            'originalMatchedStartLosses': affected,
            'matchedCostComparisons': comparison.get('matchedCostComparisons', {}),
            'caseSensitivityRanges': case_ranges(subjects, plan['caseSensitivity']) if subjects else {}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=split.PHASES, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current phase seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
