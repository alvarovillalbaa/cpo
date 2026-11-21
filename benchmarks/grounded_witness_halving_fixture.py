"""Script a fallback win and a failed independent proof."""

import json
from random import Random

from benchmarks import grounded, grounded_witness_episode as original, grounded_witness_episode_fixture as fixture


RECOVERY_TASK = 'ticket'


def responder(tasks, profile):
    parent = fixture.responder(tasks, profile)
    if profile == 'rejected':
        return parent

    recovery = tasks[RECOVERY_TASK]
    anchors = [row['input'] for row in recovery['validation']]
    labels = {row['input']: row['expected'] for row in recovery['validation']}
    first_order = anchors.copy()
    Random(original.SEED).shuffle(first_order)
    initial_pass = next(case for case in first_order if case not in anchors[:original.GEPA_ANCHORS])
    misses = {}
    for cycle in range(original.CYCLES):
        order = anchors.copy()
        Random(original.SEED + cycle).shuffle(order)
        misses[recovery['train'][cycle * original.TRAIN_ROWS]['id']] = next(row for row in order if row != initial_pass)

    def respond(request):
        case, prompt = request['input'], request['instruction']
        if (request['task'], request['role']) != (RECOVERY_TASK, 'evaluation') or case not in labels or prompt == grounded.BASELINE:
            return parent(request)
        missed = misses[prompt.rsplit(' ', 1)[1]]
        passed = prompt.startswith('fixture broad ') and case != missed
        return json.dumps(labels[case] if passed else {}, sort_keys=True)

    return respond
