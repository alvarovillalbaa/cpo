"""Test routed repair on interacting rules with one witnessed edit per proposal."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import combinations, product
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import feedback_budget, grounded, opening_screen_typed as typed
from benchmarks import opening_repair_api_replay as repair_api, opening_repair_diagnostic as diagnostic
from benchmarks.opening_probe_robustness import paired
from cpo._contract import digest
from cpo.routed_repair_cycle import run_routed_repair_cycle


ROOT = Path(__file__).resolve().parents[1]
CAP = 56
SEEDS = (62701, 62723, 62743, 62753)
TASKS = {
    'venue': (('Zone', 'Access', 'Time', 'Staff'), ('entrance', 'waitMinutes', 'escort')),
    'dispatch': (('Area', 'Load', 'Weather', 'Crew'), ('service', 'priority', 'verify')),
    'archive': (('Office', 'Retention', 'Media', 'Review'), ('location', 'days', 'approve')),
}
FAULTS = {
    'one-exception': ((1, '2/2'),),
    'overlap': ((1, '2/2'), (2, '2/2')),
    'three-exceptions': ((0, '2/2'), (1, '2/2'), (2, '2/2')),
}
PRIMARY = 'interaction-features'
ATOMIC = 'atomic-features'
DEFAULTS = ('unassigned', -1, False)


def feature_key(values):
    return '/'.join(map(str, values))


def target(values, task, seed):
    a, b, c, d = values
    # The first and third fields use different interactions. The middle
    # field applies an exceptional override on top of an ordinary formula.
    return (f'{task}-{(a + b + seed) % 3}', 5 + 3 * b + c + 17 * (b == c == 2),
            (c == 2) != (d == 2))


def panel(task, profile, seed):
    attributes, fields = TASKS[task]
    rng = Random(f'{task}/{profile}/{seed}')
    offsets = list(product(range(3), repeat=2))
    rng.shuffle(offsets)
    blocks = []
    for first, second in offsets:
        block = [(a, b, (a + b + first) % 3, (a + 2 * b + second) % 3)
                 for a, b in product(range(3), repeat=2)]
        rng.shuffle(block)
        blocks.append(block)
    splits = {'train': blocks[0] + blocks[1] + blocks[2], 'validation': blocks[3] + blocks[4][:3],
              'confirmation': blocks[5], 'holdout': blocks[6] + blocks[7]}
    result = {}
    for split, values_by_row in splits.items():
        rows = []
        for number, values in enumerate(values_by_row):
            text = '; '.join(f'{key}={value}' for key, value in zip(attributes, values, strict=True))
            text += f'; Policy={task}-{profile}-{seed}.'
            critical = any(a == b == 2 for a, b in zip(values, values[1:]))
            rows.append({'id': f'{task}-{profile}-{seed}-{split}-{number}', 'input': text,
                         'critical': critical, 'expected': dict(zip(fields, target(values, task, seed), strict=True))})
        result[split] = rows
    return result


def conjunctions(task, raw):
    inputs = typed.fixture.facts(raw)
    attributes = TASKS[task][0]
    return [feature_key((inputs[left], inputs[right])) for left, right in zip(attributes, attributes[1:])]


def learned_rules(task, rows):
    fields = TASKS[task][1]
    rules = {field: {} for field in fields}
    for row in rows:
        for field, key in zip(fields, conjunctions(task, row['input']), strict=True):
            value = row['expected'][field]
            if rules[field].setdefault(key, value) != value:
                raise ValueError('The disclosed training labels disagree')
    if any(len(values) != 9 for values in rules.values()):
        raise ValueError('The training block failed to cover each of the nine pair values')
    return rules


def opening(profile, request):
    task = request['task']
    rules = learned_rules(task, request['input']['labeledTraining'])
    fields = TASKS[task][1]
    repair = {fields[0]: dict(rules[fields[0]])}
    for field, key in FAULTS[profile]:
        value = rules[fields[field]][key]
        rules[fields[field]][key] = not value if type(value) is bool else DEFAULTS[field]
    return json.dumps({'rewrite': json.dumps(rules, sort_keys=True), 'repair': json.dumps(repair, sort_keys=True)})


def instruction(value):
    return {} if value == grounded.BASELINE else grounded.load_json(value)


def complete(task, program, raw, _training):
    spec = instruction(grounded.load_json(program)['instruction'])
    fields = TASKS[task][1]
    return json.dumps({field: spec.get(field, {}).get(key, default) for field, key, default in
                       zip(fields, conjunctions(task, raw), DEFAULTS, strict=True)}, sort_keys=True)


def repair(request):
    task, payload = request['task'], request['input']
    training = {row['id']: row for row in payload['labeledTraining']}
    fields = TASKS[task][1]
    program = instruction(payload['current'])
    votes, values, visited = Counter(), {}, set()
    for observation in feedback_budget.observation_records(payload['recentFeedback']):
        row = training[observation['id']]
        if row['id'] in visited:
            continue
        visited.add(row['id'])
        actual = grounded.load_json(observation['observed'])
        for field_index, (field, key) in enumerate(zip(fields, conjunctions(task, row['input']), strict=True)):
            expected = row['expected'][field]
            if actual[field] != expected and program.get(field, {}).get(key) != expected:
                entry = field_index, key
                votes[entry] += 1 + row['critical']
                values[entry] = expected
    if not votes:
        return json.dumps({'instruction': payload['current']})
    winner = min(votes, key=lambda entry: (-votes[entry], entry))
    field_index, key = winner
    program.setdefault(fields[field_index], {})[key] = values[winner]
    return json.dumps({'instruction': json.dumps(program, sort_keys=True)})


def feature_map(task, groups, with_pairs):
    attributes = TASKS[task][0]
    result = {}
    for split in ('train', 'validation'):
        for row in groups[split]:
            inputs = typed.fixture.facts(row['input'])
            values = {key: inputs[key] for key in attributes}
            if with_pairs:
                values.update({f'{a}/{b}': feature_key((inputs[a], inputs[b])) for a, b in combinations(attributes, 2)})
            result[row['id']] = values
    return result


def cycle(features):
    def run(*args, rounds, train_per_round, **options):
        return run_routed_repair_cycle(
            *args, input_features=lambda row: features[row.id], diagnostic_prompt=repair_api.strip_demonstrations,
            recover_stalls=True, fallback_probe_limit=12, **options)
    return run


def compare(task, profile, seed, groups):
    with (patch.object(typed, 'FAMILY_FIELD', {key: value[0][0] for key, value in TASKS.items()}),
          patch.object(typed.fixture, 'respond', lambda request: opening(profile, request)),
          patch.object(typed.programs, 'complete', complete), patch.object(typed.feedback, 'observed_repair', repair)):
        control = typed.trial(task, groups, seed, CAP)
        for arm, with_pairs in ((ATOMIC, False), (PRIMARY, True)):
            features = feature_map(task, groups, with_pairs)
            control['arms'][arm] = diagnostic.rerun_repair(task, groups, seed, CAP, cycle(features))
    return {**control, 'profile': profile}


def prepare():
    panels = {f'{task}/{profile}/{seed}': panel(task, profile, seed)
              for task in TASKS for profile in FAULTS for seed in SEEDS}
    inputs = [row['input'] for groups in panels.values() for rows in groups.values() for row in rows]
    if len(inputs) != len(set(inputs)):
        raise ValueError('Training, validation, qualification, and holdout require disjoint inputs')
    parent, _ = typed.prepare()
    files = {*parent['sourceSha256'], 'benchmarks/opening_interaction_transfer.py',
             'benchmarks/opening_repair_api_replay.py', 'benchmarks/opening_repair_diagnostic.py',
             'benchmarks/opening_probe_robustness.py', 'cpo/routed_repair_cycle.py', 'cpo/opening_repair_cycle.py',
             'cpo/expected_qualification.py'}
    design = {'protocol': 'cpo-opening-interaction-transfer-v1', 'gepaVersion': parent['gepaVersion'],
              'primary': PRIMARY, 'seeds': SEEDS, 'searchCap': CAP, 'maxEditsPerProposal': 1,
              'faultProfiles': FAULTS, 'gate': parent['gate'],
              'datasetSha256': {name: digest(groups) for name, groups in panels.items()},
              'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(files)}}
    return design, panels


def measure(panels):
    trials = []
    for name, groups in panels.items():
        task, profile, seed = name.split('/')
        trials.append(compare(task, profile, int(seed), groups))
    with (patch.object(typed, 'ARMS', (*typed.ARMS, ATOMIC, PRIMARY)),
          patch.object(typed, 'CPO', (PRIMARY, 'cpo-adaptive'))):
        result = typed.summary(trials)
        result['profiles'] = {profile: typed.summary([trial for trial in trials if trial['profile'] == profile])
                              for profile in FAULTS}
    result['vsAtomic'] = paired(trials, PRIMARY, ATOMIC)
    result['traceSha256'] = digest(trials)
    result['disagreements'] = [{
        'task': trial['task'], 'profile': trial['profile'], 'seed': trial['seed'],
        'passes': {arm: sum(trial['arms'][arm]['holdout'].values()) for arm in (ATOMIC, PRIMARY, *typed.GEPA)},
        'searchLookups': {arm: trial['arms'][arm]['searchLookups'] for arm in (ATOMIC, PRIMARY, *typed.GEPA)},
        'primaryRepairStatuses': [event['status'] for event in trial['arms'][PRIMARY]['events']
                                  if event['kind'] == 'routed-probes'],
    } for trial in trials if len({sum(trial['arms'][arm]['holdout'].values())
                                 for arm in (ATOMIC, PRIMARY, *typed.GEPA)}) > 1]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    design, panels = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        parser.error('Use GEPA 0.1.4')
    results = measure(panels)
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
