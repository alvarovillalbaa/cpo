"""Diversify the deferred screen using incumbent misses observed in earlier cycles."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import bounded_miss_alternation as previous
from benchmarks import case_difficulty_allocation as parent
from benchmarks import routed_score_allocation as route
from cpo._contract import digest
from cpo.lazy_incumbent import select_with_lazy_incumbent
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
BOUNDED_REPORT = '90c4872bfd6d125a666c2cefb16afd366839ef1dd75fcb6ed561d88996eef0da'
METHODS = ('cached-alternate', 'cache-observed-control')


def select(incumbent, candidates, validation, evaluate, *, metric_limit, prior, stats):
    rows, candidates = tuple(validation), tuple(candidates)
    misses = tuple(row for row in rows if prior.get(row.id, {}).get(incumbent) is False)
    limit = max(0, metric_limit - (2 * len(rows) - 1))
    if not misses or limit < 2 or len(candidates) < 2:
        return select_with_lazy_incumbent(incumbent, candidates, rows, evaluate, metric_limit=metric_limit)
    known = {}

    def observe(prompt, row):
        key = (prompt, row.id)
        if key not in known:
            if len(known) >= metric_limit:
                raise ValueError('The cached alternate must stay within the existing search cap')
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Validation requires exact boolean outcomes')
            known[key] = reply
        return known[key]

    first = next((row for row in rows if not observe(incumbent, row).passed), None)
    if first is None:
        raise ValueError('Earlier and current incumbent evidence contradict one another')
    # Prefer a miss another prompt has already answered correctly. The stable
    # order among equal cases comes from the current validation schedule.
    second = max((row for row in misses if row != first),
                 key=lambda row: any(prior[row.id].values()), default=first)
    stats.update(cyclesWithCachedAlternate=int(second != first))
    for index, prompt in enumerate(candidates[:limit]):
        witness = second if index % 2 else first
        stats.update(alternateProbes=int(witness != first))
        if not observe(prompt, witness).passed:
            continue
        stats.update(alternateFinalists=int(witness != first))
        ordered = rows if witness == first else (witness, *(row for row in rows if row != witness))
        result = select_with_lazy_incumbent(incumbent, (prompt,), ordered, observe, metric_limit=metric_limit - index)
        return FinalistResult(result.prompt, result.finalist, len(known))
    return FinalistResult(incumbent, None, len(known))


def episode(matrix, held, seed, plan, start, *, alternate):
    split = route.ties.split
    cycle = split.fixed_pool_cycle
    cycle_search = cycle.run_fixed_pool_cycle
    history, stats = {}, Counter()
    prior = {}

    def track(incumbent, candidates, rows, cohort, evaluate, **kwargs):
        nonlocal prior
        prior = {row.id: history[row.id].copy() for row in rows if row.id in history}

        def observe(prompt, row):
            reply = evaluate(prompt, row)
            known = history.setdefault(row.id, {})
            if known.setdefault(prompt, reply.passed) is not reply.passed:
                raise ValueError('Reused validation outcomes must agree')
            return reply

        return cycle_search(incumbent, candidates, rows, cohort, observe, **kwargs)

    def deferred(incumbent, candidates, rows, evaluate, *, metric_limit):
        stats.update(deferredScreens=1)
        return select(incumbent, candidates, rows, evaluate, metric_limit=metric_limit, prior=prior, stats=stats)

    with patch.object(cycle, 'run_fixed_pool_cycle', track):
        if alternate:
            with patch.object(split, 'select_with_lazy_incumbent', deferred):
                measured, trace = route.run(matrix, held, seed, plan, start, 'strict')
        else:
            measured, trace = route.run(matrix, held, seed, plan, start, 'strict')
    if sum(map(len, history.values())) != measured['searchPaid']:
        raise ValueError('Screen evidence must equal previously paid validation lookups')
    measured.update(stats)
    return measured, trace


def prepare():
    parent_design, inputs = previous.prepare()
    parent.checked_file('docs/bounded-miss-alternation-results-v1.json', BOUNDED_REPORT)
    files = ('benchmarks/cached_miss_alternation.py', 'benchmarks/bounded_miss_alternation.py',
             'benchmarks/archive_complementarity_transfer.py', 'cpo/lazy_incumbent.py')
    design = {'protocol': 'cpo-cached-miss-alternation-v1', 'parentDesignSha256': digest(parent_design),
              'parentReportSha256': BOUNDED_REPORT, 'methods': METHODS, 'primary': METHODS[0],
              'controls': previous.CONTROLS,
              'scope': ('Keep the original incumbent miss for the first challenger. Alternate later first probes with '
                        'one same-incumbent missed case from earlier paid validation. Prefer a case another '
                        'prompt previously passed. Buy no additional incumbent replies to discover it. '
                        'Keep the same strict validation and qualification gates.'),
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in files}}
    return design, inputs


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
    if any(version('gepa') != plan['gepaVersion'] for _, _, plan, _ in inputs.values()):
        parser.error('Use pinned GEPA 0.1.4')
    with patch.multiple(previous, METHODS=METHODS, episode=episode):
        results = {key: previous.measure(*value) for key, value in inputs.items()}
    for cohort in results.values():
        for point in cohort['panels'].values():
            for field in parent.FIELDS:
                if point[METHODS[1]][field] != point['strict'][field]:
                    raise ValueError('Cache observation by itself must preserve the exact baseline trace and costs')
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
