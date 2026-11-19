"""Measure precomputed openings and training probes with two deterministic proposers."""

from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from inspect import signature
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import alternative_controls as controls, grounded, grounded_fixture as fixture, typed_policy
from cpo import optimizer
from cpo._contract import digest


SEEDS = (43117, 43147, 43177, 43201, 43223, 43237)
ARMS = ('cpo-joint', 'gepa-joint')
CONDITIONS = ('label-templates', 'observed-errors')
BUDGETS = (40, 56)
OPTIONS = {'callback-two': (False, 2), 'precomputed-two': (True, 2),
           'callback-one': (False, 1), 'precomputed-one': (True, 1)}


def observation_records(payload):
    if isinstance(payload, dict):
        if {'id', 'observed'} <= payload.keys():
            yield payload
        else:
            for entry in payload.values():
                yield from observation_records(entry)
    elif isinstance(payload, (list, tuple)):
        for entry in payload:
            yield from observation_records(entry)


def observed_repair(request):
    inputs = request['input']
    task, parent = request['task'], inputs['current']
    training = {example['id']: example for example in inputs['labeledTraining']}
    state = {'fields': [], 'queues': {}} if parent == grounded.BASELINE else grounded.load_json(parent)
    candidate = set(state['fields'])
    errors = Counter()
    seen = set()
    for receipt in observation_records(inputs.get('recentFeedback')):
        row = receipt['id']
        if row not in training:
            raise ValueError('Feedback must originate in the training cohort')
        if row in seen:
            continue
        seen.add(row)
        observed = grounded.load_json(receipt['observed'])
        for field, expected in training[row]['expected'].items():
            errors[field] += field not in candidate and observed[field] != expected
    missing = [key for key in fixture.FIELDS[task] if errors[key]]
    if not missing:
        return json.dumps({'instruction': parent})
    candidate.add(max(missing, key=errors.get))
    queues = ({fixture.facts(example['input'])['Topic']: example['expected']['queue'] for example in training.values()}
              if task == 'ticket' else {})
    return json.dumps({'instruction': fixture.encode((key for key in fixture.FIELDS[task] if key in candidate), queues)})


def compare(task, data, seed, cap, proposer, mode):
    precomputed, samples = OPTIONS[mode]
    search = controls.search
    respond = controls.fixture.respond
    rounds = Counter()

    def dispatch(request):
        later = request['role'] == 'reflection' and request['instruction'] == grounded.UPDATE
        if later:
            rounds['laterProposals'] += 1
            observed = {item['id'] for item in observation_records(request['input'].get('recentFeedback'))}
            if observed:
                rounds['withFeedback'] += 1
            if len(observed) > samples:
                raise ValueError('Reflection exceeds the matched feedback cap')
        if later and proposer == 'observed-errors':
            return observed_repair(request)
        return respond(request)

    def candidate(initial, train, validation, evaluate, propose, **settings):
        if not precomputed:
            return search(initial, train, validation, evaluate, propose, **settings)
        bank = propose(initial, [], [], 2)
        return search(initial, train, validation, evaluate, propose, opening_pair=bank, **settings)

    with (patch.object(controls, 'ARMS', ARMS), patch.object(grounded, 'MINIBATCH', samples),
          patch.object(controls, 'search', candidate), patch.object(fixture, 'respond', dispatch)):
        trial = controls.compare(task, data, seed, cap)
    if proposer == 'observed-errors' and rounds['laterProposals'] != rounds['withFeedback']:
        raise ValueError('Every later fixture repair must receive observed training evidence')
    return {**trial, 'laterProposals': rounds['laterProposals'], 'laterProposalsWithFeedback': rounds['withFeedback']}


def summarize(trials, frozen):
    candidate, reference = ARMS
    totals = {}
    for arm in ARMS:
        totals[arm] = {'exact': sum(sum(trial['arms'][arm]['holdout'].values()) for trial in trials),
                       'searchCalls': sum(trial['arms'][arm]['evaluations'] + trial['arms'][arm]['reflections']
                                          for trial in trials)}
    paired = 0
    minimums, critical_losses = [], 0
    for trial in trials:
        proposed, control = (trial['arms'][arm]['holdout'] for arm in ARMS)
        minimums.append(sum(proposed.values()))
        paired += sum(proposed.values()) < sum(control.values())
        critical_losses += sum(control[key] and not proposed[key] for key in trial['criticalHoldoutIDs'])
    gain = totals[candidate]['exact'] - totals[reference]['exact']
    saved = totals[reference]['searchCalls'] - totals[candidate]['searchCalls']
    return {'totals': totals, 'paired': {'additionalPasses': gain, 'searchCallsSaved': saved, 'taskPanelsWithLoss': paired,
                                        'criticalLosses': critical_losses},
            'qualified': (not paired and not critical_losses and min(minimums) >= frozen['minPassesPerPanel']
                          and (gain >= frozen['minGain'] and saved >= 0 or
                               saved * 100 >= frozen['minSavingsPercent'] * totals[reference]['searchCalls']))}


def report():
    if version('gepa') != '0.1.4' or 'opening_pair' not in signature(controls.search).parameters:
        raise ValueError('Use GEPA 0.1.4 and the CPO precomputed-opening prototype')
    cohorts = {seed: typed_policy.cohorts(seed) for seed in SEEDS}
    sources = (controls, grounded, fixture, typed_policy, optimizer)
    frozen = {'protocol': 'typed-observed-feedback-budget-v1', 'delivery': 'deterministic-fixture',
              'settings': {name: {'precomputedOpening': opening, 'trainingProbes': probes}
                           for name, (opening, probes) in OPTIONS.items()},
              'sourceSha256': {Path(module.__file__).name: sha256(Path(module.__file__).read_bytes()).hexdigest()
                               for module in sources},
              'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'gepaVersion': '0.1.4',
              'datasetSha256': {str(seed): digest(groups) for seed, groups in cohorts.items()},
              'conditions': list(CONDITIONS), 'caps': list(BUDGETS), 'minPassesPerPanel': 14,
              'primaryCap': BUDGETS[-1], 'minSavingsPercent': 10, 'minGain': 8}
    results = {}
    for proposer in CONDITIONS:
        results[proposer] = {}
        for cap in BUDGETS:
            results[proposer][str(cap)] = {}
            for mode in OPTIONS:
                trials = [compare(task, data, seed, cap, proposer, mode)
                          for seed, tasks in cohorts.items() for task, data in tasks.items()]
                results[proposer][str(cap)][mode] = {'pairedJudgmentsSha256': digest(trials),
                    'laterProposals': sum(trial['laterProposals'] for trial in trials), **summarize(trials, frozen)}
    return {'plan': frozen, 'planSha256': digest(frozen), 'results': results}


if __name__ == '__main__':
    print(json.dumps(report(), indent=2, sort_keys=True))
