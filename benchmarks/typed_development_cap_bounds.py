"""Check the sealed Luna v1 verdict with one unknown grade per capped reply."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from benchmarks.typed_development_futility import SOURCE_HASHES, recorded_samples, replay as historical_replay
from cpo._contract import unique_object
from cpo.development_qualification import CANDIDATE
from cpo.development_qualification_bounds import assess_development_bounds


def replay(archive):
    historical = historical_replay(archive)

    def parse(raw):
        return json.loads(raw, object_pairs_hook=unique_object)

    def load(name):
        raw = (archive / name).read_bytes()
        if sha256(raw).hexdigest() != SOURCE_HASHES[name]:
            raise ValueError(f'{name} differs from the verified qualification archive')
        return raw

    plan = parse(load('plan.json'))
    rows = parse(load('qualification.json'))
    events = list(map(parse, load('wire.jsonl').splitlines()))
    calls = list(zip(events[::2], events[1::2], strict=True))
    schedule, observed, charges = recorded_samples(rows, calls, plan)
    gate, costs = plan['developmentGate'], plan['developmentSearchCostAtReservationRatesMicrousd']
    grades = []
    capped_by_arm, capped_by_task, capped_sequences = Counter(), Counter(), []
    for sample, grade, (request, finish) in zip(schedule, observed, calls, strict=True):
        reply = finish['reply']
        if reply['status'] == 'completed':
            grades.append(grade)
            continue
        cap = parse(request['request'])['max_output_tokens']
        if (reply['status'] != 'incomplete' or (reply.get('incomplete_details') or {}).get('reason') != 'max_output_tokens'
                or reply['usage']['output_tokens'] != cap or grade):
            raise ValueError('An incomplete reply differs from the sealed max-output accounting')
        grades.append(None)
        capped_sequences.append(request['sequence'])
        capped_by_arm.update(sample.arms)
        capped_by_task[sample.task] += 1

    full = assess_development_bounds(schedule, grades, gate=gate, search_costs=costs)
    for count in range(len(schedule) + 1):
        prefix = assess_development_bounds(schedule, grades[:count], gate=gate, search_costs=costs)
        if prefix.status == 'impossible':
            first_impossible = {'physicalReplies': count, 'reasons': prefix.rejection_reasons,
                                'capsSeen': sum(grade is None for grade in grades[:count]),
                                'observedSuffixRequests': len(charges) - count,
                                'observedSuffixUsageAtPlanRatesMicrousd': sum(charges[count:])}
            break
    else:
        first_impossible = None

    by_task = {}
    for row in rows:
        arm = by_task.setdefault(row['task'], {}).setdefault(row['arm'], {'confirmedPasses': 0, 'possiblePasses': 0})
        grade = grades[row['sampleSequence'] - 1]
        arm['confirmedPasses'] += grade is True
        arm['possiblePasses'] += grade is not False
    if set(capped_by_arm) - costs.keys() or CANDIDATE in capped_by_arm or full.status != 'impossible':
        raise ValueError('The outcome differs from the recorded v1 qualification scope')
    return {'protocol': 'cpo-recorded-typed-development-cap-bounds-v1',
            'qualificationPlanSha256': historical['qualificationPlanSha256'], 'sourceSha256': SOURCE_HASHES,
            'physicalReplies': len(schedule), 'logicalReplies': len(rows), 'cappedSequences': capped_sequences,
            'cappedByTask': capped_by_task, 'cappedByArm': capped_by_arm, 'passBoundsByTaskAndArm': by_task,
            'finalGate': {'status': full.status, 'reasons': full.rejection_reasons},
            'firstImpossibleWithCapsUnknown': first_impossible,
            'historicalFirstCertainRejection': historical['firstCertainRejection'], 'newProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True, help='Original live qualification directory')
    parser.add_argument('--out', type=Path, required=True, help='Fresh report path')
    args = parser.parse_args()
    if args.out.exists() or args.out.resolve().is_relative_to(args.archive.resolve()):
        parser.error('Use a fresh report path outside the qualification archive')
    report = replay(args.archive)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
