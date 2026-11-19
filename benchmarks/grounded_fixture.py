"""Deterministic rule-template responder for the portable grounded study."""

import json

from benchmarks.grounded import BASELINE, OPENING, load_json


FIELDS = {
    'ticket': ('queue',),
    'warehouse': ('available', 'action', 'owner', 'windowHours'),
    'outage': ('credit', 'review', 'reason'),
}


def facts(text):
    return dict(part.split('=', 1) for part in text.rstrip('.').replace('. ', '; ').split('; '))


def answers(task, fields, queues):
    if task == 'ticket':
        return {'queue': 'GENERAL'}, {'queue': queues.get(fields['Topic'], 'GENERAL')}
    if task == 'warehouse':
        on_hand = int(fields['On hand'])
        available = max(0, on_hand - int(fields['Reserved']) - int(fields['Damaged']))
        rush = fields['Tier'] == 'RUSH'
        action = 'HOLD' if not available or fields['Inspection'] == 'FAIL' else ('REVIEW' if rush else 'RELEASE')
        return (
            {'available': on_hand, 'action': 'LEGACY', 'owner': 'CENTRAL', 'windowHours': 24},
            {'available': available, 'action': action, 'owner': f"CREW-{fields['Site'][0]}",
             'windowHours': 4 if rush else 8},
        )
    duration = int(fields['Duration minutes'])
    rate = duration // (5 if fields['Plan'] == 'STANDARD' else 3) if duration >= 30 else 0
    missing = fields['Evidence'] == 'MISSING'
    long = duration >= 120
    return (
        {'credit': 0, 'review': False, 'reason': 'DEFAULT'},
        {'credit': min(rate, int(fields['Monthly fee whole USD']) // 10), 'review': missing or long,
         'reason': 'NEEDS_DOC' if missing else ('LONG' if long else 'NORMAL')},
    )


def encode(fields, queues):
    return json.dumps({'fields': list(fields), 'queues': queues}, sort_keys=True)


def resolve(task, instruction, row):
    template = {'fields': [], 'queues': {}} if instruction == BASELINE else load_json(instruction)
    legacy, full = answers(task, facts(row), template['queues'])
    return {**legacy, **{name: full[name] for name in template['fields']}}


def respond(request):
    task, instruction, inputs = (request[key] for key in ('task', 'instruction', 'input'))
    if request['role'] != 'reflection':
        return json.dumps(resolve(task, instruction, inputs), sort_keys=True)

    training = inputs['labeledTraining']
    queues = {facts(row['input'])['Topic']: row['expected']['queue'] for row in training} if task == 'ticket' else {}
    supported = tuple(name for name in FIELDS[task] if all(
        answers(task, facts(row['input']), queues)[1][name] == row['expected'][name] for row in training
    ))
    if instruction == OPENING:
        if task == 'ticket':
            rewrite = encode(supported, queues)
            repair = encode(supported, dict(list(queues.items())[:2]))
        else:
            rewrite = encode(supported[:-1], {})
            repair = encode(supported[:1], {})
        return json.dumps({'rewrite': rewrite, 'repair': repair}, sort_keys=True)

    parent = inputs['current']
    selected = set() if parent == BASELINE else set(load_json(parent)['fields'])
    missing = next((name for name in supported if name not in selected), None)
    if missing:
        selected.add(missing)
    added = [name for name in supported if name in selected]
    return json.dumps({'instruction': encode(added, queues)}, sort_keys=True)
