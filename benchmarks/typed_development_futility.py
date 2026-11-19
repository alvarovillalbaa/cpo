"""Find when the sealed Luna typed development gate became impossible."""

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from cpo._contract import digest, unique_object


SOURCE_HASHES = {
    'plan.json': 'f7c0ea81ff54dd15cf6b5bc65b7fa22578595185da34da84d8a90d63ada9d029',
    'qualification.json': 'bef435783b851d5e1b148d855a489563d6b6c34e305e7ca8b492da38b41dfb85',
    'summary.json': '77df819c8d5597c921592d5f079a074ff2f7695ee07a2db6b7ff1e4fb1422455',
    'wire.jsonl': 'cfdf8f2e32e579e53067bab32b8b3c79878942b5281699c3be18dfc838dcd4a0',
}
CANDIDATE, INITIAL = 'cpo', 'initial'


@dataclass(frozen=True)
class Sample:
    task: str
    case: str
    repeat: int
    critical: bool
    arms: tuple[str, ...]


def rejection_reasons(schedule, observed, gate, costs):
    """Test the best completion of the known schedule, with one bit per physical reply.

    The input is a complete schedule with one sample per arm, case and repeat.
    Observed bits are a prefix. Unobserved samples shared with CPO pass, and
    all other unobserved samples fail. This maximizes every gate margin at once.
    """
    cells = defaultdict(dict)
    for index, sample in enumerate(schedule):
        passed = observed[index] if index < len(observed) else CANDIDATE in sample.arms
        cells[sample.task, sample.case, sample.repeat, sample.critical].update(dict.fromkeys(sample.arms, passed))
    scores = Counter((task, arm) for (task, _, _, _), row in cells.items() for arm, passed in row.items() if passed)
    tasks = sorted({task for task, _, _, _ in cells})
    reasons = [{'gate': 'task-floor', 'task': task, 'maximumPasses': scores[task, CANDIDATE],
                'requiredPasses': gate['minimumPassesPerTask']}
               for task in tasks if scores[task, CANDIDATE] < gate['minimumPassesPerTask']]

    for arm in sorted({*costs, INITIAL} - {CANDIDATE}):
        failed_tasks = [task for task in tasks if scores[task, CANDIDATE] < scores[task, arm]]
        if failed_tasks:
            reasons.append({'gate': 'task-regression', 'arm': arm, 'tasks': failed_tasks})
        if any(critical and row[arm] and not row[CANDIDATE] for (_, _, _, critical), row in cells.items()):
            reasons.append({'gate': 'critical-regression', 'arm': arm})
        if arm == INITIAL:
            continue
        deltas = Counter()
        for (task, case, _, _), row in cells.items():
            deltas[task, case] += row[CANDIDATE] - row[arm]
        best_gain = sum(deltas.values())
        efficiency_possible = (costs[arm] > 0 and
                               100 * costs[CANDIDATE] <= costs[arm] * gate['maxSearchCostPercentForEfficiency'] and
                               all(delta >= 0 for delta in deltas.values()))
        if best_gain < gate['minimumAddedPasses'] and not efficiency_possible:
            reasons.append({'gate': 'quality-or-efficiency', 'arm': arm, 'maximumAddedPasses': best_gain})
    return reasons


