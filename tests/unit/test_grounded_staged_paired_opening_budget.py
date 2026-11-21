"""T2 tests of distinct physical samples and the tightened request bounds."""

from collections import Counter
from io import StringIO
import json

import pytest

from benchmarks import grounded_staged_paired_opening_budget as budget


def request(task, role, prompt, row, splits, repeat=None):
    sample = {'task': task, 'role': role, 'instruction': prompt, 'input': row['input'],
              'jsonSchema': budget.comparison.staged.schema(splits)}
    if repeat is not None:
        sample['repeat'] = repeat
    return sample


def journal(monkeypatch, *, counts=None):
    staged = budget.comparison.staged
    groups = staged.cohorts()
    original = {'reflection': 48, 'evaluation': 852, 'admission': 576, 'qualification': 756}
    plan = {'searchCap': 56, 'repeats': 2, 'physicalLimitsByRole': original}
    plan['physicalLimitsByRole'] = budget.development_limits(groups, plan)
    plan['logicalLimitsByRole'] = original
    if counts is not None:
        plan['confirmationPromptCountsByTask'] = counts
        plan['physicalLimitsByRole'] = {'qualification': 16 * sum(counts.values())}
    calls = Counter()

    def respond(sample):
        calls[sample['role']] += 1
        return json.dumps({'rewrite': 'rewrite', 'repair': 'repair'}) if sample['role'] == 'reflection' else '{}'

    monkeypatch.setattr(staged, 'record', lambda sink, data: sink.write(json.dumps(data) + '\n'))
    return groups, budget.Journal(StringIO(), plan, respond), calls


def test_upper_bounds_cover_disjoint_dynamic_reads_and_all_six_admission_and_scoring_prompts(monkeypatch):
    groups, wire, paid = journal(monkeypatch)
    for task, splits in groups.items():
        wire.send('shared', {'task': task, 'role': 'reflection', 'instruction': 'opening', 'input': 'training'})
        openers = (budget.BASELINE, 'rewrite', 'repair')
        for arm in budget.DYNAMIC:
            for index in range(56):
                wire.send(arm, request(task, 'evaluation', f'{arm}-{index}', splits['train'][0], splits))
        for prompt in openers:
            for row in splits['validation']:
                wire.send('opening-only', request(task, 'evaluation', prompt, row, splits))
        nominees = dict(zip((*budget.DYNAMIC, 'opening-only', budget.ARM), (*budget.DYNAMIC, 'rewrite', 'repair')))
        for arm, prompt in nominees.items():
            for row in splits['admission']:
                for repeat in range(2):
                    for candidate in (budget.BASELINE, prompt):
                        wire.send(arm, request(task, 'admission', candidate, row, splits, repeat))
        for prompt in (*openers, *budget.DYNAMIC):
            for row in splits['holdout']:
                for repeat in range(2):
                    wire.send('paired', request(task, 'qualification', prompt, row, splits, repeat))

    assert paid == {'reflection': 3, 'evaluation': 612, 'admission': 288, 'qualification': 648}
    assert wire.physical == paid
    assert wire.logical['admission'] == 480


def test_runtime_rejects_a_second_dynamic_nominee_and_a_fixed_read_on_training(monkeypatch):
    groups, wire, paid = journal(monkeypatch)
    task, splits = next(iter(groups.items()))
    wire.send('shared', {'task': task, 'role': 'reflection', 'instruction': 'opening', 'input': 'training'})
    with pytest.raises(ValueError, match='shared validation or prompt pool'):
        wire.send(budget.ARM, request(task, 'evaluation', 'rewrite', splits['train'][0], splits))
    first = request(task, 'admission', 'dynamic-one', splits['admission'][0], splits, 0)
    wire.send('cpo', first)
    with pytest.raises(ValueError, match='more than one nominee'):
        wire.send('cpo', {**first, 'instruction': 'dynamic-two'})
    assert paid == {'reflection': 1, 'admission': 1}


def test_confirmation_rejects_an_extra_prompt_and_noncanonical_schema_before_dispatch(monkeypatch):
    counts = dict.fromkeys(budget.comparison.staged.cohorts(), 2)
    groups, wire, paid = journal(monkeypatch, counts=counts)
    task, splits = next(iter(groups.items()))
    first = request(task, 'qualification', 'initial', splits['confirmation'][0], splits, 0)
    wire.send('paired', first)
    wire.send('paired', {**first, 'instruction': 'final'})
    with pytest.raises(ValueError, match='bound prompt count'):
        wire.send('paired', {**first, 'instruction': 'extra'})
    schema = {**first['jsonSchema'], 'additionalProperties': 0}
    with pytest.raises(ValueError, match='canonical sample identity'):
        wire.send('paired', {**first, 'jsonSchema': schema})
    assert paid == {'qualification': 2}
