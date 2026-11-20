"""Compare staged and opening-only CPO against split-safe GEPA controls."""

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks import gepa_cached_opening, gepa_disjoint_cases, grounded, grounded_staged as staged
from benchmarks import grounded_staged_case_evidence as evidence
from benchmarks import grounded_staged_opening_ablation as opening
from cpo._contract import digest


POLICIES = ('cpo', 'opening-only')
CONTROLS = (*staged.ARMS[1:], staged.CACHED_OPENING)
ARMS = (POLICIES[0], *CONTROLS, POLICIES[1])
CERTIFICATES = {'certify_opening': True, 'certify_final_draft': True}
PANEL_GATE = {'minimumTaskPasses': 12, 'minimumAddedPasses': 4, 'efficiencyPercent': 90}
ARCHIVE_FILES = staged.ARCHIVE_FILES
CACHED_OPENING_MINIBATCH = 2
CACHED_OPENING_READS = 2 * staged.SPLITS['validation']


def archive_bytes(directory):
    return {name: (directory / name).read_bytes() for name in ARCHIVE_FILES}


def prepare(development=None, *, certify_validation=False, certify_dominance=False):
    groups, base, _ = staged.prepare(**CERTIFICATES)
    tasks, repeats = len(groups), base['repeats']
    limits = dict(base['logicalLimitsByRole'])
    additional_arms = len(ARMS) - len(staged.ARMS)
    limits['evaluation'] += tasks * (base['searchCap'] + CACHED_OPENING_READS)
    limits['admission'] += additional_arms * tasks * 2 * staged.SPLITS['admission'] * repeats
    limits['qualification'] += additional_arms * tasks * staged.SPLITS['holdout'] * repeats
    modules = (Path(__file__), Path(opening.__file__), Path(evidence.__file__),
               Path(gepa_cached_opening.__file__), Path(gepa_disjoint_cases.__file__),
               Path(__file__).with_name('grounded_staged_combined_fixture.py'))
    frozen = {**base, 'protocol': 'portable-grounded-staged-policy-comparison-v2', 'arms': list(ARMS),
              'scope': 'Both CPO policies, two split-safe native GEPA controls and fixed-opening GEPA.',
              'sourceSha256': {**base['sourceSha256'], **{
                  f'benchmarks/{path.name}': sha256(path.read_bytes()).hexdigest() for path in modules}},
              'combinedPlanSha256': digest(base), 'logicalLimitsByRole': limits,
              'developmentRequestCeiling': sum(limits.values()),
              'openingControl': {'placement': 'after staged and GEPA arms for each task', 'sharedOpening': True,
                                 'laterProposals': 0, 'admission': 'same exact family certificate'},
              'nativeGepaCaseIds': 'original case IDs, disjoint across train and validation',
              'cachedGepaOpening': {'proposal': 'supplied rewrite', 'minibatch': CACHED_OPENING_MINIBATCH,
                                    'observations': 'reuse validation replies', 'laterProposals': 0,
                                    'evaluationLimitPerTask': CACHED_OPENING_READS}}
    if certify_validation:
        frozen['protocol'] = 'portable-grounded-staged-policy-comparison-v3'
        frozen['openingControl']['validation'] = 'exact promotion gate from bounded paired validation'
        names = ('cpo/opening_validation.py', 'benchmarks/grounded_staged_certified_opening_comparison.py')
        frozen['sourceSha256'].update({name: sha256((staged.ROOT / name).read_bytes()).hexdigest() for name in names})
    if certify_dominance:
        if not certify_validation:
            raise ValueError('The dominance comparison requires certified full validation')
        frozen['protocol'] = 'portable-grounded-staged-policy-comparison-v4'
        frozen['openingControl']['nomination'] = 'strict opening dominance with a funded exact fallback'
        names = ('cpo/opening_dominance.py', 'benchmarks/grounded_staged_opening_dominance_comparison.py')
        frozen['sourceSha256'].update({name: sha256((staged.ROOT / name).read_bytes()).hexdigest() for name in names})
    if development is None:
        return groups, frozen, None

    source = archive_bytes(development)
    with TemporaryDirectory(prefix='cpo-policy-comparison-bind-') as scratch:
        prior = replay(development, Path(scratch) / 'verified', certify_validation=certify_validation,
                       certify_dominance=certify_dominance)
    if archive_bytes(development) != source:
        raise ValueError('The development archive changed during confirmation binding')
    passing = prior['outcome']['qualifyingPolicies']
    if not passing:
        raise ValueError('At least one CPO policy must qualify in development')
    count = tasks * (1 + len(ARMS)) * staged.SPLITS['confirmation'] * repeats
    bound = {**frozen, 'protocol': frozen['protocol'] + '-confirmation', 'gate': PANEL_GATE,
             'developmentPlanSha256': prior['planSha256'], 'developmentDelivery': prior['delivery'],
             'developmentArchiveSha256': {key: sha256(raw).hexdigest() for key, raw in source.items()},
             'developmentQualifyingPolicies': passing, 'promptsSha256': digest(prior['selected']),
             'logicalLimitsByRole': {'qualification': count}, 'confirmationRequestCeiling': count}
    del bound['developmentRequestCeiling']
    return groups, bound, prior


