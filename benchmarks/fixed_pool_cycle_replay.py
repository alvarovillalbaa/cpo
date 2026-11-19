"""Verify the public fixed-pool cycle against the archived transfer and costs."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import bounded_transfer_matched_cost as reference
from benchmarks import prompteval_archive_cycles as archive
from benchmarks import prompteval_continuous as continuous
from benchmarks import prompteval_validation_size as smaller
from cpo import Observation, Row
from cpo._contract import digest, unique_object
from cpo.fixed_pool_cycle import run_fixed_pool_cycle


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '9ff02d2b6a9200dba0b573705de9036b53f00e9d1c4473221182623266003f4c'
METHODS = reference.CPO_METHODS
IDENTITY = ('incumbent', 'challenger', 'selected', 'archiveNominee', 'archivePromoted', 'searchSha256')


def run_episode(matrix, held, seed, original, plan, screen, expected):
    incumbent, layouts = smaller.narrow_schedule(
        *continuous.schedule(len(matrix[0]), len(matrix), held, seed, original), plan['validationRows'])
    previous, attempted, search_cache = [], set(), {}
    costs = Counter()
    journals = []
    for layout, before in zip(layouts, expected['steps'], strict=True):
        cases = layout['qualify']
        nominee = archive.nominate(incumbent, previous, attempted, 'runner-up')
        replies, requested, search = {}, [], {}
        archive_promoted, reserved = False, 0
        old_search_reads = len(search_cache)

        def qualification_lookup(prompt, case):
            key = (prompt, case)
            if case not in cases or prompt not in (incumbent, nominee, *layout['alternatives']):
                raise ValueError('Qualification left its cohort or prompt pool')
            if key not in replies:
                replies[key] = matrix[int(prompt)][case] == '1'
            return replies[key]

        def qualify(prompt, row, repeat):
            if repeat != 0:
                raise ValueError('The archived transfer uses one repeat per case')
            reply = qualification_lookup(prompt, int(row.id))
            requested.append((prompt, row.id, repeat, reply))
            return reply

        def evaluate(prompt, row):
            key = (prompt, int(row.id))
            if key[1] not in layout['validation'] or prompt not in (incumbent, *layout['alternatives']):
                raise ValueError('Validation left its cohort or prompt pool')
            if key not in search_cache:
                search_cache[key] = matrix[int(prompt)][key[1]] == '1'
            search[key] = search_cache[key]
            return Observation(search[key], {'correct': search[key]})

        if nominee is not None:
            attempted.add((incumbent, nominee))
            archive_promoted, reserved, _ = archive.qualify_archived(incumbent, nominee, cases, qualification_lookup)
        if archive_promoted:
            challenger = selected = nominee
        else:
            validation = [Row(str(case), 'task') for case in layout['validation']]
            qual_rows = [Row(str(case), 'task') for case in cases]
            result = run_fixed_pool_cycle(incumbent, layout['alternatives'], validation, qual_rows, evaluate,
                                          metric_limit=plan['searchCap'] - reserved, qualify=qualify, screen=screen,
                                          minimum_gain=original['minimumQualificationGain'], seed=layout['seed'])
            challenger, selected = result.search.prompt, result.prompt
            observations = () if result.qualification is None else result.qualification.observations
            if ((result.qualification is not None and result.qualification.status == 'undecided') or
                    result.search.evaluations != len(search) or result.qualification_evaluations != len(requested) or
                    tuple(requested) != tuple((row.prompt, row.row_id, row.repeat, row.passed) for row in observations)):
                raise ValueError('The wired cycle returned a decision or lookup count inconsistent with its callbacks')
        journal = [(prompt, case, outcome) for (prompt, case), outcome in search.items()]
        step = {'incumbent': incumbent, 'challenger': challenger, 'selected': selected,
                'archiveNominee': nominee, 'archivePromoted': archive_promoted, 'searchSha256': digest(journal)}
        if any(step[field] != before[field] for field in IDENTITY) or len(search) != before['searchLookups']:
            raise ValueError('The public cycle changed the archived search or promotion')
        archived = {(prompt, case): passed for prompt, case, passed in before['qualification']}
        if any(key not in archived or archived[key] is not passed for key, passed in replies.items()):
            raise ValueError('The public cycle used a qualification reply outside the archived evidence')
        costs.update(searchLookups=len(search), searchAfterReuse=len(search_cache) - old_search_reads,
                     fullQualification=before['qualificationLookups'], qualificationAfterStop=len(replies))
        previous.append(step)
        journals.append({'decision': step, 'observedQualification': requested, 'paidQualification': len(replies)})
        incumbent = selected
    costs['holdoutPasses'] = sum(matrix[int(incumbent)][case] == '1' for case in held)
    if incumbent != expected['candidate'] or costs['holdoutPasses'] != expected['holdoutPasses']:
        raise ValueError('The public cycle changed the final prompt or holdout')
    return costs, journals


def prepare(phase):
    raw = (ROOT / 'docs/bounded-transfer-matched-cost-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('The archived matched-cost report differs')
    stored = json.loads(raw, object_pairs_hook=unique_object)['runs'][phase]['report']
    parent, original, data, published = reference.prepare(phase)
    if digest(parent) != stored['planSha256']:
        raise ValueError('The archived matched-cost plan differs')
    plan = {
        'protocol': 'cpo-fixed-pool-cycle-replay-v1', 'phase': phase,
        'parentPlanSha256': digest(parent), 'parentReportSha256': SOURCE_SHA256,
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'cycleSha256': sha256((ROOT / 'cpo/fixed_pool_cycle.py').read_bytes()).hexdigest(),
        'gepaVersion': parent['gepaVersion'], 'methods': list(METHODS),
        'validationRows': parent['validationRows'], 'searchCap': reference.first.transfer.DESIGNS['candidate'][1],
        'scope': 'Call the public fixed-pool cycle with metered callbacks. Verify decisions and paid lookup counts.',
    }
    return plan, original, data, published, stored['panels']


def replay(plan, original, panels, published, costs):
    report = {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        arms = {}
        for method in METHODS:
            total = Counter()
            before, journals = [], []
            for seed in original['seeds']:
                with patch.object(archive, 'METHODS', archive.METHODS[:1]):
                    expected, expect_cost = reference.captured_episode(
                        matrix, held, seed, original, method, plan['validationRows'])[method]
                current, journal = run_episode(matrix, held, seed, original, plan, method, expected)
                if current != expect_cost:
                    raise ValueError('The wired callbacks did not spend the predicted lookup counts')
                total.update(current)
                before.append(expected)
                journals.append(journal)
            if digest(before) != published[name]['traceSha256'][method] or (
                    reference.summary(total) != costs[name]['totals'][method]):
                raise ValueError('The public path failed to reproduce published decision or cost evidence')
            arms[method] = {'totals': reference.summary(total), 'callbackTraceSha256': digest(journals)}
        report[name] = arms
    return {'plan': plan, 'planSha256': digest(plan), 'panels': report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=reference.transfer.SOURCES, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current phase seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version for the archived benchmark')
    report = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
