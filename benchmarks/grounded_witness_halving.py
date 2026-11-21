"""Compare capped witness fallback with the original matched prospective arms."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks import grounded, grounded_staged as staged, grounded_witness_episode as original
from cpo._contract import digest
from cpo.halving import HalvingSearch
from cpo.paired_qualification import certify_paired_qualification


ROOT = original.ROOT
PARENT_SEAL = '0e20cd3cfb0f50c6959ec4e961513c5d6ec3ef8b6e51a0f3243aeb87bf462016'
CANDIDATE = 'witness-then-halving'
HALVING = {'halving-only-8': 8, 'halving-only-12': 12}
FALLBACK_LIMIT = 16
ARMS = (*original.ARMS, CANDIDATE, *HALVING)
CONTROLS = (original.CANDIDATE, *original.GEPA, *HALVING)


def prepare(development=None):
    tasks, parent, _ = original.prepare()
    if digest(parent) != PARENT_SEAL:
        raise ValueError('The published witness plan must reproduce before deriving the fallback comparison')
    names = ('benchmarks/grounded_witness_halving.py', 'benchmarks/grounded_witness_halving_fixture.py',
             'cpo/halving/__init__.py')
    limits = parent['physicalLimitsByRole'].copy()
    limits['evaluation'] += len(tasks) * (FALLBACK_LIMIT + original.CYCLES * sum(HALVING.values()))
    limits['admission'] += len(tasks) * (1 + len(HALVING)) * 2 * (original.SPLITS['admission'] // original.CYCLES) * grounded.REPEATS
    limits['qualification'] = len(tasks) * (1 + len(ARMS)) * original.SPLITS['holdout'] * grounded.REPEATS
    plan = {**parent, 'protocol': 'portable-grounded-witness-halving-development-v1', 'parentPlanSha256': PARENT_SEAL,
            'sourceSha256': {**parent['sourceSha256'], **{name: sha256((ROOT / name).read_bytes()).hexdigest()
                                                       for name in names}},
            'arms': list(ARMS), 'candidate': CANDIDATE, 'gateControls': list(CONTROLS), 'halvingLogicalCaps': HALVING,
            'fallbackLogicalCapPerCycle': 8, 'fallbackNewEvaluationLimitPerTask': FALLBACK_LIMIT,
            'fallbackRule': ('Run only when the original witness path submitted no independent proof. Use its '
                             'validation grades and the same rosters, with at most one independent proof.'),
            'maxAdmissionAttempts': {**parent['maxAdmissionAttempts'], CANDIDATE: 1, **dict.fromkeys(HALVING, 1)},
            'logicalLimitsByRole': limits, 'physicalLimitsByRole': limits, 'requestCeiling': sum(limits.values())}
    if development is None:
        return tasks, plan, None

    archive = original.archive_bytes(development)
    with TemporaryDirectory(prefix='cpo-witness-halving-bind-') as tmp:
        prior = replay(development, Path(tmp) / 'verified')
    if not prior['qualifiedOnBothMeasures'] or original.archive_bytes(development) != archive:
        raise ValueError('Confirmation requires an exact, qualifying fallback development archive')
    cap = sum(len(set(prior['selected'][task].values())) * len(groups['confirmation']) * grounded.REPEATS
              for task, groups in tasks.items())
    plan.update(protocol='portable-grounded-witness-halving-confirmation-v1', gate=original.CONFIRMATION_GATE,
                logicalLimitsByRole={'qualification': cap}, physicalLimitsByRole={'qualification': cap},
                requestCeiling=cap, developmentPlanSha256=prior['planSha256'], developmentDelivery=prior['delivery'],
                developmentArchiveSha256={name: sha256(raw).hexdigest() for name, raw in archive.items()},
                selectedSha256=digest(prior['selected']))
    return tasks, plan, prior


def run_halving(start, task, roster, groups, evaluate, qualify, *, metric_limit, logical_limit, paid=()):
    search = HalvingSearch(metric_limit=metric_limit, paid=paid)
    anchors = tuple(row['id'] for row in groups['validation'])
    width = original.SPLITS['admission'] // original.CYCLES
    log = []
    for index, (prompts, _) in enumerate(roster):
        nominee = search.select((start, *prompts), anchors, evaluate, logical_limit=logical_limit)
        state = 'capped' if nominee is None else 'no-nominee'
        if nominee in (None, start):
            log.append({'nominee': nominee, 'prompt': start, 'admission': state})
            if nominee is None:
                break
            continue
        rows = staged.cases(task, groups['admission'][index * width:(index + 1) * width])
        proof = certify_paired_qualification(start, nominee, rows, qualify, repeats=grounded.REPEATS,
                                             seed=original.SEED + index)
        log.append({'nominee': nominee, 'prompt': proof.prompt, 'admission': proof.status})
        return proof.prompt, log, search.evaluations
    return start, log, search.evaluations


def choose(task, groups, dispatch, journal):
    specs = {row['id']: row for rows in groups.values() for row in rows}
    cases = {row['input']: row for row in groups['validation']}
    roster, paid = [], {}
    use_start = len(journal.search_uses[original.CANDIDATE])

    def capture(arm, role, prompt, inputs, *, repeat=None):
        text = dispatch(arm, role, prompt, inputs, repeat=repeat)
        if role == 'reflection':
            roster.append((grounded.proposals(text, grounded.BASELINE, ('rewrite', 'repair')), journal.sequence))
        if role == 'evaluation' and arm == original.CANDIDATE:
            row = cases[inputs]
            paid[prompt, row['id']] = grounded.score(text, row['expected'])[0]
        return text

    selected, admissions = original.choose(task, groups, capture, journal)
    original_log = admissions[original.CANDIDATE]
    journal.search_uses[CANDIDATE].extend(journal.search_uses[original.CANDIDATE][use_start:])
    counts = dict.fromkeys((CANDIDATE, *HALVING), 0)

    def select(arm, limit, logical, cached=()):
        def grade(role, prompt, case, repeat=None):
            spec = specs[case]
            text = dispatch(arm, role, prompt, spec['input'], repeat=repeat)
            return grounded.score(text, spec['expected'])[0]

        return run_halving(selected['initial'], task, roster, groups, lambda prompt, case: grade('evaluation', prompt, case),
                           lambda prompt, row, repeat: grade('admission', prompt, row.id, repeat),
                           metric_limit=limit, logical_limit=logical, paid=cached)

    fallback_log = []
    selected[CANDIDATE] = selected[original.CANDIDATE]
    if all(item['admission'] == 'no-nominee' for item in original_log):
        selected[CANDIDATE], fallback_log, counts[CANDIDATE] = select(CANDIDATE, FALLBACK_LIMIT, 8, paid)
    admissions[CANDIDATE] = {'witness': original_log, 'fallback': fallback_log}
    for arm, cap in HALVING.items():
        selected[arm], admissions[arm], counts[arm] = select(arm, cap * original.CYCLES, cap)
        journal.search_uses[arm].extend(sequence for _, sequence in roster[:len(admissions[arm])])
    return selected, admissions, counts


def finish(plan, outcomes, costs):
    projected = {task: [{**row, 'passes': {**row['passes'], 'cpo': row['passes'][CANDIDATE]}} for row in rows]
                 for task, rows in outcomes.items()}
    return {name: staged.grade(projected, {**values, 'cpo': values[CANDIDATE]}, plan['gate'], controls=CONTROLS)
            for name, values in costs.items()}


def run(seal, directory, respond, *, delivery, development=None):
    tasks, plan, prior = prepare(development)
    if seal != digest(plan) or version('gepa') != plan['gepaVersion'] or delivery not in ('fixture', 'model'):
        raise ValueError('Use the sealed fallback plan, pinned GEPA, and declared delivery')
    if prior and (prior['delivery'] != delivery or directory.resolve().is_relative_to(development.resolve())):
        raise ValueError('Confirmation needs matching delivery and a separate fresh archive')
    directory.mkdir(mode=0o700)
    staged.save(directory / 'plan.json', {**plan, 'planSha256': seal, 'delivery': delivery})
    selected, admissions, counts = ({}, {}, {}) if prior is None else (
        prior['selected'], prior['admissions'], prior['additionalValidationUses'])
    scoring = 'holdout' if prior is None else 'confirmation'
    allowed = {task: {split: {row['input'] for row in rows} for split, rows in groups.items()}
               for task, groups in tasks.items()}
    schemas = {task: staged.schema(groups) for task, groups in tasks.items()}
    outcomes = {}
    with (directory / 'wire.jsonl').open('x') as wire:
        journal = original.Journal(wire, plan, respond)

        def dispatch(task, arm, role, prompt, inputs, *, repeat=None):
            request = {'task': task, 'role': role, 'instruction': prompt, 'input': inputs}
            if role != 'reflection':
                regions = {'evaluation': ('validation', 'train') if arm in original.GEPA else ('validation',),
                           'admission': ('admission',), 'qualification': (scoring,)}
                if not any(inputs in allowed[task][split] for split in regions[role]):
                    raise ValueError('The fallback request left its sealed case split')
                request['jsonSchema'] = schemas[task]
            if repeat is not None:
                request['repeat'] = repeat
            return journal.send(arm, request)

        try:
            if prior is None:
                for task, groups in tasks.items():
                    search = {split: groups[split] for split in ('train', 'validation', 'admission')}
                    selected[task], admissions[task], counts[task] = choose(
                        task, search, lambda *args, **kwargs: dispatch(task, *args, **kwargs), journal)
            for task, groups in tasks.items():
                paired = grounded.qualify_task(task, groups[scoring], selected[task],
                                              lambda *args, **kwargs: dispatch(task, *args, **kwargs))
                outcomes[task] = [{'id': row, 'repeat': repeat, 'critical': critical, 'passes': passed}
                                  for (row, repeat), (critical, passed) in paired.items()]
        except grounded.ResponderFailed as failure:
            raise failure.__cause__ from None
    if prior and dict(journal.physical) != plan['physicalLimitsByRole']:
        raise ValueError('Confirmation must complete its exact scoring schedule')
    uses = {arm: journal.search_uses[arm] for arm in ARMS}
    costs = ({'logicalSearchUses': {arm: len(samples) for arm, samples in uses.items()},
              'attributedSearchRequests': {arm: len(set(samples)) for arm, samples in uses.items()}}
             if prior is None else prior['searchCosts'])
    verdicts = finish(plan, outcomes, costs)
    result = {'planSha256': seal, 'delivery': delivery, 'selected': selected, 'admissions': admissions,
              'additionalValidationUses': counts, 'holdout': outcomes, 'searchCosts': costs,
              'logicalCallsByRole': dict(journal.logical), 'physicalCallsByRole': dict(journal.physical),
              'verdicts': verdicts, 'qualifiedOnBothMeasures': all(report['qualified'] for report in verdicts.values())}
    staged.save(directory / 'result.json', result)
    return result


def replay(directory, fresh, *, development=None):
    if fresh.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Replay requires a separate output directory')
    raw = original.archive_bytes(directory)
    manifest = grounded.load_json(raw['plan.json'])
    pending = iter(raw['wire.jsonl'].splitlines())
    sequence = 0

    def respond(request):
        nonlocal sequence
        sequence += 1
        sent, received = next(pending, None), next(pending, None)
        if sent is None or received is None:
            raise ValueError('The fallback journal contains an incomplete reply')
        sent, received = grounded.load_json(sent), grounded.load_json(received)
        if sent['sequence'] != sequence or received['sequence'] != sequence or sent['request'] != request:
            raise ValueError('The replay request differs from the sealed fallback journal')
        return received['response']

    output = run(manifest['planSha256'], fresh, respond, delivery=manifest['delivery'], development=development)
    if next(pending, None) is not None or original.archive_bytes(fresh) != raw or original.archive_bytes(directory) != raw:
        raise ValueError('The comparison archive differs from its exact replay')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--fixture')
    mode.add_argument('--replay', type=Path)
    parser.add_argument('--development', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--profile', choices=('qualifying', 'rejected'), default='qualifying')
    args = parser.parse_args()
    if bool(args.fixture or args.replay) != bool(args.out):
        parser.error('Fixture and replay require fresh output paths')
    if args.fixture:
        from benchmarks.grounded_witness_halving_fixture import responder

        result = run(args.fixture, args.out, responder(original.cohorts(), args.profile), delivery='fixture',
                     development=args.development)
    elif args.replay:
        result = replay(args.replay, args.out, development=args.development)
    else:
        _, plan, _ = prepare(args.development)
        result = {**plan, 'planSha256': digest(plan)}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