def recorded_samples(rows, calls, plan):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['sampleSequence']].append(row)
    if set(grouped) != set(range(1, len(calls) + 1)) or len(rows) != plan['logicalArmReplies']:
        raise ValueError('Recorded logical replies do not cover the physical schedule')
    schedule, observed, charges = [], [], []
    cells = defaultdict(set)
    responses = set()
    limits = plan['responseLimits']
    for sequence, (request, finish) in enumerate(calls, 1):
        reply = finish['reply']
        first, *shared = grouped[sequence]
        fields = ('task', 'case', 'repeat', 'critical', 'classification', 'responseId')
        if (request['sequence'] != sequence or finish['sequence'] != sequence or request['role'] != 'qualification' or
                first['responseId'] != reply['id'] or reply['id'] in responses or request['arm'] != first['arm'] or
                any(any(row[key] != first[key] for key in fields) for row in shared)):
            raise ValueError('Reply, wire sequence and shared arm observations disagree')
        sample = Sample(first['task'], first['case'], first['repeat'], first['critical'],
                        tuple(row['arm'] for row in grouped[sequence]))
        key = (sample.task, sample.case, sample.repeat, sample.critical)
        if len(set(sample.arms)) != len(sample.arms) or cells[key].intersection(sample.arms):
            raise ValueError('A case and repeat contains a second sample for the same arm')
        cells[key].update(sample.arms)
        schedule.append(sample)
        observed.append(first['classification'] == 'pass')
        responses.add(reply['id'])
        usage = reply['usage']
        charges.append(usage['input_tokens'] * limits['inputMicrousdPerToken'] +
                       usage['output_tokens'] * limits['outputMicrousdPerToken'])
    arms = {*plan['developmentSearchCostAtReservationRatesMicrousd'], INITIAL}
    cases = {(task, case, critical) for task, case, _, critical in cells}
    expected = {(task, case, repeat, critical) for task, case, critical in cases
                for repeat in range(plan['qualificationReplicates'])}
    if set(cells) != expected or len({case for _, case, _ in cases}) != len(cases) or any(
            actual != arms for actual in cells.values()):
        raise ValueError('Qualification needs a complete, uniquely labeled arm-by-repeat matrix')
    return schedule, observed, charges


def replay(archive):
    files = {name: (archive / name).read_bytes() for name in SOURCE_HASHES}
    for name, raw in files.items():
        if sha256(raw).hexdigest() != SOURCE_HASHES[name]:
            raise ValueError(f'{name} differs from the archived qualification fingerprint')

    def parse(raw):
        return json.loads(raw, object_pairs_hook=unique_object)

    plan, summary, rows = (parse(files[name]) for name in ('plan.json', 'summary.json', 'qualification.json'))
    seal = plan.pop('planSha256')
    if seal != digest(plan) or seal != summary['planSha256'] or plan['delivery'] != 'live':
        raise ValueError('Qualification source seal or delivery differs')
    events = [parse(line) for line in files['wire.jsonl'].splitlines()]
    calls = list(zip(events[::2], events[1::2], strict=True))
    schedule, observed, charges = recorded_samples(rows, calls, plan)
    gate, costs = plan['developmentGate'], plan['developmentSearchCostAtReservationRatesMicrousd']
    full = rejection_reasons(schedule, observed, gate, costs)
    if not full or summary['qualified'] or len(charges) != summary['providerRequests'] or (
            sum(charges) != summary['usageAtPlanRatesMicrousd']):
        raise ValueError('Qualification decision, requests, or measured usage differ from the source summary')
    for cutoff in range(len(schedule) + 1):
        reasons = rejection_reasons(schedule, observed[:cutoff], gate, costs)
        if reasons:
            break
    return {'protocol': 'cpo-recorded-typed-development-futility-v1', 'qualificationPlanSha256': seal,
            'sourceSha256': SOURCE_HASHES, 'gate': gate, 'historicalDecision': 'reject',
            'firstCertainRejection': {'physicalReplies': cutoff, 'reasons': reasons},
            'historicalQualificationRequests': len(schedule), 'historicalLogicalReplies': len(rows),
            'replayOmittedRequests': len(schedule) - cutoff, 'historicalUsageAtPlanRatesMicrousd': sum(charges),
            'replayOmittedUsageAtPlanRatesMicrousd': sum(charges[cutoff:])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True, help='Original live qualification directory')
    parser.add_argument('--out', type=Path, required=True, help='Fresh report path')
    args = parser.parse_args()
    report = replay(args.archive)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
