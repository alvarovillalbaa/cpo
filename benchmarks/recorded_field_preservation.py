"""Test whether preserving individual correct fields prevents archived promotion losses."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path
from random import Random
import subprocess

from benchmarks.recorded_independent_holdout import CONTROLS
from benchmarks.recorded_promotion_coverage import PRIMARY, assign_panels
from cpo._contract import digest, unique_object


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PLAN_SHA256 = '4023fb794d1488f61a6518e28214423ed904b0f68b6ca67ea524af01aa3a3f84'
ORIGINS = ('strict', 'fields', 'hybrid')
ARMS = (PRIMARY, *CONTROLS)
NODE_FIELDS = """
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
const { gradeStructuredFields } = await import(pathToFileURL(process.argv[1]));
const rows = JSON.parse(readFileSync(0, 'utf8'));
const sha256 = content => createHash('sha256').update(content).digest('hex');
const results = rows.map(([event, row]) => {
  const grade = gradeStructuredFields(event.output, row);
  for (const key of ['passed', 'cause', 'matchedFields']) {
    if (grade[key] !== event[key]) throw new Error('Validation event disagrees with the pinned grader');
  }
  if (grade.cause === 'format') return [[], sha256(JSON.stringify(['format', event.output]))];
  const answer = JSON.parse(event.output);
  const keys = Object.keys(row.expected).sort();
  const correct = keys.filter(key => answer[key] === row.expected[key]);
  return [correct, sha256(JSON.stringify(keys.map(key => [key, answer[key]])))];
});
console.log(JSON.stringify(results));
"""


def verified(path, fingerprint):
    data = path.read_bytes()
    if sha256(data).hexdigest() != fingerprint:
        raise ValueError(f'{path.name} differs from the sealed source')
    return data


def parse(data):
    return json.loads(data, object_pairs_hook=unique_object)


def validation_evidence(archive, grader, task, files):
    rows_by_id, events, receipts = None, [], {}
    for origin in ORIGINS:
        stem = f'{task}-{origin}'
        plan = parse(verified(archive / f'{stem}-plan.json', files[f'{stem}-plan.json']))
        rows = {row['id']: row for row in plan['datasets']['validation']}
        if rows_by_id is not None and rows != rows_by_id:
            raise ValueError('Validation inputs differ across source arms')
        rows_by_id = rows
        file = f'{stem}/events.jsonl'
        usage = {}
        for line in verified(archive / file, files[file]).splitlines():
            event = parse(line)
            if event['type'] == 'provider-usage':
                key = event['responseId']
                if key in usage:
                    raise ValueError('Duplicate provider receipt in one source journal')
                usage[key] = event['model']
            if event['type'] != 'evaluation' or event['split'] != 'validation':
                continue
            row = rows[event['id']]
            response = event['requestId']
            identity = event['promptSha256'], row['id'], event['output']
            if (usage.get(response) != plan['model'] or event['critical'] != row['critical'] or
                    receipts.setdefault(response, identity) != identity):
                raise ValueError('Validation reply differs from its receipt, prompt, or row')
            events.append((event, row))
    raw = subprocess.check_output(['node', '--input-type=module', '-e', NODE_FIELDS, str(grader)],
                                  input=json.dumps(events).encode(), env={'PATH': os.environ.get('PATH', '')})
    masks, outputs = {}, defaultdict(set)
    for (event, _), (fields, output) in zip(events, parse(raw), strict=True):
        cell = event['promptSha256'], event['id']
        mask = frozenset(fields)
        if len(mask) != event['matchedFields'] or masks.setdefault(cell, mask) != mask:
            raise ValueError('A prompt and case has conflicting correct fields')
        outputs[cell].add(output)
    return rows_by_id, masks, outputs, len(receipts)


def field_guard(incumbent, candidate, cases, rows, masks, paid, *, preserve_identity):
    """Audit remaining protected challenger rows after an exact promotion certificate."""
    lost, extra = [], 0
    for case in cases:
        base = masks[incumbent, case]
        if not rows[case]['critical'] or not base:
            continue
        extra += case not in paid
        challenger = masks[candidate, case]
        loses_fields = bool(base - challenger) if preserve_identity else len(base) > len(challenger)
        if loses_fields:
            lost.append(case)
            break
    return lost, extra


def analyze_task(trials, incumbent, rows, masks, outputs, external_directions):
    summary = {arm: {policy: Counter(promotionsBlocked=0, extraLookups=0, holdoutPassDelta=0)
                     for policy in ('field-count', 'field-identity')} for arm in ARMS}
    loss_observations, indistinguishable, loss_directions = [], set(), set()
    seen_pairs = set()
    for trial in trials:
        holdout = trial['holdout']
        remaining = sorted(rows.keys() - set(holdout))
        Random(trial['seed']).shuffle(remaining)
        train = remaining[:3]
        validation, promotion = assign_panels(remaining[3:6], remaining[6:], rows, 2)
        if trial['critical'] != [case for case in holdout if rows[case]['critical']]:
            raise ValueError('Replay has inconsistent holdout critical labels')
        for arm in ARMS:
            outcome = trial['arms'][arm]
            candidate = outcome['chosen']
            hits = {case: len(masks[candidate, case]) == len(rows[case]['expected']) for case in holdout}
            if hits != outcome['outcomes'] or set(outcome['qualification']) - set(promotion):
                raise ValueError('Archived replay outcomes or partition differ')
            if outcome['promotion'] != 'promote':
                continue
            if candidate != outcome['challenger'] or not outcome['qualification']:
                raise ValueError('Expected a measured promotion to the recorded challenger')
            if any(passed != (len(masks[candidate, case]) == len(rows[case]['expected']))
                   for case, passed in outcome['qualification'].items()):
                raise ValueError('Recorded promotion reply differs from the verified field mask')
            for policy, stats in summary[arm].items():
                blocked, extra = field_guard(incumbent, candidate, promotion, rows, masks, outcome['qualification'],
                                             preserve_identity=policy == 'field-identity')
                stats['extraLookups'] += extra
                if blocked:
                    stats['promotionsBlocked'] += 1
                    stats['holdoutPassDelta'] += sum(len(masks[incumbent, case]) == len(rows[case]['expected'])
                                                      for case in holdout) - sum(hits.values())
        left = trial['arms'][PRIMARY]
        for control in CONTROLS:
            right = trial['arms'][control]
            pair = left['chosen'], right['chosen']
            if pair[0] != pair[1]:
                seen_pairs.add(tuple(sorted(pair)))
            for case in trial['critical']:
                if not right['outcomes'][case] or left['outcomes'][case]:
                    continue
                loss_directions.add(pair)
                prior = {role: sum(outputs[pair[0], row] != outputs[pair[1], row] for row in cohort)
                         for role, cohort in [('train', train), ('validation', validation), ('promotion', promotion)]}
                if not any(prior.values()):
                    indistinguishable.add(pair)
                loss_observations.append({'seed': trial['seed'], 'control': control, 'case': case,
                                          'differentPreHoldoutReplies': prior})
    hidden = sum(len(masks[a, case]) == len(masks[b, case]) and masks[a, case] != masks[b, case]
                 for a, b in seen_pairs for case in rows)
    external = [external_directions[pair] for pair in sorted(loss_directions) if external_directions[pair] is not None]
    return {'policiesByArm': summary, 'distinctNonidenticalFinalistPairs': len(seen_pairs),
            'sameCountDifferentFieldsAcrossFinalists': hidden, 'criticalLossObservations': loss_observations,
            'distinctCriticalLossDirections': len(loss_directions),
            'lossDirectionsWithIdenticalPreHoldoutReplies': len(indistinguishable),
            'identicalReplyDirectionsWithExternalHoldout': sum(external_directions[pair] is not None
                                                                for pair in indistinguishable),
            'lossDirectionsWithExternalHoldout': external}


def replay(replay_path, independent_path, source_path, archive, grader):
    prior = parse((ROOT / 'docs/recorded-promotion-coverage-results-v1.json').read_bytes())
    previous = parse(verified(replay_path, prior['detailsSha256']))
    source = parse(verified(source_path, SOURCE_PLAN_SHA256))
    independent = parse((ROOT / 'docs/recorded-independent-holdout-results-v1.json').read_bytes())
    external = parse(verified(independent_path, independent['detailsSha256']))
    grader_hash = independent['plan']['sourceGraderSha256']
    verified(grader, grader_hash)
    if (previous['planSha256'] != prior['planSha256'] or digest(previous['plan']) != prior['planSha256'] or
            external['plan']['priorReplaySha256'] != prior['detailsSha256']):
        raise ValueError('Prior promotion replay and independent evidence do not reconcile')
    results = {}
    for task, task_data in sorted(previous['results'].items()):
        rows, masks, outputs, receipt_count = validation_evidence(archive, grader, task, source['taskSources'][task])
        directions = {(item['cpo'], item['control']): item['external']
                      for item in external['tasks'][task]['distinctDirections']}
        result = analyze_task(task_data['trials'], source['rootRewriteByTask'][task], rows, masks, outputs, directions)
        results[task] = {'verifiedProviderReplies': receipt_count, 'distinctPromptCaseSlots': len(masks), **result}
    return {'protocol': 'cpo-recorded-field-preservation-v1', 'priorReplaySha256': prior['detailsSha256'],
            'independentAuditSha256': independent['detailsSha256'], 'sourcePlanSha256': SOURCE_PLAN_SHA256,
            'graderSha256': grader_hash, 'tasks': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('replay', 'independent', 'source-plan', 'archive', 'grader', 'out'):
        parser.add_argument('--' + argument, type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.replay, args.independent, args.source_plan, args.archive, args.grader.resolve())
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
