"""Audit typed case overlap and build a disjoint policy stress fixture."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from random import Random

from benchmarks import grounded_fixture, grounded_staged, typed_policy
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_DATA_SHA256 = 'a8bc9978274d57cbe0a57638b78bb7c0a8ae0fce075c2567410f653295cf7182'
SEARCH_SPLITS = ('train', 'validation', 'admission', 'holdout')
STRESS_SEED = 931541

OUTAGE_BOUNDARIES = (
    (28, 'PLUS', 33, 'POSTED', 0, 'NORMAL'),
    (30, 'STANDARD', 40, 'POSTED', 4, 'NORMAL'),
    (30, 'PLUS', 100, 'POSTED', 10, 'NORMAL'),
    (119, 'STANDARD', 230, 'POSTED', 23, 'NORMAL'),
    (119, 'PLUS', 70, 'POSTED', 7, 'NORMAL'),
    (29, 'STANDARD', 47, 'MISSING', 0, 'NEEDS_DOC'),
    (120, 'PLUS', 170, 'POSTED', 17, 'LONG'),
    (120, 'STANDARD', 240, 'MISSING', 24, 'NEEDS_DOC'),
)


def regime(task, text):
    fields = grounded_fixture.facts(text)
    if task == 'ticket':
        return (fields['Topic'],)
    if task == 'warehouse':
        remaining = int(fields['On hand']) - int(fields['Reserved']) - int(fields['Damaged'])
        stock = 'positive' if remaining > 0 else 'depleted' if remaining < 0 else 'zero'
        return stock, fields['Inspection'], fields['Tier'], fields['Site']
    if task == 'outage':
        minutes, plan = int(fields['Duration minutes']), fields['Plan']
        raw = minutes // (3 if plan == 'PLUS' else 5) if minutes >= 30 else 0
        cap = int(fields['Monthly fee whole USD']) // 10
        binding = 'binding' if cap < raw else 'equal' if cap == raw else 'slack'
        return minutes, plan, fields['Evidence'], binding
    raise ValueError(f'Unknown typed policy task {task}')


def topic_channel(text):
    fields = grounded_fixture.facts(text)
    return fields['Topic'], fields['Channel']


def overlap(splits, enrollment, key):
    prior = {name: {key(row['input']) for row in rows} for name, rows in splits.items()}
    enrolled = [key(row['input']) for row in enrollment]
    known = set.union(*prior.values())
    return {'rows': len(enrolled), 'distinctRegimes': len(set(enrolled)),
            'rowsSeenBySplit': {name: sum(item in keys for item in enrolled) for name, keys in prior.items()},
            'rowsWithPreviouslySeenRegime': sum(item in known for item in enrolled)}


def build_stress(groups):
    """Keep the existing scores, task sizes and critical counts with different inputs."""
    rng = Random(STRESS_SEED)
    tickets = (*typed_policy.QUEUES.items(), ('warranty-period', 'GENERAL'), ('address-change', 'GENERAL'))
    critical_topics = {'refund-question', 'return-label', 'warranty-period'}
    channels = ('phone', 'portal')
    data = {'ticket': [(f'Topic={topic}. Channel={channels[i % 2]}. Reference=CPO-{500 + i}.', {'queue': queue},
                        topic in critical_topics)
                       for i, (topic, queue) in enumerate(tickets)]}

    seen = {regime('warehouse', row['input']) for rows in groups['warehouse'].values() for row in rows}
    novel = tuple(item for item in typed_policy.WAREHOUSE if item not in seen)
    if len(novel) != 6:
        raise ValueError('Expected six unobserved warehouse regime combinations')
    extras = (('zero', 'FAIL', 'RUSH', 'NORTH'), ('positive', 'PASS', 'NORMAL', 'SOUTH'))
    data['warehouse'] = [typed_policy.warehouse(index, rng, item) for index, item in enumerate((*novel, *extras), 500)]
    data['outage'] = [
        (f'Duration minutes={minutes}; Plan={plan}; Monthly fee whole USD={fee}; Evidence={evidence}.',
         {'credit': credit, 'review': reason != 'NORMAL', 'reason': reason}, reason != 'NORMAL')
        for minutes, plan, fee, evidence, credit, reason in OUTAGE_BOUNDARIES
    ]
    return {task: [{'id': f'policy-stress-{task}-{i:02d}', 'input': text, 'expected': expected, 'critical': critical}
                   for i, (text, expected, critical) in enumerate(rows, 1)] for task, rows in data.items()}


def audit(groups, stress):
    original, revised = {}, {}
    for task, splits in groups.items():
        def key(text):
            return regime(task, text)

        before = {name: splits[name] for name in SEARCH_SPLITS}
        legacy, alternative = splits['confirmation'], stress[task]
        all_rows = [row for rows in splits.values() for row in rows] + alternative
        if (len({row['id'] for row in all_rows}) != len(all_rows)
                or len({row['input'] for row in all_rows}) != len(all_rows)
                or Counter(row['critical'] for row in legacy) != Counter(row['critical'] for row in alternative)):
            raise ValueError('The fixture lost distinct identities or changed the critical case counts')
        for row in all_rows:
            _, full = grounded_fixture.answers(task, grounded_fixture.facts(row['input']), typed_policy.QUEUES)
            if digest(full) != digest(row['expected']):
                raise ValueError('A case disagrees with the unchanged policy scorer')

        original[task] = overlap(before, legacy, key)
        revised[task] = overlap(splits, alternative, key)
        if task == 'ticket':
            original[task]['topicAndChannel'] = overlap(before, legacy, topic_channel)
            revised[task]['topicAndChannel'] = overlap(splits, alternative, topic_channel)
    return original, revised


def report():
    groups = grounded_staged.cohorts()
    if digest(groups) != ORIGINAL_DATA_SHA256:
        raise ValueError('The quoted Luna cohort fingerprint changed')
    stress = build_stress(groups)
    original, revised = audit(groups, stress)
    if any(value['rowsWithPreviouslySeenRegime'] != 8 for value in original.values()):
        raise ValueError('The original confirmation overlap did not reproduce')
    if (revised['ticket']['rowsWithPreviouslySeenRegime'] != 6
            or revised['ticket']['topicAndChannel']['rowsWithPreviouslySeenRegime']
            or any(revised[task]['rowsWithPreviouslySeenRegime'] for task in ('warehouse', 'outage'))):
        raise ValueError('A stress fixture case repeated a required holdout regime')
    files = ('benchmarks/grounded_policy_regimes.py', 'benchmarks/grounded_staged.py',
             'benchmarks/grounded_fixture.py', 'benchmarks/typed_policy.py')
    plan = {'protocol': 'cpo-typed-policy-stress-v1', 'originalDatasetSha256': ORIGINAL_DATA_SHA256,
            'stressPanelSha256': digest(stress), 'stressSeed': STRESS_SEED,
            'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in files}}
    return {'plan': plan, 'planSha256': digest(plan), 'original': original, 'stress': revised,
            'criticalCasesByTask': {task: sum(row['critical'] for row in rows) for task, rows in stress.items()},
            'newProviderRequests': 0}


if __name__ == '__main__':
    print(json.dumps(report(), sort_keys=True, indent=2))
