"""Measure exact early rejection for staged paired-opening scoring."""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks import grounded_staged_paired_opening_budget as budget
from cpo._contract import digest


comparison = budget.comparison
staged, grounded = comparison.staged, comparison.grounded
PORTABLE_SEAL = '10e96e1f523233968e8f96eb7b4edf40f5d559fc282db20789b29dd650c84869'
CONTROLS = ('initial', *comparison.CONTROLS)


def scheduled_samples(groups, selected, split):
    """Use the reference scoring order and expand shared samples to every matching arm."""
    samples = []
    for task, splits in groups.items():
        prompts = selected[task]
        aliases = (comparison.PAIRED, comparison.CHARGED)
        if any(prompts[arm] != prompts[staged.CACHED_OPENING] for arm in aliases):
            raise ValueError('The paired rewrite controls must share the cached GEPA scoring prompt')
        dispatched = {arm: prompt for arm, prompt in prompts.items() if arm not in aliases}
        rows = {row['input']: row for row in splits[split]}
        schema = staged.schema(splits)

        def collect(_arm, role, instruction, inputs, *, repeat):
            row = rows[inputs]
            request = {'task': task, 'role': role, 'instruction': instruction, 'input': inputs,
                       'jsonSchema': schema, 'repeat': repeat}
            matched = tuple(arm for arm, prompt in prompts.items() if prompt == instruction)
            samples.append((request, row, matched))
            return '{}'

        grounded.qualify_task(task, splits[split], dispatched, collect)
    return samples


def optimistic_rows(samples, observed):
    tasks = {}
    for index, (request, row, arms) in enumerate(samples):
        task = tasks.setdefault(request['task'], {})
        key = row['id'], request['repeat']
        cell = task.setdefault(key, {'id': row['id'], 'repeat': request['repeat'],
                                    'critical': row['critical'], 'passes': {}})
        passed = observed[index] if index < len(observed) else budget.ARM in arms
        cell['passes'].update(dict.fromkeys((arm for arm in arms if arm in CONTROLS), passed))
        if budget.ARM in arms:
            cell['passes']['cpo'] = passed
    return {task: list(rows.values()) for task, rows in tasks.items()}


def score_until_rejected(samples, gate, search_costs, respond):
    """Score in the sealed order and return the paid prefix of an exact verdict.

    Supply search costs per required accounting measure, fixed before scoring.
    Each measure keys costs by the original arm names. Matching instructions
    share one exact grade per case and repeat according to the sample schedule.
    """
    if not samples or not search_costs:
        raise ValueError('Supply a nonempty schedule and at least one fixed search cost measure')
    prices = {name: {**{arm: costs[arm] for arm in comparison.CONTROLS}, 'cpo': costs[budget.ARM]}
              for name, costs in search_costs.items()}
    if any(type(cost) is not int or cost < 0 for costs in prices.values() for cost in costs.values()):
        raise ValueError('Search costs must be nonnegative integers')

    observed = []
    while True:
        optimistic = optimistic_rows(samples, observed)
        verdicts = {measure: staged.grade(optimistic, costs, gate, controls=comparison.CONTROLS)
                    for measure, costs in prices.items()}
        passed = all(verdict['qualified'] for verdict in verdicts.values())
        complete = len(observed) == len(samples)
        if not passed or complete:
            return {'status': 'qualified' if passed else 'rejected', 'completePanel': complete,
                    'scoredRequests': len(observed), 'scheduledRequests': len(samples),
                    'verdictsOnBestCompletion': verdicts}
        request, row, _ = samples[len(observed)]
        text = respond(deepcopy(request))
        observed.append(grounded.score(text, row['expected'])[0])


