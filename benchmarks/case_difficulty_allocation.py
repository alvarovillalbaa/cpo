"""Test case-specific forecasts in the existing posterior-wide replay."""

import argparse
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import posterior_model_transfer as latest
from benchmarks import routed_score_allocation as original
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
COHORTS = {
    'llama-mistral': ('routed-start-model-confirmation', 'routed-score-allocation',
                     'c0b444d66986002f84fdeb46d22c3b459eda3d63a5c1d3ebae4130a935e381c8',
                     '096f581ea76be3be25bd109167d7a944c2825debd16f760796d23b1b1f38dd49'),
    'gemma-flan': ('posterior-model-transfer', 'posterior-model-transfer',
                   '6cefcc4ccc4d2dd197dcdff2294b178e14ccdd5de6819e03b66edf821b09efec',
                   'bfd185a56e9fbe648d1b3efd5fa3107338314a9190c3a60422327fac60ed6dc5'),
}
CANDIDATE = 'case-difficulty-wide'
ODDS = (0.25, 0.5, 1, 2, 4)
FIELDS = ('holdoutPasses', 'paidLookups', 'traceSha256')


@lru_cache(maxsize=8192)
def proof_chance(seen, pending, target):
    """Integrate a prompt's odds multiplier over independent row outcomes."""
    total, proof = 0.0, 0.0
    for multiplier in ODDS:
        def adjusted(passes, reads):
            odds = multiplier * (passes + 1) / (reads - passes + 1)
            return odds / (1 + odds)

        likelihood = 1.0
        for passes, reads, outcome in seen:
            chance = adjusted(passes, reads)
            likelihood *= chance if outcome else 1 - chance
        total += likelihood

        distribution = [1.0]
        for passes, reads, required in pending:
            chance = adjusted(passes, reads)
            next_counts = [0.0] * (len(distribution) + 1)
            for score, mass in enumerate(distribution):
                if not required:
                    next_counts[score] += mass * (1 - chance)
                next_counts[score + 1] += mass * chance
            distribution = next_counts
        proof += likelihood * sum(distribution[max(0, target):])
    return proof / total


def allocate(incumbent, candidates, rows, observe, journal, *, limit):
    """Change the forecast only. Preserve the original exact search rules."""
    baseline = {row.id: observe(incumbent, row).passed for row in rows}
    protected = {row.id for row in rows if row.critical and baseline[row.id]}
    successes = Counter(baseline)
    reads = Counter(dict.fromkeys(baseline, 1))
    order = {prompt: index for index, prompt in enumerate((incumbent, *candidates))}
    pending = {prompt: list(rows) for prompt in candidates}
    known = {prompt: {} for prompt in candidates}
    leader, best = incumbent, sum(baseline.values())
    while pending:
        priorities = {}
        for prompt, unread in pending.items():
            evidence = known[prompt]
            needed = best + (order[prompt] > order[leader]) - sum(evidence.values())
            if len(unread) > limit - len(journal) or len(unread) < needed:
                continue
            seen = tuple((successes[case] - outcome, reads[case] - 1, outcome)
                         for case, outcome in evidence.items())
            unknown = tuple((successes[row.id], reads[row.id], row.id in protected) for row in unread)
            priorities[prompt] = proof_chance(seen, unknown, needed), -len(unread), -order[prompt]
        if not priorities:
            break
        prompt = max(priorities, key=priorities.__getitem__)
        row = min(pending[prompt], key=lambda row: (
            row.id not in protected, Fraction(successes[row.id] + 1, reads[row.id] + 2)))
        pending[prompt].remove(row)
        passed = known[prompt][row.id] = observe(prompt, row).passed
        successes[row.id] += passed
        reads[row.id] += 1
        if row.id in protected and not passed:
            del pending[prompt]
        elif not pending[prompt]:
            score = sum(known[prompt].values())
            if (score, -order[prompt]) > (best, -order[leader]):
                best, leader = score, prompt
            del pending[prompt]
    return leader


