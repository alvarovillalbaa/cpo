"""Verify and deduplicate original provider holdout comparisons from a sealed replay."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from benchmarks import recorded_promotion_coverage as replay
from cpo._contract import digest


CONTROLS = ('gepa-sequential.two-critical', 'gepa-batched.two-critical')
NODE_VERIFIER = """
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
const grader = await import(pathToFileURL(process.argv[1]));
const data = JSON.parse(readFileSync(0, 'utf8'));
for (const [code, prompt] of data.prompts) {
  if (createHash('sha256').update(JSON.stringify(prompt)).digest('hex') !== code) {
    throw new Error('Archived prompt fingerprint differs');
  }
}
for (const [event, row] of data.scores) {
  const measured = grader.gradeStructuredFields(event.output, row);
  for (const key of ['passed', 'cause', 'matchedFields']) {
    if (measured[key] !== event[key]) throw new Error('Archived outcome differs from the original scorer');
  }
}
"""


def read_json(path):
    return json.loads(path.read_bytes())


def independent_rows(datasets):
    inputs = {split: {row['input'].removeprefix(f"Record {row['id']}. ").strip() for row in rows}
              for split, rows in datasets.items()}
    if inputs['holdout'] & (inputs['train'] | inputs['validation']):
        raise ValueError('Holdout input duplicates a development input')
    ids = [row['id'] for rows in datasets.values() for row in rows]
    if len(ids) != len(set(ids)) or len(inputs['holdout']) != len(datasets['holdout']):
        raise ValueError('Task partitions contain duplicate identities or holdout inputs')
    return {row['id']: row for row in datasets['holdout']}


def audit_task(source, grader, task, replayed):
    frozen = read_json(source.ARCHIVE / f'{task}-strict-plan.json')
    expected = independent_rows(frozen['datasets'])
    responses, by_prompt, prompts, grades = {}, defaultdict(dict), {}, []
    response_counts = Counter()
    for origin in source.ORIGINS:
        run = source.ARCHIVE / f'{task}-{origin}'
        plan = read_json(source.ARCHIVE / f'{task}-{origin}-plan.json')
        if plan['datasets'] != frozen['datasets'] or plan['model'] != frozen['model']:
            raise ValueError('Recorded provider arms disagree on their inputs')
        result = read_json(run / 'results.json')
        for item in (result['holdoutBaseline'], result['holdoutCandidate'],
                     *(arm for round_ in result['rounds'] for arm in round_['arms'])):
            prompts[item['promptSha256']] = item['prompt']
        events = [json.loads(line) for line in (run / 'events.jsonl').read_text().splitlines()]
        usage = {event['responseId']: (index, event) for index, event in enumerate(events)
                 if event['type'] == 'provider-usage'}
        if len(usage) != sum(event['type'] == 'provider-usage' for event in events):
            raise ValueError('A provider response was counted twice in one origin')
        last_search = max((index for index, event in enumerate(events) if event['type'] == 'reflection' or
                           (event['type'] == 'evaluation' and event['split'] != 'holdout')), default=-1)
        expected_outputs = {(item['promptSha256'], row['id']): row
                            for item in (result['holdoutBaseline'], result['holdoutCandidate'])
                            for row in item['evaluations']}
        measured_outputs = set()
        for index, event in enumerate(events):
            if event['type'] != 'evaluation' or event['split'] != 'holdout':
                continue
            row = expected[event['id']]
            prompt, response = event['promptSha256'], event['requestId']
            key = prompt, row['id']
            receipt_index, receipt = usage[response]
            same_model = receipt['model'] == plan['model'] or receipt['model'].startswith(plan['model'] + '-')
            if not last_search < receipt_index < index or not same_model or event['critical'] != row['critical']:
                raise ValueError('Holdout observation has inconsistent provider evidence or ordering')
            if key not in expected_outputs or any(event[k] != value for k, value in expected_outputs[key].items()):
                raise ValueError('Holdout result and journal disagree')
            measured_outputs.add(key)
            value = event['passed'], event['matchedFields']
            if key[1] in by_prompt[prompt] and by_prompt[prompt][key[1]] != value:
                raise ValueError('Repeated provider grades disagree on a prompt and case')
            by_prompt[prompt][key[1]] = value
            grades.append((event, row))
            previous = responses.setdefault(response, key)
            if previous != key:
                raise ValueError('One provider response backs multiple prompt or case identities')
            response_counts[key] += 1
        if measured_outputs != expected_outputs.keys():
            raise ValueError('One or more reported holdout outcomes lack a provider-backed observation')
    subprocess.run(['node', '--input-type=module', '-e', NODE_VERIFIER, str(grader)],
                   input=json.dumps({'prompts': list(prompts.items()), 'scores': grades}),
                   text=True, check=True, env={'PATH': os.environ.get('PATH', '')})

    pairs, directions, uses = Counter(), Counter(), Counter()
    for trial in replayed['trials']:
        left = trial['arms'][replay.PRIMARY]
        for baseline in CONTROLS:
            right = trial['arms'][baseline]
            candidate, control = left['chosen'], right['chosen']
            if candidate != control:
                pairs[tuple(sorted((candidate, control)))] += 1
            direction = candidate, control
            uses[direction] += 1
            directions[direction] += sum(right['outcomes'][case] and not left['outcomes'][case]
                                         for case in trial['critical'])
    finalists = sorted({code for pair in pairs for code in pair})
    missing = {prompt: sorted(expected.keys() - by_prompt.get(prompt, {}).keys()) for prompt in finalists
               if by_prompt.get(prompt, {}).keys() != expected.keys()}
    exposed = []
    for (candidate, control), losses in sorted(directions.items()):
        if candidate == control:
            continue
        matched = not any(prompt in missing for prompt in (candidate, control))
        if matched:
            a, b = by_prompt[candidate], by_prompt[control]
            heldout = {'cpoPasses': sum(value[0] for value in a.values()), 'controlPasses': sum(value[0] for value in b.values()),
                       'criticalLosses': sum(row['critical'] and b[case][0] and not a[case][0] for case, row in expected.items())}
        else:
            heldout = None
        exposed.append({'cpo': candidate, 'control': control, 'replayComparisons': uses[candidate, control],
                        'replayCriticalLosses': losses, 'external': heldout})
    return {'recordedProviderResponses': len(responses), 'distinctPromptCaseSlots': len(response_counts),
            'uniqueNonidenticalPairs': len(pairs), 'matchedUniquePairs': sum(not any(prompt in missing for prompt in pair) for pair in pairs),
            'missingPromptCases': missing, 'missingPromptTextsVerified': all(prompt in prompts for prompt in missing),
            'distinctDirections': exposed}


def prepare(input_path):
    from field_validation_replay import ARCHIVE, ORIGINS
    import field_validation_replay as source

    root = Path(__file__).resolve().parents[1]
    prior = read_json(root / 'docs/recorded-promotion-coverage-results-v1.json')
    frozen_replay, _, _, _ = replay.prepare()
    content = input_path.read_bytes()
    artifact = json.loads(content)
    if (sha256(content).hexdigest() != prior['detailsSha256'] or artifact['planSha256'] != digest(frozen_replay)
            or artifact['plan'] != frozen_replay or set(artifact['results']) != set(source.TASKS)):
        raise ValueError('Replay does not reproduce the published promotion experiment')
    grade = ARCHIVE.parents[4] / 'apps/cli/src/scenario/improvement-plan.mjs'
    plan = {'protocol': 'cpo-recorded-independent-holdout-v1', 'priorReplaySha256': prior['detailsSha256'],
            'priorPlanSha256': prior['planSha256'], 'sourceProvider': 'gpt-6.2-sol', 'controls': list(CONTROLS),
            'origins': list(ORIGINS), 'codeSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'sourceGraderSha256': sha256(grade.read_bytes()).hexdigest()}
    return plan, source, grade, artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, source, grade, replayed = prepare(args.replay)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    tasks = {task: audit_task(source, grade, task, experiment) for task, experiment in sorted(replayed['results'].items())}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'tasks': tasks}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