def audit_archive(groups, frozen, result, archive, split):
    wire = [json.loads(line) for line in (archive / 'wire.jsonl').read_bytes().splitlines()]
    samples = scheduled_samples(groups, result['selected'], split)
    paid = [(sent['request'], reply['response']) for sent, reply in zip(wire[::2], wire[1::2], strict=True)
            if sent['request']['role'] == 'qualification']
    if len(paid) != result['physicalCallsByRole']['qualification'] or [x[0] for x in paid] != [x[0] for x in samples]:
        raise ValueError('The reference scoring requests differ from the generated schedule')
    observed = [grounded.score(text, row['expected'])[0] for (_, text), (_, row, _) in zip(paid, samples, strict=True)]
    rows = optimistic_rows(samples, observed)
    seen = {task: [{**row, 'passes': {**{arm: row['passes'][arm] for arm in CONTROLS},
                                     'cpo': row['passes'][budget.ARM]}} for row in panel]
            for task, panel in result['holdout'].items()}
    if rows != seen:
        raise ValueError('Physical replies did not reproduce the paired scorecard')

    def respond(request):
        original, text = next(source)
        if request != original:
            raise ValueError('Early rejection changed the sealed dispatch order')
        return text

    source = iter(paid)
    outcome = score_until_rejected(samples, frozen['gate'], {'logicalSearchUses': result['searchCallsByArm']}, respond)
    if (outcome['status'] == 'qualified') != (budget.ARM in result['outcome']['qualifyingPolicies']):
        raise ValueError('Early rejection changed the sealed verdict')
    return {**outcome, 'skippedRequests': sum(1 for _ in source),
            'originalArchivesSha256': {key: sha256(raw).hexdigest()
                                       for key, raw in comparison.archive_bytes(archive).items()}}


def fixture_profiles(groups):
    answers = {row['input']: row['expected'] for splits in groups.values() for panel in splits.values() for row in panel}

    def rewrite_only(request):
        instruction = request['instruction']
        if instruction == grounded.OPENING:
            return json.dumps({'rewrite': 'fixture verified rewrite', 'repair': 'fixture rejected repair'})
        if instruction == grounded.UPDATE:
            return json.dumps({'instruction': 'fixture rejected later'})
        return json.dumps(answers[request['input']]) if instruction == 'fixture verified rewrite' else '{}'

    return {**comparison.opening.PROFILES, 'rewrite-only': rewrite_only}


def prepare():
    groups, frozen, _ = budget.prepare()
    if digest(frozen) != PORTABLE_SEAL:
        raise ValueError('Use the sealed shared-sample paired-opening sources')
    profiles = fixture_profiles(groups)
    modules = (Path(__file__), Path(comparison.opening.__file__), Path(comparison.opening.grounded_staged_fixture.__file__),
               Path(grounded.__file__))
    study = {'protocol': 'portable-grounded-staged-paired-opening-futility-v1', 'parentPlanSha256': PORTABLE_SEAL,
             'sourceSha256': {module.name: sha256(module.read_bytes()).hexdigest() for module in modules},
             'profiles': list(profiles), 'measuredAccounting': 'logical search uses',
             'rule': 'Keep the original sample order. Stop only if the best exact completion would fail.'}
    return groups, frozen, study


def measure(groups, frozen, study):
    evidence = {}
    with TemporaryDirectory(prefix='cpo-paired-opening-futility-') as disposable:
        for label, respond in fixture_profiles(groups).items():
            development = Path(disposable) / f'{label}-development'
            result = budget.run(PORTABLE_SEAL, development, respond, delivery='fixture')
            evaluated = {'development': audit_archive(groups, frozen, result, development, 'holdout')}
            if evaluated['development']['status'] == 'qualified':
                panel = Path(disposable) / f'{label}-confirmation'
                _, bound, _ = budget.prepare(development)
                result = budget.run(digest(bound), panel, respond, delivery='fixture', development=development)
                evaluated['confirmation'] = audit_archive(groups, bound, result, panel, 'confirmation')
            evidence[label] = evaluated
    return {'study': study, 'studySha256': digest(study), 'profiles': evidence, 'liveProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    options = parser.parse_args()
    groups, frozen, study = prepare()
    seal = digest(study)
    if options.execute is None and options.out is None:
        print(json.dumps({**study, 'studySha256': seal}, indent=2, sort_keys=True))
        return
    if options.execute != seal or options.out is None or options.out.exists():
        parser.error('Use the current study seal and a fresh output path')
    result = measure(groups, frozen, study)
    with options.out.open('x') as destination:
        json.dump(result, destination, indent=2, sort_keys=True)
        destination.write('\n')


if __name__ == '__main__':
    main()
