"""Script qualification and rejection for the portable witness episode."""

import json
from random import Random

from benchmarks import grounded, grounded_witness_episode as study


def responder(tasks, profile):
    labels = {task: {row['input']: row['expected'] for panel in splits.values() for row in panel}
              for task, splits in tasks.items()}
    scenarios = {}
    for task, splits in tasks.items():
        anchors = [row['input'] for row in splits['validation']]
        narrow = set(anchors[:study.GEPA_ANCHORS])
        order = anchors.copy()
        Random(study.SEED).shuffle(order)
        initial_pass = next(row for row in order if row not in narrow)
        initial_miss = next(row for row in order if row != initial_pass)
        broad_miss = next(row for row in anchors[:study.GEPA_ANCHORS] if row != initial_miss)
        narrow_passes = narrow | {row['input'] for split in ('train', 'admission') for row in splits[split]}
        scenarios[task] = initial_pass, broad_miss, narrow_passes

    def respond(request):
        task, prompt, inputs = (request[name] for name in ('task', 'instruction', 'input'))
        if request['role'] == 'reflection':
            first = inputs['labeledTraining'][0]['id']
            return json.dumps({'rewrite': f'fixture narrow {first}', 'repair': f'fixture broad {first}'}, sort_keys=True)
        if profile == 'rejected' and request['role'] == 'admission':
            return '{}'
        initial_pass, broad_miss, narrow_passes = scenarios[task]
        if prompt == grounded.BASELINE:
            passed = inputs == initial_pass
        elif prompt.startswith('fixture narrow '):
            passed = inputs in narrow_passes
        elif prompt.startswith('fixture broad '):
            passed = inputs != broad_miss
        else:
            raise ValueError('The fixture received an unknown prompt')
        return json.dumps(labels[task][inputs] if passed else {}, sort_keys=True)

    return respond
