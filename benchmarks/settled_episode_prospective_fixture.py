"""Drive the shared-roster comparison without a provider connection."""

import json

from benchmarks import grounded


def responder(tasks):
    rows = {task: {row['input']: (split, index, row['expected'])
                   for split, panel in groups.items() for index, row in enumerate(panel)}
            for task, groups in tasks.items()}
    opening_score = dict(ticket=0, warehouse=1, outage=2)

    def respond(request):
        task, role, prompt, inputs = (request[name] for name in ('task', 'role', 'instruction', 'input'))
        if role == 'reflection':
            tag = inputs['labeledTraining'][0]['id']
            return json.dumps({'rewrite': f'fixture rewrite {tag}', 'repair': f'fixture repair {tag}'}, sort_keys=True)
        split, index, expected = rows[task][inputs]
        if prompt == grounded.BASELINE:
            passed = split == 'train' and index < opening_score[task]
        elif prompt.startswith(('fixture rewrite ', 'fixture repair ')):
            passed = split != 'admission' or index >= 4
        else:
            raise ValueError('The fixture received an unknown instruction')
        return json.dumps(expected if passed else {}, sort_keys=True)

    return respond
