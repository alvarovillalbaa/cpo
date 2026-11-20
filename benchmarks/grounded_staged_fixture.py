"""Exercise staged repair with a witnessed error in each shared rewrite."""

import json

from benchmarks import grounded, grounded_fixture as fixture


FAULTS = {
    'ticket': ('Topic', 'refund-question', 'queue'),
    'warehouse': ('Tier', 'RUSH', 'windowHours'),
    'outage': ('Evidence', 'MISSING', 'reason'),
}


def respond(request):
    task, instruction = request['task'], request['instruction']
    answer = json.loads(fixture.respond(request))
    if request['role'] == 'reflection' and instruction == grounded.OPENING:
        rewrite = json.loads(answer['rewrite'])
        rewrite['fields'] = list(fixture.FIELDS[task])
        rewrite['fixtureFault'] = True
        answer['rewrite'] = json.dumps(rewrite, sort_keys=True)
    elif request['role'] != 'reflection' and instruction != grounded.BASELINE:
        program = json.loads(instruction)
        fields = fixture.facts(request['input'])
        key, value, field = FAULTS[task]
        if program.get('fixtureFault') and fields[key] == value:
            legacy, _ = fixture.answers(task, fields, program['queues'])
            answer[field] = legacy[field]
    return json.dumps(answer, sort_keys=True)
