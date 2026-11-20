"""Measure the contribution of staged repairs over the same shared opening."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks import grounded, grounded_staged as staged, grounded_staged_fixture
from benchmarks.grounded_staged_case_evidence import case_resampling_range
from benchmarks.grounded_staged_combined_fixture import mixed_fixture
from cpo import Observation, ProposalPair
from cpo._contract import digest
from cpo.family_qualification import certify_family_qualification
from cpo.opening_screen_cycle import run_opening_screen_cycle


PROFILES = {'all-rewrites-faulted': grounded_staged_fixture.respond, 'perfect-ticket-rewrite': mixed_fixture}
BASELINE = grounded.BASELINE
CERTIFICATES = {'certify_final_draft': True, 'certify_opening': True}
REFERENCE = staged.ROOT / 'docs/grounded-staged-combined-results-v1.json'


def plan():
    groups, combined, _ = staged.prepare(**CERTIFICATES)
    design = {'protocol': 'portable-grounded-staged-opening-ablation-v1',
              'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'combinedPlanSha256': digest(combined), 'referenceSha256': sha256(REFERENCE.read_bytes()).hexdigest(),
              'profiles': list(PROFILES), 'control': 'certified opening screen, no subsequent proposals',
              'controlAdmission': 'same family certificate as staged repair', 'searchCost': 'opening plus evaluation and admission uses',
              'holdoutAnalysis': 'matched replies with task-stratified case resampling',
              'sourceSha256': {name: sha256((staged.ROOT / name).read_bytes()).hexdigest() for name in (
                  'benchmarks/grounded_staged_case_evidence.py', 'benchmarks/grounded_staged_combined_fixture.py')}}
    return groups, combined, design


def opening_only(task, groups, respond, *, certify_validation=False):
    train, validation, admission = (groups[name] for name in ('train', 'validation', 'admission'))
    evaluation = {row['id']: row for row in (*train, *validation)}
    admission_rows = {row['id']: row for row in admission}
    training = [{key: row[key] for key in ('id', 'input', 'expected')} for row in train]
    counts = Counter()

    def request(role, instruction, inputs, *, repeat=None):
        counts[role] += 1
        attempt = {'task': task, 'role': role, 'instruction': instruction, 'input': inputs}
        if role != 'reflection':
            attempt['jsonSchema'] = staged.schema(groups)
        if repeat is not None:
            attempt['repeat'] = repeat
        return respond(attempt)

    def evaluate(prompt, row):
        target = evaluation[row.id]
        text = request('evaluation', prompt, target['input'])
        passed, fields = grounded.score(text, target['expected'])
        return Observation(passed, {'id': row.id, 'observed': text}, fields)

    def qualify(prompt, row, repeat):
        target = admission_rows[row.id]
        return grounded.score(request('admission', prompt, target['input'], repeat=repeat), target['expected'])[0]

    opening = request('reflection', grounded.OPENING,
                      {'task': task, 'current': BASELINE, 'labeledTraining': training, 'recentFeedback': []})
    pair = grounded.proposals(opening, BASELINE, ('rewrite', 'repair'))
    if not pair:
        raise ValueError('The shared opening must contain two distinct valid instructions')
    repeats = grounded.REPEATS
    screened = run_opening_screen_cycle(
        BASELINE, staged.cases(task, train), staged.cases(task, validation), staged.cases(task, admission),
        evaluate, opening_pair=ProposalPair(*pair), metric_limit=grounded.METRIC_LIMIT,
        qualify=qualify, qualification_limit=0, repeats=repeats, seed=staged.SEED,
        field_credit=True, certify_opening=True, certify_validation=certify_validation)
    nominee = screened.search.prompt
    proof = certify_family_qualification(BASELINE, nominee, staged.cases(task, admission), qualify,
                                         repeats=repeats, seed=staged.SEED)
    return proof.prompt, counts, proof.status


def compare(result, groups, selected, control_cost, respond, split, gate):
    by_task, control_rows = {}, {}
    critical_losses = 0
    for task, rows in result['holdout'].items():
        def dispatch(_arm, role, instruction, inputs, *, repeat):
            return respond({'task': task, 'role': role, 'instruction': instruction, 'input': inputs,
                            'repeat': repeat, 'jsonSchema': staged.schema(groups[task])})

        matches = grounded.qualify_task(task, groups[task][split], {'opening': selected[task]}, dispatch)
        deltas, control_rows[task] = Counter(), []
        for row in rows:
            critical, passes = matches.pop((row['id'], row['repeat']))
            if critical != row['critical']:
                raise ValueError('The two policies must use identical critical cases')
            control = passes['opening']
            delta = row['passes']['cpo'] - control
            if selected[task] == result['selected'][task]['cpo'] and delta:
                raise ValueError('Identical selected prompts must have identical fixture outcomes')
            deltas[row['id']] += delta
            critical_losses += critical and delta < 0
            control_rows[task].append({**row, 'passes': {**row['passes'], 'cpo': control}})
        if matches:
            raise ValueError('The two policies must have identical paired cases and repeats')
        by_task[task] = list(deltas.values())
    costs = {**result['searchCallsByArm'], 'cpo': control_cost}
    return {'combinedPassesByTask': result['outcome']['passesByTask']['cpo'],
            'addedPassesByTask': {task: sum(deltas) for task, deltas in by_task.items()},
            'caseResampling95PassDifference': case_resampling_range(by_task.values()),
            'matchedCriticalLosses': critical_losses, 'combinedQualified': result['outcome']['qualified'],
            'openingOnlyOutcome': staged.grade(control_rows, costs, gate)}


def measure(seal):
    groups, frozen, design = plan()
    if seal != digest(design):
        raise ValueError('Use the current opening ablation seal')
    reference = grounded.load_json(REFERENCE.read_bytes())
    profiles = {}
    with TemporaryDirectory(prefix='cpo-opening-ablation-') as scratch:
        for label, respond in PROFILES.items():
            work = Path(scratch) / label
            work.mkdir()
            development, confirmation = work / 'development', work / 'confirmation'
            selected, search_costs, admission = {}, {}, {}
            for task, splits in groups.items():
                allowed = {name: splits[name] for name in ('train', 'validation', 'admission')}
                selected[task], search_costs[task], admission[task] = opening_only(task, allowed, respond)
            control_cost = sum(sum(counts.values()) for counts in search_costs.values())

            dev = staged.run(digest(frozen), development, respond, delivery='fixture', **CERTIFICATES)
            _, bound, _ = staged.prepare(development, **CERTIFICATES)
            panel = staged.run(digest(bound), confirmation, respond, delivery='fixture', development=development,
                               **CERTIFICATES)
            outcomes = {}
            for phase, archive, result, split, gate in (
                ('development', development, dev, 'holdout', frozen['gate']),
                ('confirmation', confirmation, panel, 'confirmation', bound['gate']),
            ):
                hashes = {name: sha256((archive / name).read_bytes()).hexdigest() for name in staged.ARCHIVE_FILES}
                if hashes != reference['profiles'][label]['combined'][phase]['archiveSha256']:
                    raise ValueError('The staged comparison differs from its published fixture archive')
                outcomes[phase] = compare(result, groups, selected, control_cost, respond, split, gate)
            profiles[label] = {'openingOnlySearchUsesByTaskAndRole': search_costs, 'openingOnlySearchUses': control_cost,
                               'combinedSearchUses': dev['searchCallsByArm']['cpo'], 'openingOnlyAdmission': admission,
                               'sameSelectionByTask': {task: prompt == dev['selected'][task]['cpo']
                                                       for task, prompt in selected.items()}, **outcomes}
    return {'plan': design, 'planSha256': seal, 'profiles': profiles}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if bool(args.execute) != bool(args.out) or (args.out and args.out.exists()):
        parser.error('Execution requires a fresh --out report path')
    if args.execute:
        try:
            result = measure(args.execute)
        except ValueError as error:
            parser.error(str(error))
        staged.save(args.out, result)
    else:
        _, _, design = plan()
        print(json.dumps({**design, 'planSha256': digest(design)}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
