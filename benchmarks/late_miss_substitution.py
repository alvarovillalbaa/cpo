"""Trade one late challenger screen for one new incumbent witness probe."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import bounded_miss_alternation as parent
from benchmarks import case_difficulty_allocation as inputs
from benchmarks import routed_score_allocation as route
from cpo._contract import digest
from cpo.lazy_incumbent import select_with_lazy_incumbent
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
CACHED_REPORT = '4b8f14cb5f5ae07f19f17deb2efef6f2994a36beb4d5be5422144d81d9444754'
FAILURES = 4
METHODS = ('substitute-tail-probe', 'original-witness-control')


def select(incumbent, candidates, validation, evaluate, *, metric_limit, stats):
    rows, candidates = tuple(validation), tuple(candidates)
    available = len(candidates[:max(0, metric_limit - (2 * len(rows) - 1))])
    if available < FAILURES + 2:
        return select_with_lazy_incumbent(incumbent, candidates, rows, evaluate, metric_limit=metric_limit)
    known = {}

    def observe(prompt, row):
        key = (prompt, row.id)
        if key not in known:
            if len(known) >= metric_limit:
                raise ValueError('The substitution cannot exceed the original search allowance')
            response = evaluate(prompt, row)
            if type(response.passed) is not bool:
                raise ValueError('Validation requires exact boolean outcomes')
            known[key] = response
        return known[key]

    first_index = next((i for i, row in enumerate(rows) if not observe(incumbent, row).passed), None)
    if first_index is None:
        return FinalistResult(incumbent, None, len(known))
    first, second = rows[first_index], rows[first_index]
    # In the deferred route, a miss on the first row implies the router
    # already saw the incumbent pass the second row.
    alternate_index = max(2, first_index + 1)
    for index, prompt in enumerate(candidates):
        if index == available:
            break
        if index == FAILURES and alternate_index < len(rows):
            available -= 1
            stats.update(tailProbesSubstituted=1)
            new_case = rows[alternate_index]
            if not observe(incumbent, new_case).passed:
                second = new_case
                stats.update(alternateMisses=1)
        witness = second if index >= FAILURES and (index - FAILURES) % 2 == 0 else first
        stats.update(alternateProbes=int(witness != first))
        if not observe(prompt, witness).passed:
            continue
        stats.update(alternateFinalists=int(witness != first))
        ordered = rows if witness == first else (witness, *(row for row in rows if row != witness))
        proof = select_with_lazy_incumbent(incumbent, (prompt,), ordered, observe, metric_limit=metric_limit - index)
        return FinalistResult(proof.prompt, proof.finalist, len(known))
    return FinalistResult(incumbent, None, len(known))


def episode(matrix, held, seed, plan, start, *, alternate):
    if not alternate:
        return route.run(matrix, held, seed, plan, start, 'strict')
    stats = Counter()

    def substitute(incumbent, candidates, rows, evaluate, *, metric_limit):
        stats.update(deferredScreens=1)
        return select(incumbent, candidates, rows, evaluate, metric_limit=metric_limit, stats=stats)

    with patch.object(route.ties.split, 'select_with_lazy_incumbent', substitute):
        counts, trace = route.run(matrix, held, seed, plan, start, 'strict')
    counts.update(stats)
    return counts, trace


def prepare():
    parent_design, data = parent.prepare()
    inputs.checked_file('docs/cached-miss-alternation-results-v1.json', CACHED_REPORT)
    sources = ('benchmarks/late_miss_substitution.py', 'benchmarks/bounded_miss_alternation.py',
               'benchmarks/routed_witness_split.py', 'cpo/lazy_incumbent.py')
    design = {'protocol': 'cpo-late-miss-substitution-v1', 'parentDesignSha256': digest(parent_design),
              'cachedExperimentSha256': CACHED_REPORT, 'failuresBeforeSubstitution': FAILURES,
              'methods': METHODS, 'primary': METHODS[0], 'controls': parent.CONTROLS,
              'scope': ('Keep the original first probe through four consecutive challenger failures. '
                        'Trade one tail screen for one incumbent reply after the routing and witness reads. '
                        'If it is a miss, alternate later challengers between the two misses. '
                        'Keep the original proof reserve, exact gate, and separate qualification.'),
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in sources}}
    return design, data


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, data = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for _, _, plan, _ in data.values()):
        cli.error('Use pinned GEPA 0.1.4')
    with patch.multiple(parent, METHODS=METHODS, episode=episode):
        results = {name: parent.measure(*args) for name, args in data.items()}
    for cohort in results.values():
        for points in cohort['panels'].values():
            if any(points[METHODS[1]][field] != points['strict'][field] for field in inputs.FIELDS):
                raise ValueError('The original control must preserve all recorded traces and costs')
    with args.out.open('x') as stream:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