def checked_file(path, expected):
    raw = (ROOT / path).read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError(f'Published input differs from its hash: {path}')
    return json.loads(raw)


def prepare():
    inputs, source_hashes = {}, {}
    for name, (snapshot, report, snapshot_hash, report_hash) in COHORTS.items():
        corpus = checked_file(f'benchmarks/data/{snapshot}-v1.json', snapshot_hash)
        reference = checked_file(f'docs/{report}-results-v1.json', report_hash)
        inputs[name] = corpus['panels'], reference['panels'], reference['plan']
        source_hashes.update(reference['plan']['sourceSha256'])
    own = Path(__file__).resolve()
    source_hashes[str(own.relative_to(ROOT))] = sha256(own.read_bytes()).hexdigest()
    for path, expected in source_hashes.items():
        if sha256((ROOT / path).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Sealed source differs: {path}')
    return {'protocol': 'cpo-case-difficulty-allocation-v1', 'cohorts': COHORTS, 'oddsMultipliers': ODDS,
            'analysis': ('Keep the same row acquisition order and change only challenger priority within '
                         'posterior-wide. Use paid same-case peer observations and a discrete odds prior. '
                         'Both archived cohorts must pass the original 10% paid savings and joint case range gate.'),
            'candidate': CANDIDATE, 'sourceSha256': source_hashes}, inputs


def measure(panels, references, plan):
    controls = (*latest.CPO, *latest.CONTROLS)
    results, totals, vectors, holdouts = {}, {method: Counter() for method in (*controls, CANDIDATE)}, {}, {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held, points, outcomes = latest.measure(panel, plan)
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('Both model splits must use the same holdout cases')
        for method, point in points.items():
            previous = references[name][method]
            if any(point[key] != previous[key] for key in FIELDS if key in previous):
                raise ValueError(f'Published control changed for {name}/{method}')

        starts = original.ties.costs.retained_prompts(matrix, held, plan['schedule'])
        counts, logs = Counter(), []
        with patch.object(original.allocation, 'allocate', allocate):
            for seed, start in zip(plan['schedule']['seeds'], starts, strict=True):
                usage, trace = original.run(matrix, held, seed, plan, str(start), latest.CANDIDATE)
                counts.update(usage)
                logs.append(trace)
        finals = [int(trace[-1]['decision']['selected']) for trace in logs]
        cases = original.CONFIRMATION.uncertainty.case_totals(matrix, held, finals)
        if sum(cases.values()) != counts['holdoutPasses']:
            raise ValueError('Candidate score does not match its selected prompts')
        points[CANDIDATE] = {**counts, 'paidLookups': counts['searchPaid'] + counts['qualificationPaid'],
                             'traceSha256': digest(logs)}
        subject_vectors = vectors.setdefault(subject, {method: [0] * len(held) for method in controls})
        for method, vector in subject_vectors.items():
            for index, case in enumerate(held):
                vector[index] += cases[case] - outcomes[method][case]
        for method, point in points.items():
            totals[method].update({key: point[key] for key in FIELDS[:2]})
        results[name] = {method: {key: point[key] for key in FIELDS if key in point}
                         for method, point in points.items()}

    ranges = original.transfer.ranges(vectors, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
    budget = totals[CANDIDATE]['paidLookups']
    savings = {method: 1 - budget / totals[method]['paidLookups'] for method in original.GEPA}
    cutoff = 100 - plan['minimumLookupSavingPercent']
    meets_cost = all(100 * budget <= cutoff * totals[method]['paidLookups'] for method in original.PRIMARY)
    low, high = ranges['joint']
    gate = 'failed' if not meets_cost or high < 0 else 'passed' if low >= 0 else 'inconclusive'
    return {'panels': results, 'totals': totals, 'pairedRanges': ranges, 'lookupSavings': savings, 'gate': gate}


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
    if any(version('gepa') != parent['gepaVersion'] for _, _, parent in inputs.values()):
        parser.error('Use pinned GEPA 0.1.4')
    results = {name: measure(*data) for name, data in inputs.items()}
    with args.out.open('x') as stream:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
