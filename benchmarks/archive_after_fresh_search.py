"""Measure archive retries that cannot preempt fresh prompt search."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import cached_miss_witness as cached
from benchmarks import episode_screen_adaptation as screens
from benchmarks.prompteval_paid_witness import meets_gate
from cpo import Observation, Row
from cpo._contract import digest
from cpo.challenger import certify_challenger
from cpo.fixed_pool_cycle import run_fixed_pool_cycle


CACHED_REPORT_SHA256 = '78391d1ceac218cc51e68c8d411ed2d3073a0ef8c5ad49c1d34c9ac86e4f8a29'
WITNESSES = ('seeded', 'two-prior-passes')
ORDERINGS = ('preflight', 'fresh-first')
INCIDENT = ('lmentry-ends_with_word/flan-t5-xxl', 47690)


def certify_archived(incumbent, nominee, rows, replies, evaluate, remaining):
    """Meter only new replies and retain the gate from archive preflight."""
    missing = sum((incumbent, row.id) not in replies for row in rows)
    if remaining <= missing:
        return None
    baseline = {row.id: evaluate(incumbent, row) for row in rows}
    return certify_challenger(rows, baseline, lambda row: Observation(evaluate(nominee, row), {}),
                              metric_limit=remaining - missing)


def run_fresh_first(matrix, held, seed, original, plan, witness_policy):
    incumbent, layouts = archive.smaller.narrow_schedule(
        *archive.continuous.schedule(len(matrix[0]), len(matrix), held, seed, original), plan['validationRows'])
    totals = Counter(searchPaid=0, qualificationPaid=0, searchLogical=0, archiveAttempts=0,
                     archivePromotions=0, archiveBudgetSkips=0, freshPromotions=0)
    past, attempted, cache, history, traces = [], set(), {}, {}, []
    for layout in layouts:
        candidates = layout['alternatives']
        nominee = archive.archive.nominate(incumbent, past, attempted, 'runner-up')
        validation = tuple(Row(str(case), 'task') for case in layout['validation'])
        qualification = tuple(Row(str(case), 'task') for case in layout['qualify'])
        witness = cached.choose_witness(incumbent, validation, history, witness_policy)
        if witness is not None:
            validation = (witness, *(row for row in validation if row != witness))
        search_roster = {incumbent, *candidates}
        qualification_roster = search_roster | {nominee}
        search_ids, qualification_ids = {row.id for row in validation}, {row.id for row in qualification}
        search, replies, requested = {}, {}, []
        prior_cost = len(cache)

        def evaluate(prompt, row):
            if prompt not in search_roster or row.id not in search_ids:
                raise ValueError('Search left the original roster or validation cases')
            key = (prompt, row.id)
            if key not in cache:
                cache[key] = matrix[int(prompt)][int(row.id)] == '1'
            passed = cache[key]
            search[key] = passed
            history.setdefault(row.id, {})[prompt] = passed
            return Observation(passed, {'correct': passed})

        def qualify(prompt, row):
            if prompt not in qualification_roster or row.id not in qualification_ids:
                raise ValueError('Qualification left the original roster or reserved cases')
            key = (prompt, row.id)
            if key not in replies:
                replies[key] = matrix[int(prompt)][int(row.id)] == '1'
            return replies[key]

        def qualify_fresh(prompt, row, repeat):
            if repeat != 0:
                raise ValueError('The replay requires one qualification repeat')
            passed = qualify(prompt, row)
            requested.append((prompt, row.id, passed))
            return passed

        fresh = run_fixed_pool_cycle(incumbent, candidates, validation, qualification, evaluate,
                                     metric_limit=plan['searchCap'], qualify=qualify_fresh, seed=layout['seed'])
        if (fresh.search.evaluations != len(search) or fresh.qualification_evaluations != len(requested) or
                (fresh.qualification is not None and fresh.qualification.status == 'undecided')):
            raise ValueError('The fresh lookup ledger disagrees with the public cycle')
        total_cap = plan['searchCap'] + 2 * len(qualification)
        available = total_cap - len(search) - len(replies)
        archive_status, selected = 'not-attempted', fresh.prompt
        if not fresh.promoted and nominee is not None:
            fallback = certify_archived(incumbent, nominee, qualification, replies, qualify, available)
            if fallback is None:
                totals['archiveBudgetSkips'] += 1
                archive_status = 'insufficient-budget'
            else:
                attempted.add((incumbent, nominee))
                totals['archiveAttempts'] += 1
                archive_status = fallback.status
                if fallback.status == 'promote':
                    selected = nominee
                    totals['archivePromotions'] += 1
        if len(search) + len(replies) > total_cap:
            raise ValueError('Fresh search and archive exceeded the original combined cap')
        step = {'incumbent': incumbent, 'challenger': fresh.search.prompt, 'selected': selected,
                'archiveNominee': nominee, 'archivePromoted': archive_status == 'promote'}
        traces.append({'decision': step, 'witness': witness.id if witness else None,
                       'searchFinalist': fresh.search.finalist, 'archiveStatus': archive_status,
                       'searchSha256': digest(list(search.items())),
                       'qualificationSha256': digest(list(replies.items()))})
        past.append(step)
        totals.update(searchLogical=len(search), searchPaid=len(cache) - prior_cost,
                      qualificationPaid=len(replies), freshPromotions=int(fresh.promoted))
        incumbent = selected
    totals['holdoutPasses'] = sum(matrix[int(incumbent)][case] == '1' for case in held)
    return totals, traces


def prepare(phase):
    parent, original, data, gepa, _ = cached.prepare(phase)
    prior = archive.checked_report('cached-miss-witness-results-v1.json', CACHED_REPORT_SHA256, phase)
    if digest(parent) != prior['planSha256']:
        raise ValueError('The cached-witness plan differs from the published controls')
    plan = {
        **{k: parent[k] for k in ('phase', 'gepaReportSha256', 'fixedPoolReportSha256', 'gepaVersion',
                                'searchCap', 'validationRows', 'gate')},
        'protocol': 'cpo-archive-after-fresh-search-v1', 'cachedWitnessPlanSha256': digest(parent),
        'cachedWitnessReportSha256': CACHED_REPORT_SHA256, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'witnesses': list(WITNESSES), 'orderings': list(ORDERINGS), 'diagnosticEpisode': list(INCIDENT),
        'scope': ('Offer fresh search the original search ceiling before an archive retry. '
                  'An archive retry uses remaining combined capacity and shared incumbent qualification replies.'),
    }
    return plan, original, data, gepa, prior['panels']


def replay(plan, original, data, gepa, prior):
    panels, incident = {}, {}
    for panel in data:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        methods, episode_passes = {}, {}
        for witness in WITNESSES:
            for order in ORDERINGS:
                method = f'{witness}/{order}'
                total, traces = Counter(), []
                episode_passes[method] = []
                for seed in original['seeds']:
                    if order == 'preflight':
                        measured, trace, _ = cached.run_episode(matrix, held, seed, original, plan, witness)
                    else:
                        measured, trace = run_fresh_first(matrix, held, seed, original, plan, witness)
                    total.update(measured)
                    traces.append(trace)
                    episode_passes[method].append(measured['holdoutPasses'])
                    if (name, seed) == INCIDENT:
                        incident[method] = {'holdoutPasses': measured['holdoutPasses'],
                                            'steps': [cycle['decision'] for cycle in trace]}
                result = dict(total, paidLookups=total['searchPaid'] + total['qualificationPaid'],
                              traceSha256=digest(traces))
                if order == 'preflight':
                    expected = prior[name]['policies'][witness]
                    keys = ('holdoutPasses', 'searchLogical', 'searchPaid', 'qualificationPaid', 'paidLookups', 'traceSha256')
                    if any(result[key] != expected[key] for key in keys):
                        raise ValueError(f'{name} {method} differs from the published preflight path')
                result['pairedPassesVsSeededPreflight'] = screens.paired_deltas(
                    episode_passes[method], episode_passes['seeded/preflight'])
                methods[method] = result
        controls = {key: {k: row[k] for k in ('holdoutPasses', 'paidLookups')}
                    for key, row in gepa[name]['reinvested'].items()}
        gates = {method: {key: meets_gate(result, control) for key, control in controls.items()}
                 for method, result in methods.items()}
        panels[name] = {'methods': methods, 'gepa': controls, 'gates': gates}
    names = (f'{witness}/{order}' for witness in WITNESSES for order in ORDERINGS)
    qualified = {method: [name for name, panel in panels.items() if all(panel['gates'][method].values())]
                 for method in names}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels, 'panelsClearingBothGates': qualified,
            'diagnosticEpisode': incident}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=archive.controls.reference.transfer.SOURCES, required=True)
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
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
