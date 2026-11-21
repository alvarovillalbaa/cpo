"""Replay alternate request orders under the same grounded witness acceptance gate."""

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks import grounded, grounded_witness_halving_futility as original
from cpo._contract import digest


PARENT_SEAL = 'aae517e6c51cf57645d0f788beb8d86fcc90f59a6a91ac6f85e2c3ba64ecaea0'
REFERENCE = 'docs/grounded-witness-halving-futility-rehearsal-v1.json'
REFERENCE_SHA256 = '65e90e9031d3b8d5b9727cc5bdf9ea4e96caa5208b96587364de7fee899b6aad'
SEALED, CRITICAL, GATE = 'sealed-order', 'contested-critical-first', 'gate-relevant-first'
METHODS = (SEALED, CRITICAL, GATE)
CONTROLS = {'initial', *original.parent.CONTROLS}
CANDIDATE = original.parent.CANDIDATE


def prepare():
    groups, parent, _ = original.prepare()
    raw = (original.ROOT / REFERENCE).read_bytes()
    if digest(parent) != PARENT_SEAL or sha256(raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError('Use the published grounded witness gate and fixture receipts')
    plan = {'protocol': 'grounded-witness-scoring-order-v1', 'parentPlanSha256': PARENT_SEAL,
            'parentFixtureReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': METHODS, 'scope': 'Reorder the same scoring samples after search and proof are finished. '
            'Keep every prompt, case, repeat, shared response, fixed cost and acceptance rule.',
            'fixtures': 'Reproduce the published complete and all-faulted panels. On each panel also fault the '
            'candidate on one task, and force one matched critical loss at each contested critical repeat.',
            'invariant': 'Every order must agree with the fully observed gate. A qualifying run scores every sample.'}
    return groups, parent, plan, json.loads(raw)['runs']


def blocks(samples):
    cells = defaultdict(list)
    for sample in samples:
        cells[sample.request['task'], sample.case['id'], sample.request['repeat']].append(sample)
    return cells


def order(samples, method):
    if method == SEALED:
        return samples

    def contested_critical(group):
        return group[0].case['critical'] and any(CANDIDATE not in sample.arms and CONTROLS.intersection(sample.arms)
                                                for sample in group)

    grouped = sorted(blocks(samples).values(), key=lambda group: not contested_critical(group))
    if method == CRITICAL:
        return [sample for group in grouped for sample in group]
    decisive, descriptive = [], []
    for group in grouped:
        for sample in sorted(group, key=lambda sample: CANDIDATE not in sample.arms):
            relevant = CANDIDATE in sample.arms or CONTROLS.intersection(sample.arms)
            (decisive if relevant else descriptive).append(sample)
    return decisive + descriptive


def complete_verdict(samples, grades, plan, costs):
    outcomes = defaultdict(list)
    for (task, case, repeat), group in blocks(samples).items():
        passes = {arm: grades[digest(sample.request)] for sample in group for arm in sample.arms}
        outcomes[task].append({'id': case, 'repeat': repeat, 'critical': group[0].case['critical'], 'passes': passes})
    return original.parent.finish(plan, outcomes, costs)


def scenarios(samples, initial):
    yield 'published-qualifying', {}, True
    yield 'published-all-fail', dict.fromkeys(initial, False), False
    for task in dict.fromkeys(sample.request['task'] for sample in samples):
        affected = {digest(sample.request): False for sample in samples
                    if sample.request['task'] == task and CANDIDATE in sample.arms}
        yield f'candidate-task-failure/{task}', affected, False
    for (task, case, repeat), group in blocks(samples).items():
        if not group[0].case['critical']:
            continue
        candidate = next(sample for sample in group if CANDIDATE in sample.arms)
        rival = next((sample for sample in group if CANDIDATE not in sample.arms
                      and CONTROLS.intersection(sample.arms)), None)
        if rival is not None:
            yield (f'critical-loss/{task}/{case}/{repeat}',
                   {digest(candidate.request): False, digest(rival.request): True}, False)


def compare(samples, plan, costs, reference, fixture):
    initial = {digest(sample.request): grounded.score(fixture(sample.request), sample.case['expected'])[0]
               for sample in samples}
    orders = {name: order(samples, name) for name in METHODS}
    if len(initial) != len(samples) or any({digest(sample.request): sample for sample in ordered} !=
                                         {digest(sample.request): sample for sample in samples}
                                         or len(ordered) != len(samples) for ordered in orders.values()):
        raise ValueError('A scoring order changed the sealed request identities or sharing')
    results = {}
    for profile, faults, expected in scenarios(samples, initial):
        grades = {**initial, **faults}
        complete = complete_verdict(samples, grades, plan, costs)
        if all(verdict['qualified'] for verdict in complete.values()) != expected:
            raise ValueError(f'The scripted scenario did not exercise the intended gate: {profile}')
        results[profile] = {}
        for name, ordered in orders.items():
            scoring, outcome = original.score_until_rejected(ordered, plan, costs,
                                                            lambda sample: grades[digest(sample.request)])
            if (scoring['status'] == 'qualified') != expected or (expected and not scoring['completePanel']):
                raise ValueError('A reordered path changed the acceptance decision or scored only part of a pass')
            if scoring['completePanel'] and outcome['verdicts'] != complete:
                raise ValueError('A reordered full result changed the fixed gate evidence')
            if name == SEALED and profile in reference and scoring != reference[profile]['scoring']:
                raise ValueError('The published fixture scoring trace changed')
            results[profile][name] = {key: scoring[key] for key in ('status', 'scoredRequests')}
    rejections = [row for row in results.values() if row[SEALED]['status'] != 'qualified']
    summary = {}
    for name in (CRITICAL, GATE):
        savings = [row[SEALED]['scoredRequests'] - row[name]['scoredRequests'] for row in rejections]
        summary[name] = {'earlier': sum(change > 0 for change in savings), 'later': sum(change < 0 for change in savings),
                         'same': sum(change == 0 for change in savings), 'totalRequestsSaved': sum(savings),
                         'minimumSaved': min(savings), 'maximumSaved': max(savings)}
    return {'sampleCount': len(samples), 'requestOrderSha256': {name: digest([sample.request for sample in ordered])
                                                              for name, ordered in orders.items()},
            'scenarios': results, 'rejectionSummary': summary}


def run(groups, parent, plan, reference):
    fixture = original.fixture_responder(groups, 'qualifying')
    with TemporaryDirectory(prefix='cpo-scoring-order-') as temporary:
        development = Path(temporary) / 'development'
        measured = original.run(PARENT_SEAL, development, fixture, delivery='fixture')
        hashes = {key: sha256(raw).hexdigest()
                  for key, raw in original.parent.original.archive_bytes(development).items()}
        if hashes != reference['qualifying']['archiveSha256']:
            raise ValueError('The qualifying development journal must reproduce the published archive')
        _, confirmation, prior = original.prepare(development)

    def study(split, contract, result, keys):
        rows = original.scoring_schedule(groups, result['selected'], split)
        calibrated = {name: reference[key] for name, key in zip(('published-qualifying', 'published-all-fail'),
                                                               keys, strict=True)}
        return compare(rows, contract, result['searchCosts'], calibrated, fixture)

    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0,
            'development': study('holdout', parent, measured, ('qualifying', 'faulted-scoring')),
            'confirmation': study('confirmation', confirmation, prior,
                                  ('confirmation-qualifying', 'confirmation-faulted-scoring'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    groups, parent, plan, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    result = run(groups, parent, plan, reference)
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
