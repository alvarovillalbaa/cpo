"""Reprice verified CPO and GEPA trajectories with the same evidence reuse."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import bounded_discovery_transfer as transfer
from benchmarks import prompteval_archive_cycles as archive
from benchmarks import prompteval_continuous as continuous
from benchmarks import prompteval_paid_witness as paid
from benchmarks import prompteval_qualification_bounds as qualification
from benchmarks import prompteval_single_finalist as first
from benchmarks import prompteval_transfer as gepa
from benchmarks import prompteval_validation_size as smaller
from benchmarks.prompteval_validation_transfer import CPO
from cpo._contract import digest, unique_object
from cpo.bounded_discovery import select_with_bounded_discovery
from cpo.lazy_incumbent import select_with_lazy_incumbent


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = 'bf93b81c903577f4a8b2272e58abdbb787f3118f619a81c057004899f3d8b621'
CPO_METHODS = ('deferred-first-gain', transfer.METHOD)
GEPA_METHODS = tuple(first.METHODS[1:])
METHODS = (*CPO_METHODS, *GEPA_METHODS)


def record(log, prompt, case, passed):
    if type(passed) is not bool or log.setdefault((prompt, case), passed) is not passed:
        raise ValueError('The same recorded lookup must have one exact outcome')
    return passed


def captured_episode(matrix, held, seed, original, cpo_method, validation_rows):
    logs = {m: [] for m in first.METHODS}
    original_gepa = gepa.optimize_gepa
    selector = (select_with_lazy_incumbent if cpo_method == CPO_METHODS[0]
                else select_with_bounded_discovery)

    def measure_cpo(incumbent, candidates, validation, evaluate, *, metric_limit, screen):
        if screen != 'first-gain':
            raise ValueError('Expected the archived first-gain CPO entry point')
        log = {}
        logs[CPO].append(log)

        def observe(prompt, row):
            reply = evaluate(prompt, row)
            record(log, prompt, int(row.id), reply.passed)
            return reply

        return selector(incumbent, candidates, validation, observe, metric_limit=metric_limit)

    def measure_gepa(initial, alternatives, train, validation, evaluate, *, batched, seed):
        log = {}
        logs[GEPA_METHODS[int(batched)]].append(log)

        def observe(prompt, case):
            return record(log, prompt, case, evaluate(prompt, case))

        return original_gepa(initial, alternatives, train, validation, observe, batched=batched, seed=seed)

    arms = archive.METHODS if cpo_method == CPO_METHODS[0] else archive.METHODS[:1]
    with patch.object(archive, 'METHODS', arms), patch.object(first, 'select_single_finalist', measure_cpo), patch.object(
            gepa, 'optimize_gepa', measure_gepa):
        outcomes = first.screened_episode(matrix, held, seed, original, 'first-gain')
    _, layouts = smaller.narrow_schedule(
        *continuous.schedule(len(matrix[0]), len(matrix), held, seed, original), validation_rows)
    return {cpo_method if method == CPO else method: (trace, episode_cost(trace, layouts, logs[method]))
            for method, trace in outcomes.items()}


def episode_cost(trace, layouts, journals):
    """Verify every recorded cycle and discount only exact repeat observations."""
    pending = iter(journals)
    cache = {}
    total = Counter(holdoutPasses=trace['holdoutPasses'], searchLookups=0, searchAfterReuse=0,
                    fullQualification=0, qualificationAfterStop=0)
    for step, layout in zip(trace['steps'], layouts, strict=True):
        replies = {} if step['archivePromoted'] else next(pending, None)
        if replies is None:
            raise ValueError('Missing search journal for a completed cycle')
        calls = [(prompt, case, passed) for (prompt, case), passed in replies.items()]
        scope = set(layout['train']) | set(layout['validation'])
        prompts = {*layout['alternatives'], step['incumbent']}
        if (len(calls) != step['searchLookups'] or digest(calls) != step['searchSha256'] or
                any(prompt not in prompts or case not in scope for prompt, case, _ in calls)):
            raise ValueError('The captured search journal does not match the sealed cycle')
        before = len(cache)
        for prompt, case, passed in calls:
            record(cache, prompt, case, passed)
        prefix, _ = qualification.qualification_cost(step, layout)
        total.update(searchLookups=len(calls), searchAfterReuse=len(cache) - before,
                     fullQualification=step['qualificationLookups'], qualificationAfterStop=prefix)
    if next(pending, None) is not None or total['searchLookups'] + total['fullQualification'] != trace['evaluations']:
        raise ValueError('The captured episode totals do not reconcile')
    return total


def prepare(phase):
    raw = (ROOT / 'docs/bounded-discovery-transfer-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('The archived transfer report differs')
    published = json.loads(raw, object_pairs_hook=unique_object)['runs'][phase]['report']
    settings, original = transfer.design()
    parent, original, data = transfer.prepare(phase, settings, original)
    if digest(parent) != published['planSha256']:
        raise ValueError('The transfer seal differs')
    inputs = ['benchmarks/prompteval_qualification_bounds.py', 'cpo/paired_qualification.py']
    plan = {
        'protocol': 'cpo-bounded-transfer-matched-cost-v1', 'phase': phase,
        'parentPlanSha256': digest(parent), 'parentReportSha256': SOURCE_SHA256,
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'dependenciesSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in inputs},
        'gepaVersion': parent['gepaVersion'], 'validationRows': parent['validationRowsAndSearchCap'][0],
        'gate': parent['gate'], 'methods': list(METHODS),
        'accounting': 'One charge per exact search pair per arm and episode. Stop fresh qualification at a decisive reply.',
        'scope': 'Fixed logical budgets, archive checks, proposal streams, nominations and promotions. Savings are not reallocated.',
    }
    return plan, original, data, published['panels']


def summary(total):
    return {**total, 'originalPaidLookups': total['searchLookups'] + total['fullQualification'],
            'paidLookups': total['searchAfterReuse'] + total['qualificationAfterStop']}


def replay(plan, original, data, published):
    panels = {}
    for panel in data:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        totals, traces = {m: Counter() for m in METHODS}, {m: [] for m in METHODS}
        for seed in original['seeds']:
            for method in CPO_METHODS:
                episode = captured_episode(matrix, held, seed, original, method, plan['validationRows'])
                for arm, (trace, costs) in episode.items():
                    totals[arm].update(costs)
                    traces[arm].append(trace)
        baseline = published[name]
        for method in METHODS:
            if digest(traces[method]) != baseline['traceSha256'][method] or first.totals(traces[method]) != (
                    baseline['totals'][method]):
                raise ValueError('An archived optimizer trace did not reproduce exactly')
        totals = {method: summary(total) for method, total in totals.items()}
        panels[name] = {'totals': totals, 'pairedGates': {method: {control: paid.meets_gate(
            totals[method], totals[control]) for control in GEPA_METHODS} for method in CPO_METHODS}}
    qualified = {m: [name for name, row in panels.items() if all(row['pairedGates'][m].values())]
                 for m in CPO_METHODS}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels, 'panelsClearingBothGates': qualified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=transfer.SOURCES, required=True)
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
