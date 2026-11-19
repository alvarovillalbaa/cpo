"""Try prompts from an episode's earlier cycles on a fresh qualification panel."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_continuous as continuous, prompteval_transfer as transfer
from cpo import Observation, Row
from cpo._contract import digest, unique_object
from cpo.challenger import certify_challenger


ROOT = Path(__file__).resolve().parents[1]
METHODS = (continuous.CPO[0], *continuous.GEPA)
POLICIES = ('base', 'retired', 'runner-up')
PHASES = ('development', 'retrospective-transfer')


def nominate(incumbent, history, attempted, policy):
    """Walk backwards through prior search decisions, once per directed pair."""
    for previous in reversed(history):
        displaced = previous['incumbent'] != previous['selected']
        if not displaced and policy == 'retired':
            continue
        alternate = previous['incumbent'] if displaced else previous['challenger']
        if alternate is not None and alternate != incumbent and (incumbent, alternate) not in attempted:
            return alternate
    return None


def qualify_archived(incumbent, challenger, cohort, evaluate):
    rows = tuple(Row(str(case), 'task') for case in cohort)
    baseline = {row.id: evaluate(incumbent, int(row.id)) for row in rows}
    result = certify_challenger(rows, baseline, lambda row: Observation(evaluate(challenger, int(row.id)), {}),
                                metric_limit=len(rows))
    evidence = [(incumbent, int(case), passed) for case, passed in baseline.items()]
    evidence.extend((challenger, int(case), passed) for case, passed in result.observations.items())
    return result.status == 'promote', result.evaluations, evidence


def combine_qualification(first, second):
    evidence = {}
    for prompt, case, passed in (*first, *second):
        if evidence.setdefault((prompt, case), passed) is not passed:
            raise ValueError('Qualification replay contains contradictory outcomes')
    return [(prompt, case, passed) for (prompt, case), passed in evidence.items()]


def prepare(phase, search_cap):
    original, data = continuous.prepare(phase)
    path = ROOT / 'docs/prompteval-continuous-results-v1.json'
    raw = path.read_bytes()
    archived = json.loads(raw, object_pairs_hook=unique_object)[phase]
    seal = digest(original)
    if seal != archived['planSha256'] or original['minimumQualificationGain'] != 1:
        raise ValueError('The source continuous-prompt replay must reproduce its published seal and promotion gate')
    published_cap = original['evaluationLookupLimit']
    cap = published_cap if search_cap is None else search_cap
    if not original['validationRows'] + original['qualificationRowsPerCycle'] <= cap <= published_cap:
        raise ValueError('Search cap must leave room for incumbent validation after an archive check')
    plan = {'protocol': 'cpo-prompteval-archive-cycles-v1', 'phase': phase, 'basePlanSha256': seal,
            'archivedResultSha256': sha256(raw).hexdigest(), 'corpusSha256': original['corpusSha256'],
            'gepaVersion': original['gepaVersion'], 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'policies': list(POLICIES), 'methods': list(METHODS), 'cycles': original['cycles'], 'searchCap': cap,
            'reproducesPublishedBaseline': cap == published_cap,
            'archive': 'One prompt per cycle, nominated from completed earlier cycles of the same optimizer and episode',
            'accounting': 'Charge each distinct qualification lookup and reduce fallback search by the archive challenger cost',
            'retry': 'A directed archive comparison is allowed once per episode'}
    return plan, {**original, 'evaluationLookupLimit': cap}, archived, data


def episode(matrix, holdout, seed, plan):
    start, layouts = continuous.schedule(len(matrix[0]), len(matrix), holdout, seed, plan)
    all_qualification = [case for layout in layouts for case in layout['qualify']]
    search = {case for layout in layouts for role in ('train', 'validation') for case in layout[role]}
    if len(set(all_qualification)) != len(all_qualification) or (set(all_qualification) & (search | set(holdout))) or (
            search & set(holdout)):
        raise ValueError('Holdout, search, and each cycle qualification must remain disjoint')
    cap = plan['evaluationLookupLimit']
    results, cached_search = {}, {}

    def evaluate(prompt, case):
        return matrix[int(prompt)][case] == '1'

    for method in METHODS:
        for policy in POLICIES:
            history, attempted, trace = [], set(), []
            incumbent = start
            for index, layout in enumerate(layouts):
                cohort = layout['qualify']
                challenger = None if policy == 'base' else nominate(incumbent, history, attempted, policy)
                archive_promoted, archive_fresh, reserve = False, 0, []
                if challenger is not None:
                    if challenger in layout['alternatives']:
                        raise ValueError('Archive candidate already belongs to the fresh proposal block')
                    attempted.add((incumbent, challenger))
                    archive_promoted, archive_fresh, reserve = qualify_archived(incumbent, challenger, cohort, evaluate)
                if archive_promoted:
                    step = {'incumbent': incumbent, 'challenger': challenger, 'selected': challenger,
                            'searchLookups': 0, 'qualification': [], 'searchSha256': digest([])}
                else:
                    remaining = cap - archive_fresh
                    key = method, index, incumbent, remaining
                    if key not in cached_search:
                        with patch.object(transfer, 'LOOKUP_LIMIT', remaining):
                            cached_search[key] = continuous.step(method, matrix, incumbent, layout,
                                                                 {**plan, 'evaluationLookupLimit': remaining})
                    step = cached_search[key]
                paid = combine_qualification(reserve, step['qualification'])
                if len(paid) + step['searchLookups'] > cap + 2 * len(cohort):
                    raise ValueError('The archive policy exceeded the original combined lookup cap')
                history.append(step)
                trace.append({**step, 'qualification': paid, 'qualificationLookups': len(paid),
                              'archiveNominee': challenger, 'archivePromoted': archive_promoted})
                incumbent = step['selected']
            results[f'{method}.{policy}'] = {'candidate': incumbent, 'steps': trace,
                                              'holdoutPasses': sum(evaluate(incumbent, case) for case in holdout),
                                              'evaluations': sum(s['searchLookups'] + s['qualificationLookups'] for s in trace)}
    return results


def summarize(episodes):
    names = tuple(episodes[0])
    totals = {}
    for name in names:
        results = [one[name] for one in episodes]
        steps = [step for result in results for step in result['steps']]
        totals[name] = {'holdoutPasses': sum(result['holdoutPasses'] for result in results),
                        'searchLookups': sum(s['searchLookups'] for s in steps),
                        'qualificationLookups': sum(s['qualificationLookups'] for s in steps),
                        'promotions': sum(s['incumbent'] != s['selected'] for s in steps)}
    archive_counts = {}
    for name in names:
        if name.endswith('.base'):
            continue
        steps = [step for episode in episodes for step in episode[name]['steps']]
        archive_counts[name] = {'attempted': sum(step['archiveNominee'] is not None for step in steps),
                                'accepted': sum(step['archivePromoted'] for step in steps)}
    comparisons = {}
    for policy in POLICIES:
        candidate = f'{METHODS[0]}.{policy}'
        refs = [f'{arm}.{policy}' for arm in METHODS[1:]]
        if policy != 'base':
            refs.append(f'{METHODS[0]}.base')
        comparisons[policy] = {}
        for control in refs:
            gain = totals[candidate]['holdoutPasses'] - totals[control]['holdoutPasses']
            cost = sum(one[candidate]['evaluations'] for one in episodes)
            cost_ref = sum(one[control]['evaluations'] for one in episodes)
            comparisons[policy][control] = {'deltaPasses': gain, 'deltaLookups': cost - cost_ref,
                                            'qualified': gain >= 0 and cost <= cost_ref and
                                                         (gain > 0 or 10 * cost <= 9 * cost_ref)}
    return {'totals': totals, 'archive': archive_counts, 'comparisons': comparisons}


def replay(plan, original, archived, source):
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[x] for x in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        outcomes = [episode(matrix, held, seed, original) for seed in original['seeds']]
        result = summarize(outcomes)
        if plan['reproducesPublishedBaseline'] and any(
                result['totals'][f'{arm}.base'] != archived['panels'][name]['totals'][arm] for arm in METHODS):
            raise ValueError('The source continuous replay does not reproduce its original results')
        result['publishedFullCapControls'] = {}
        for arm in METHODS[1:]:
            base = archived['panels'][name]['totals'][arm]
            ref = base['searchLookups'] + base['qualificationLookups']
            comparisons = {}
            for policy in POLICIES:
                current = result['totals'][f'{METHODS[0]}.{policy}']
                gain = current['holdoutPasses'] - base['holdoutPasses']
                cost = current['searchLookups'] + current['qualificationLookups']
                comparisons[policy] = {'deltaPasses': gain, 'deltaLookups': cost - ref,
                                       'qualified': gain >= 0 and cost <= ref and (gain > 0 or 10 * cost <= 9 * ref)}
            result['publishedFullCapControls'][arm] = comparisons
        result['episodeTraceSha256'] = digest(outcomes)
        panels[name] = result
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=PHASES, required=True)
    parser.add_argument('--search-cap', type=int)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, original, archived, source = prepare(args.phase, args.search_cap)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, original, archived, source)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
