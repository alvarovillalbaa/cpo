"""Find the smallest training panels that preserve declared policy distinctions."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path

from benchmarks import grounded, witness_halving_physical_limits as bound, witness_regime_coverage as coverage
from cpo._contract import digest


EPISODE = coverage.episode
REFERENCE = 'docs/grounded-witness-regime-coverage-results-v1.json'
REFERENCE_SHA256 = '291529c7469da819e3f886b1e6a2730cd8a46fcee83941bc9772d780de0cc55f'


def ticket_faults(row):
    topic, = coverage.regime('ticket', row)
    expected = row['expected']
    alternative = 'GENERAL' if expected['queue'] != 'GENERAL' else coverage.policy.QUEUES['refund-question']
    return {f'wrong-queue/{branch}': ({**expected, 'queue': alternative} if branch == topic else expected)
            for (branch,) in coverage.REGIMES['ticket']}


def warehouse_faults(row):
    fields = coverage.grounded_fixture.facts(row['input'])
    stock, inspection, tier, _ = coverage.regime('warehouse', row)
    expected = row['expected']
    available = int(fields['On hand']) - int(fields['Reserved']) - int(fields['Damaged'])
    action = expected['action']
    possible_states = product(('nonpositive', 'positive'), ('PASS', 'FAIL'), ('NORMAL', 'RUSH'))
    current = ('positive' if stock == 'positive' else 'nonpositive', inspection, tier)
    regression = coverage.mutation('warehouse', expected)['action']
    faults = {f'wrong-action/{"/".join(state)}': ({**expected, 'action': regression} if state == current else expected)
              for state in possible_states}
    return {**faults,
            'include-reserved-stock': {**expected, 'available': max(0, available + int(fields['Reserved']))},
            'include-damaged-stock': {**expected, 'available': max(0, available + int(fields['Damaged']))},
            'allow-negative-available': {**expected, 'available': available},
            'ignore-inspection': {**expected, 'action': ('REVIEW' if tier == 'RUSH' else 'RELEASE') if available > 0 else 'HOLD'},
            'auto-release-rush': {**expected, 'action': 'RELEASE' if action == 'REVIEW' else action},
            'fixed-north-owner': {**expected, 'owner': 'CREW-N'},
            'fixed-south-owner': {**expected, 'owner': 'CREW-S'},
            'fixed-four-hour-window': {**expected, 'windowHours': 4},
            'fixed-eight-hour-window': {**expected, 'windowHours': 8}}


def outage_faults(row):
    duration, plan, _, evidence = coverage.regime('outage', row)
    fields = coverage.grounded_fixture.facts(row['input'])
    expected = row['expected']
    fee_cap = int(fields['Monthly fee whole USD']) // 10
    divisor = 3 if plan == 'PLUS' else 5
    credit = expected['credit']
    reason = expected['reason']
    return {'pay-below-thirty': {**expected, 'credit': min(duration // divisor, fee_cap)},
            'exclude-thirty': {**expected, 'credit': 0 if duration == 30 else credit},
            'ignore-fee-cap': {**expected, 'credit': duration // divisor if duration >= 30 else credit},
            'standard-rate-for-all': {**expected, 'credit': min(duration // 5, fee_cap) if duration >= 30 else credit},
            'plus-rate-for-all': {**expected, 'credit': min(duration // 3, fee_cap) if duration >= 30 else credit},
            'exclude-one-twenty': {**expected, 'reason': 'NORMAL' if duration == 120 and evidence == 'POSTED' else reason,
                                  'review': False if duration == 120 and evidence == 'POSTED' else expected['review']},
            'ignore-missing-docs': {**expected, 'reason': 'LONG' if duration >= 120 else 'NORMAL', 'review': duration >= 120},
            'ignore-long-outage': {**expected, 'reason': 'NEEDS_DOC' if evidence == 'MISSING' else 'NORMAL',
                                   'review': evidence == 'MISSING'},
            'clear-review': {**expected, 'review': False},
            'always-review': {**expected, 'review': True}}


FAULTS = {'ticket': ticket_faults, 'warehouse': warehouse_faults, 'outage': outage_faults}


def distinguishing_faults(task, row):
    expected = row['expected']
    return {name for name, actual in FAULTS[task](row).items()
            if not grounded.score(json.dumps(actual, sort_keys=True), expected)[0]}


def signals(task, row):
    labels = {f'label/{field}/{json.dumps(value)}' for field, value in row['expected'].items()
              if type(value) in (str, bool)}
    return labels | {f'fault/{name}' for name in distinguishing_faults(task, row)}


def minimum_cover(rows, features):
    """Return the earliest smallest subset that covers everything observed in one block."""
    features_by_row = [set(features(row)) for row in rows]
    names = sorted(set().union(*features_by_row))
    bits = {name: 1 << index for index, name in enumerate(names)}
    masks = [sum(bits[name] for name in values) for values in features_by_row]
    target = (1 << len(names)) - 1
    for length in range(len(rows) + 1):
        for indices in combinations(range(len(rows)), length):
            covered = 0
            for idx in indices:
                covered |= masks[idx]
            if covered == target:
                return [rows[idx] for idx in indices]
    raise ValueError('The complete training block must cover its own features')


def payload_size(task, rows):
    inputs = {'task': task, 'current': grounded.BASELINE, 'labeledTraining': rows, 'recentFeedback': []}
    return len(json.dumps(inputs, sort_keys=True, separators=(',', ':')).encode())


def compare(task, regions):
    selected = []
    for cycle in range(EPISODE.CYCLES):
        start = cycle * EPISODE.TRAIN_ROWS
        rows = regions['train'][start:start + EPISODE.TRAIN_ROWS]
        selected.append((rows, minimum_cover(rows, lambda row: signals(task, row))))
    score_errors = {}
    for split in ('holdout', 'confirmation'):
        score_errors[split] = Counter(fault for row in regions[split] for fault in distinguishing_faults(task, row))
    results = []
    for rows, cover in selected:
        by_policy = {}
        for name, panel in (('full', rows), ('prefix', rows[:len(cover)]), ('minimumCover', cover)):
            covered = set().union(*(signals(task, row) for row in panel))
            by_policy[name] = {'cases': [row['id'] for row in panel], 'requestInputBytes': payload_size(task, panel),
                               'coveredSignals': sorted(covered), 'unresolvedScoringFaults': {
                                   split: {fault: cells for fault, cells in sorted(counts.items()) if f'fault/{fault}' not in covered}
                                   for split, counts in score_errors.items()}}
        if by_policy['full']['coveredSignals'] != by_policy['minimumCover']['coveredSignals']:
            raise ValueError('Compression discarded a training distinction')
        results.append(by_policy)
    return results


def prepare():
    groups, inherited, _ = coverage.bound.futility.prepare()
    raw = (EPISODE.ROOT / REFERENCE).read_bytes()
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or digest(inherited) != bound.PORTABLE:
        raise ValueError('Use the published regime audit and the unchanged witness plan')
    files = (Path(__file__), Path(coverage.__file__))
    plan = {'protocol': 'witness-training-discrimination-v1', 'parentPlanSha256': bound.PORTABLE,
            'parentCoverageReceiptSha256': REFERENCE_SHA256,
            'sourceSha256': {file.resolve().relative_to(EPISODE.ROOT).as_posix(): sha256(file.read_bytes()).hexdigest()
                             for file in files},
            'rule': 'Preserve every seen string or boolean output label and every declared policy fault '
                    'distinguished by the 16 training examples. Minimize the number of examples, then retain '
                    'the earliest subset in the original order.',
            'controls': 'Compare the full block and an equally sized chronological prefix. Price only the '
                        'serialized reflection-input bytes. Determine holdout and confirmation mismatches '
                        'after selecting solely from training.',
            'scope': 'Deterministic typed fixtures. Keep every split, proposal budget and scoring gate in the sealed parent.'}
    return groups, plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    groups, plan = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    result = {'plan': plan, 'planSha256': seal, 'newProviderRequests': 0,
              'tasks': {task: compare(task, regions) for task, regions in groups.items()}}
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
