"""Stress the public opening repair across new typed rules and demo coverage."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import grounded, opening_repair_api_replay as api, opening_repair_diagnostic as diagnostic
from benchmarks import opening_screen_repair as staged, opening_screen_typed as typed
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
CAP = 56
PROFILES = ('complete', 'covered', 'one-missing', 'two-missing', 'wrong-rule')
TASKS = {
    'dispatch': (('Zone', 'Priority', 'Reason', 'Channel'), ('route', 'targetMins', 'verify', 'delivery')),
    'stock': (('Site', 'Tier', 'Inspection', 'Carrier'), ('owner', 'windowHours', 'blocked', 'handoff')),
    'service': (('Plan', 'Class', 'Timing', 'Evidence'), ('queue', 'credit', 'supervisor', 'documentation')),
}
PRIMARY = 'instruction-probes'
SEEDS = (57143, 57221)
SPLITS = {'train': 16, 'validation': 12, 'confirmation': 8, 'holdout': 18}


def make_panel(task, profile, seed):
    attributes, fields = TASKS[task]
    rng = Random(f'{task}:{profile}:{seed}')
    levels = [list(range(3)) for _ in fields]
    for order in levels:
        rng.shuffle(order)
    tables = (
        tuple(f'{task}-{profile}-{seed}-{name}' for name in levels[0]),
        tuple(3 + seed % 17 + 7 * step for step in levels[1]),
        tuple(step != levels[2][0] for step in range(3)),
        tuple(f'{profile}-{task}-policy-{step}' for step in levels[3]),
    )
    remaining = list(product(range(3), repeat=4))
    rng.shuffle(remaining)
    demos = sorted(Random(seed).sample(range(SPLITS['train']), typed.programs.DEMO_COUNT))
    seeded = {}
    for index, slot in enumerate(demos):
        final = index % (3 if profile == 'covered' else 2)
        constraints = {3: final}
        if profile == 'two-missing':
            constraints[2] = index // 2
        row = next(values for values in remaining if all(values[k] == v for k, v in constraints.items()))
        remaining.remove(row)
        seeded[slot] = row
    # Guarantee all field inputs can be learned from labeled training.
    extras = [values for values in remaining if len(set(values)) == 1]
    remaining = [values for values in remaining if values not in extras]
    candidates = iter(extras + remaining)
    training = [seeded[index] if index in seeded else next(candidates) for index in range(SPLITS['train'])]
    cases = iter(training + list(candidates))
    groups = {}
    for split, size in SPLITS.items():
        rows = []
        for index in range(size):
            values = next(cases)
            inputs = '; '.join(f'{key}={value}' for key, value in zip(attributes, values, strict=True))
            inputs += f'; Policy={task}-{profile}-{seed}.'
            rows.append({'id': f'{task}-{profile}-{seed}-{split}-{index}', 'input': inputs,
                         'expected': {key: tables[i][values[i]] for i, key in enumerate(fields)},
                         'critical': values[0] == 2 or values[3] == 2})
        groups[split] = rows
    return groups


def learned_rules(task, training):
    attributes, fields = TASKS[task]
    rules = {key: {} for key in fields}
    for row in training:
        inputs = typed.fixture.facts(row['input'])
        for field, key in zip(fields, attributes, strict=True):
            value = row['expected'][field]
            if rules[field].setdefault(inputs[key], value) != value:
                raise ValueError('The supplied training labels disagree')
    if any(len(rule) != 3 for rule in rules.values()):
        raise ValueError('Every field requires support for its three inputs')
    return rules


def encoded_rules(rules):
    return json.dumps(rules, sort_keys=True)


def decode_instruction(instruction):
    return {} if instruction == grounded.BASELINE else grounded.load_json(instruction)


def opening_response(profile):
    def respond(request):
        task = request['task']
        fields = TASKS[task][1]
        rules = learned_rules(task, request['input']['labeledTraining'])
        repair = {fields[0]: rules[fields[0]]}
        if profile in ('covered', 'one-missing', 'two-missing'):
            del rules[fields[-1]]
        if profile == 'two-missing':
            del rules[fields[-2]]
        if profile == 'wrong-rule':
            rules[fields[-1]]['2'] = 'legacy'
        return json.dumps({'rewrite': encoded_rules(rules), 'repair': encoded_rules(repair)})

    return respond


def complete(task, program, raw, training):
    attributes, fields = TASKS[task]
    inputs = typed.fixture.facts(raw)
    spec = grounded.load_json(program)
    rules = decode_instruction(spec['instruction'])
    defaults = ('legacy', -1, False, 'legacy')
    answer = {}
    for field, key, fallback in zip(fields, attributes, defaults, strict=True):
        if field in rules:
            answer[field] = rules[field].get(inputs[key], fallback)
            continue
        votes = {training[index]['expected'][field] for index in spec['demos']
                 if typed.fixture.facts(training[index]['input'])[key] == inputs[key]}
        answer[field] = next(iter(votes)) if len(votes) == 1 else fallback
    return json.dumps(answer, sort_keys=True)


def repair_response(request):
    task, inputs = request['task'], request['input']
    training = {row['id']: row for row in inputs['labeledTraining']}
    candidate = decode_instruction(inputs['current'])
    learned = learned_rules(task, training.values())
    mismatches, witnessed = Counter(), set()
    for observation in typed.feedback.observation_records(inputs['recentFeedback']):
        row = observation['id']
        if row not in training:
            raise ValueError('The repair requires training-only evidence')
        if row in witnessed:
            continue
        witnessed.add(row)
        actual = grounded.load_json(observation['observed'])
        for field, expected in training[row]['expected'].items():
            if actual[field] != expected and candidate.get(field) != learned[field]:
                mismatches[field] += 1
    if mismatches:
        field = max(TASKS[task][1], key=mismatches.__getitem__)
        candidate[field] = learned[field]
        return json.dumps({'instruction': encoded_rules(candidate)})
    return json.dumps({'instruction': inputs['current']})


def prepare():
    panels = {f'{task}/{profile}/{seed}': make_panel(task, profile, seed)
              for task in TASKS for profile in PROFILES for seed in SEEDS}
    inputs = [row['input'] for panel in panels.values() for rows in panel.values() for row in rows]
    if len(set(inputs)) != len(inputs):
        raise ValueError('The typed panels must have disjoint complete case inputs')
    files = ('benchmarks/opening_repair_policy_transfer.py', 'benchmarks/opening_repair_api_replay.py',
             'benchmarks/opening_repair_diagnostic.py', 'benchmarks/opening_screen_repair.py',
             'benchmarks/opening_screen_typed.py', 'benchmarks/alternative_controls.py',
             'benchmarks/grounded.py', 'benchmarks/grounded_fixture.py', 'benchmarks/feedback_budget.py',
             'cpo/opening_repair_cycle.py', 'cpo/opening_screen_cycle.py', 'cpo/expected_cost_proposal_cycle.py',
             'cpo/optimizer.py', 'cpo/paired_qualification.py', 'cpo/expected_qualification.py', 'cpo/_contract.py')
    design = {'protocol': 'cpo-opening-repair-policy-transfer-v1', 'gepaVersion': '0.1.4', 'searchCap': CAP,
              'datasetSha256': {name: digest(groups) for name, groups in panels.items()},
              'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
              'primary': PRIMARY, 'profiles': PROFILES, 'splits': SPLITS,
              'gate': ('Preserve each panel and its matched critical passes with at least 14 passes on every panel, '
                       'and gain eight passes at equal or lower cost or save ten percent of calls.')}
    return design, panels


def measure(panels):
    trials = []
    for name, groups in panels.items():
        task, profile, seed = name.split('/')
        seed = int(seed)
        with (patch.object(typed, 'FAMILY_FIELD', {key: item[0][0] for key, item in TASKS.items()}),
              patch.object(typed.fixture, 'respond', opening_response(profile)),
              patch.object(typed.programs, 'complete', complete),
              patch.object(typed.feedback, 'observed_repair', repair_response)):
            measured = typed.trial(task, groups, seed, CAP)
            measured['arms']['repair-two'] = diagnostic.rerun_repair(task, groups, seed, CAP, staged.staged_cycle(2))
            measured['arms'][PRIMARY] = diagnostic.rerun_repair(task, groups, seed, CAP, api.packaged_cycle)
        trials.append({**measured, 'profile': profile})
    with (patch.object(typed, 'ARMS', (*typed.ARMS, 'repair-two', PRIMARY)),
          patch.object(typed, 'CPO', (PRIMARY, 'cpo-adaptive'))):
        report = typed.summary(trials)
        report['profiles'] = {profile: typed.summary([t for t in trials if t['profile'] == profile])
                              for profile in PROFILES}
    report['repairStatuses'] = dict(Counter(
        next((event['status'] for event in t['arms'][PRIMARY]['events'] if event['kind'] == 'targeted-repair'),
             'no-opening-nominee') for t in trials))
    report['traceSha256'] = digest(trials)
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, panels = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        cli.error('Use GEPA 0.1.4')
    report = {'design': design, 'designSha256': seal, 'results': measure(panels)}
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
