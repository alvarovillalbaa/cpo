"""Rearrange fixed training examples to cover more contexts at the same size."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

from benchmarks import witness_training_context as parent
from cpo._contract import digest


EPISODE = parent.EPISODE
REFERENCE = 'docs/witness-training-context-results-v1.json'
REFERENCE_SHA256 = '96aaa92da278c7671d8b775f91ef6d99f9a74670dff7d608c3154ee059d90bbd'


def signals_in(block, features):
    return set().union(*(features[row['id']] for row in block))


def merit(contexts):
    per_block = tuple(sorted(map(len, contexts)))
    pair_coverage = tuple(sorted(len(left | right) for left, right in combinations(contexts, 2)))
    return sum(per_block), per_block, pair_coverage, len(contexts[0] | contexts[1]), len(contexts[0])


def optimize(blocks, context_of, features_of):
    """Apply the best improving same-criticality exchange until no such exchange remains."""
    chosen = [list(block) for block in blocks]
    contexts = {row['id']: context_of(row) for block in chosen for row in block}
    features = {row['id']: features_of(row) for block in chosen for row in block}
    if sum(map(len, chosen)) != len(contexts):
        raise ValueError('Each training case must belong to exactly one original block')
    required = [signals_in(block, features) for block in chosen]
    covered = [{contexts[row['id']] for row in block} for block in chosen]
    current = merit(covered)
    swaps = 0
    while True:
        best = current
        exchange = None
        for i, j in combinations(range(len(chosen)), 2):
            for a, first in enumerate(chosen[i]):
                for b, second in enumerate(chosen[j]):
                    if first['critical'] != second['critical']:
                        continue
                    left, right = chosen[i].copy(), chosen[j].copy()
                    left[a], right[b] = second, first
                    coverage = covered.copy()
                    coverage[i] = {contexts[row['id']] for row in left}
                    coverage[j] = {contexts[row['id']] for row in right}
                    proposed = merit(coverage)
                    if proposed <= best:
                        continue
                    if required[i] <= signals_in(left, features) and required[j] <= signals_in(right, features):
                        best, exchange = proposed, (i, j, left, right, coverage)
        if exchange is None:
            return chosen, swaps
        i, j, left, right, covered = exchange
        chosen[i], chosen[j] = left, right
        current = best
        swaps += 1


def summarize(task, blocks, outcomes):
    contexts = [{parent.context(task, row) for row in block} for block in blocks]
    pairs = [left | right for left, right in combinations(contexts, 2)]

    def missed(context_sets):
        return {split: sum(count for seen in context_sets for key, count in cases.items() if key not in seen)
                for split, cases in outcomes.items()}

    return {'blocks': [[row['id'] for row in block] for block in blocks],
            'criticalRowsPerBlock': [sum(row['critical'] for row in block) for block in blocks],
            'contextsPerBlock': [len(values) for values in contexts],
            'firstTwoContexts': len(contexts[0] | contexts[1]), 'fewestContextsAcrossAnyPair': min(map(len, pairs)),
            'requestInputBytesPerBlock': [parent.parent.payload_size(task, block) for block in blocks],
            'unresolvedByBlock': missed(contexts), 'unresolvedByPair': missed(pairs)}


def measure(task, regions, stress, reference):
    train = regions['train']
    blocks = [train[index:index + EPISODE.TRAIN_ROWS] for index in range(0, len(train), EPISODE.TRAIN_ROWS)]
    selected, swaps = optimize(blocks, lambda row: parent.context(task, row), lambda row: parent.parent.signals(task, row))
    outcomes = {name: parent.failures(task, rows)[0] for name, rows in {
        'development': regions['holdout'], 'confirmation': regions['confirmation'], 'stress': stress}.items()}
    original = summarize(task, blocks, outcomes)
    revised = summarize(task, selected, outcomes)
    for key in ('development', 'confirmation', 'stress'):
        if original['unresolvedByBlock'][key] != sum(row['full']['scoring'][key]['casesUnresolvedInFullBlock']
                                                     for row in reference):
            raise ValueError('The published full-block context exposure changed')
    if (sorted(case for block in original['blocks'] for case in block) != sorted(
            case for block in revised['blocks'] for case in block) or
            original['criticalRowsPerBlock'] != revised['criticalRowsPerBlock'] or
            sum(original['requestInputBytesPerBlock']) != sum(revised['requestInputBytesPerBlock'])):
        raise ValueError('Repartitioning must preserve the examples, critical counts, and total input bytes')
    counts = Counter(parent.context(task, row) for row in train)
    upper_bound = sum(min(count, len(blocks)) for count in counts.values())
    return {'original': original, 'repartitioned': revised, 'swaps': swaps,
            'totalContextUpperBound': upper_bound, 'attainsUpperBound': sum(revised['contextsPerBlock']) == upper_bound}


def prepare():
    groups, source, _ = parent.prepare()
    raw = (EPISODE.ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(source):
        raise ValueError('Use the published context stress benchmark')
    plan = {'protocol': 'witness-training-repartition-v1', 'parentPlanSha256': digest(source),
            'parentReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'rule': 'Exchange same-criticality examples between two blocks if each block still exposes its '
            'original labels and declared policy faults. Choose the earliest best exchange, maximizing total '
            'represented contexts, then worst-block and worst-pair coverage lexicographically, then first-two '
            'and first-block coverage. Stop when no exchange improves the objective.',
            'scope': 'Reuse every original training case once at the same four-block size. Score context faults '
            'on unchanged development and confirmation cases and the published disjoint stress panel after '
            'selection. The upper bound counts at most one occurrence of each context in any one block.'}
    return groups, plan, reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    groups, plan, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    stress = parent.stress_cases(groups)
    if any(digest(rows) != reference['stressCases'][task]['sha256'] for task, rows in stress.items()):
        raise ValueError('The disjoint context stress cases changed')
    result = {'plan': plan, 'planSha256': seal, 'newProviderRequests': 0, 'tasks': {
        task: measure(task, regions, stress[task], reference['tasks'][task]) for task, regions in groups.items()}}
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