def grade(heldout, costs, gate):
    by_policy = {}
    for policy in POLICIES:
        rows = {task: [{**row, 'passes': {**row['passes'], 'cpo': row['passes'][policy]}} for row in panel]
                for task, panel in heldout.items()}
        verdict = staged.grade(rows, {**costs, 'cpo': costs[policy]}, gate, controls=CONTROLS)
        verdict['passesByTask'][policy] = verdict['passesByTask'].pop('cpo')
        by_policy[policy] = verdict

    paired = {}
    staged_losses, opening_losses = 0, 0
    for task, rows in heldout.items():
        cases = Counter()
        for row in rows:
            delta = row['passes']['cpo'] - row['passes']['opening-only']
            cases[row['id']] += delta
            staged_losses += row['critical'] and delta < 0
            opening_losses += row['critical'] and delta > 0
        paired[task] = list(cases.values())
    return {'byPolicy': by_policy, 'qualifyingPolicies': [policy for policy in POLICIES if by_policy[policy]['qualified']],
            'stagedVersusOpeningOnly': {'addedPassesByTask': {task: sum(values) for task, values in paired.items()},
                'caseResampling95PassDifference': evidence.case_resampling_range(paired.values()),
                'stagedMatchedCriticalLosses': staged_losses, 'openingOnlyMatchedCriticalLosses': opening_losses,
                'addedSearchUses': costs['cpo'] - costs['opening-only']}}


class Journal:
    def __init__(self, wire, frozen, respond):
        self.wire = wire
        self.respond = respond
        self.logical_limits = frozen['logicalLimitsByRole']
        self.request_limits = {'evaluation': frozen['searchCap'],
                               'admission': 2 * staged.SPLITS['admission'] * frozen['repeats']}
        self.logical, self.physical, self.by_arm = Counter(), Counter(), Counter()
        self.shared_opening = {}
        self.samples = {}
        self.search_uses = defaultdict(list)
        self.sequence = 0

    def send(self, arm, request):
        task, role = request['task'], request['role']
        key = json.dumps(request, sort_keys=True, separators=(',', ':'))
        if arm == 'opening-only' and role == 'reflection':
            if key not in self.shared_opening:
                raise ValueError('Opening-only must reuse the exact shared opening')
            return self.shared_opening[key]

        self.logical[role] += 1
        self.by_arm[task, arm, role] += 1
        limit = self.request_limits.get(role)
        if role == 'reflection':
            limit = {'shared': 1, 'cpo': 3, staged.CACHED_OPENING: 0}.get(arm, grounded.REFLECTION_LIMIT)
        if role == 'evaluation' and arm == staged.CACHED_OPENING:
            limit = CACHED_OPENING_READS
        if (self.logical[role] > self.logical_limits.get(role, 0) or
                (limit is not None and self.by_arm[task, arm, role] > limit)):
            raise grounded.ResponderFailed from ValueError('A request exceeded a sealed task or role limit')

        if role != 'reflection' and key in self.samples:
            sequence, text = self.samples[key]
        else:
            self.sequence += 1
            sequence = self.sequence
            self.physical[role] += 1
            staged.record(self.wire, {'sequence': sequence, 'arm': arm, 'request': request})
            try:
                text = self.respond(deepcopy(request))
                if not isinstance(text, str):
                    raise ValueError('The responder must return text')
            except Exception as error:
                raise grounded.ResponderFailed from error
            staged.record(self.wire, {'sequence': sequence, 'response': text})
            if role != 'reflection':
                self.samples[key] = (sequence, text)
            elif arm == 'shared':
                self.shared_opening[key] = text
        if role != 'qualification':
            self.search_uses[arm].append(sequence)
        return text


def select_cached_gepa(initial, bank, groups, evaluate, *, cap, seed):
    return gepa_cached_opening.select_opening(initial, bank[:1], groups, evaluate, cap=cap, seed=seed, width=1,
                                              minibatch_size=CACHED_OPENING_MINIBATCH)


def run(seal, directory, respond, *, delivery, development=None, certify_validation=False, certify_dominance=False):
    if development is not None and directory.resolve().is_relative_to(development.resolve()):
        raise ValueError('Confirmation requires a separate archive')
    groups, frozen, prior = prepare(development, certify_validation=certify_validation,
                                   certify_dominance=certify_dominance)
    if seal != digest(frozen) or version('gepa') != frozen['gepaVersion'] or delivery not in ('fixture', 'model'):
        raise ValueError('Use the current comparison seal, pinned GEPA, and declared delivery')
    if prior is not None and prior['delivery'] != delivery:
        raise ValueError('Confirmation delivery must match development')
    directory.mkdir(mode=0o700)
    staged.save(directory / 'plan.json', {**frozen, 'planSha256': seal, 'delivery': delivery})
    prompts, decisions, outcomes = {}, {}, {}
    split = 'holdout' if prior is None else 'confirmation'
    if prior is not None:
        prompts, decisions = prior['selected'], prior['admissionDecisions']

    with (directory / 'wire.jsonl').open('x') as wire:
        journal = Journal(wire, frozen, respond)
        schemas = {task: staged.schema(task_groups) for task, task_groups in groups.items()}

        def dispatch(task, arm, role, instruction, inputs, *, repeat=None):
            request = {'task': task, 'role': role, 'instruction': instruction, 'input': inputs}
            if role != 'reflection':
                request['jsonSchema'] = schemas[task]
            if repeat is not None:
                request['repeat'] = repeat
            return journal.send(arm, request)

        try:
            if prior is None:
                for task, task_groups in groups.items():
                    search = {part: task_groups[part] for part in ('train', 'validation', 'admission')}
                    prompts[task], decisions[task] = staged.choose(
                        task, search, partial(dispatch, task), **CERTIFICATES,
                        native_gepa_selector=gepa_disjoint_cases.select, cached_opening_selector=select_cached_gepa,
                    )
                    prompt, counts, status = opening.opening_only(
                        task, search, partial(journal.send, 'opening-only'), certify_validation=certify_validation,
                        certify_dominance=certify_dominance)
                    prompts[task]['opening-only'] = prompt
                    decisions[task]['opening-only'] = {'admission': status, 'admissionLookups': counts['admission']}

            for task, task_groups in groups.items():
                paired = grounded.qualify_task(task, task_groups[split], prompts[task], partial(dispatch, task))
                outcomes[task] = [{'id': row, 'repeat': repeat, 'critical': critical, 'passes': passes}
                                  for (row, repeat), (critical, passes) in paired.items()]
        except grounded.ResponderFailed as error:
            raise error.__cause__ from None

    uses = dict(journal.search_uses) if prior is None else prior['developmentSearchSamplesByArm']
    costs = {arm: len(uses.get(arm, [])) + len(uses['shared']) for arm in ARMS}
    result = {'planSha256': seal, 'delivery': delivery, 'logicalCallsByRole': dict(journal.logical),
              'physicalCallsByRole': dict(journal.physical), 'selected': prompts, 'admissionDecisions': decisions,
              'developmentSearchSamplesByArm': uses, 'searchCallsByArm': costs, 'holdout': outcomes,
              'outcome': grade(outcomes, costs, frozen['gate'])}
    if prior is not None:
        result['qualifyingInBothStages'] = [policy for policy in result['outcome']['qualifyingPolicies']
                                             if policy in frozen['developmentQualifyingPolicies']]
    staged.save(directory / 'result.json', result)
    return result


def replay(directory, fresh, *, development=None, certify_validation=False, certify_dominance=False):
    if fresh.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Replay requires a separate archive')
    source = archive_bytes(directory)
    plan = grounded.load_json(source['plan.json'])
    pending = iter(source['wire.jsonl'].splitlines())
    sequence = 0

    def respond(request):
        nonlocal sequence
        sequence += 1
        start, finish = (grounded.load_json(next(pending, b'null')) for _ in range(2))
        if (not isinstance(start, dict) or not isinstance(finish, dict) or start.get('request') != request or
                start.get('sequence') != sequence or finish.get('sequence') != sequence):
            raise ValueError('The comparison journal ended early or changed its request')
        return finish.get('response')

    result = run(plan.get('planSha256'), fresh, respond, delivery=plan.get('delivery'), development=development,
                 certify_validation=certify_validation, certify_dominance=certify_dominance)
    if next(pending, None) is not None or archive_bytes(fresh) != source or archive_bytes(directory) != source:
        raise ValueError('The saved comparison differs from its replay')
    return result


def main(*, certify_validation=False, certify_dominance=False):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--fixture', metavar='PLAN_SHA256')
    modes.add_argument('--replay', type=Path)
    parser.add_argument('--profile', choices=opening.PROFILES, default='all-rewrites-faulted')
    parser.add_argument('--development', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if bool(args.fixture or args.replay) != bool(args.out) or (args.out and args.out.exists()):
        parser.error('Fixture and replay require a fresh --out archive')
    options = dict(certify_validation=certify_validation, certify_dominance=certify_dominance)
    if args.fixture:
        result = run(args.fixture, args.out, opening.PROFILES[args.profile], delivery='fixture',
                     development=args.development, **options)
    elif args.replay:
        result = replay(args.replay, args.out, development=args.development, **options)
    else:
        _, frozen, _ = prepare(args.development, **options)
        result = {**frozen, 'planSha256': digest(frozen)}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
