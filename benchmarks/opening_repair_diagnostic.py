"""Expose demonstration-masked errors during a funded typed repair."""

import argparse
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import alternative_controls as programs
from benchmarks import grounded, opening_screen_repair as earlier, opening_screen_typed as typed, typed_policy
from benchmarks.case_difficulty_allocation import checked_file
from cpo._contract import digest


REFERENCE = '13a6c2f15da515b2e169e0575564cf590b22750b53a26a300280a6f816e96690'
PRIMARY = 'instruction-probes'
PROBES = 2
FRESH_SEEDS = (47311, 47321, 47339, 47351, 47363, 47381)


def diagnostic_cycle():
    repair = earlier.staged_cycle(PROBES)

    def run(incumbent, train, validation, holdout, evaluate, propose, **settings):
        train = tuple(train)
        training_ids = {row.id for row in train}
        probes = []

        def observe(program, row):
            if row.id not in training_ids:
                return evaluate(program, row)
            original = grounded.load_json(program)
            stripped = programs.encode(original['instruction'])
            reply = evaluate(stripped, row)
            probes.append({'row_id': row.id, 'withheld_demonstrations': len(original['demos']),
                           'instruction_only_passed': reply.passed})
            return reply

        result = repair(incumbent, train, validation, holdout, observe, propose, **settings)
        search = replace(result.search, events=[*result.search.events, {'kind': PRIMARY, 'probes': probes}])
        return replace(result, search=search)

    return run


def rerun_repair(task, groups, seed, cap, cycle):
    with (patch.object(typed, 'ARMS', ('cpo-adaptive',)),
          patch.object(typed, 'run_expected_cost_proposal_cycle', cycle)):
        return typed.trial(task, groups, seed, cap)['arms']['cpo-adaptive']


def measure(cohorts, caps, *, original=None, saved_repairs=None):
    results = {}
    for cap in caps:
        selected = str(cap)
        if original is None:
            trials = [typed.trial(task, groups, seed, cap)
                      for seed, tasks in cohorts.items() for task, groups in tasks.items()]
        else:
            saved = saved_repairs[selected]['repairTrials']
            trials = [{**old, 'arms': {**old['arms'], **new['arms']}}
                      for old, new in zip(original[selected]['trials'], saved, strict=True)]
        for trial in trials:
            seed, task = trial['seed'], trial['task']
            groups = cohorts[seed][task]
            if original is None:
                for arm, width in earlier.POLICIES.items():
                    trial['arms'][arm] = rerun_repair(task, groups, seed, cap, earlier.staged_cycle(width))
            trial['arms'][PRIMARY] = rerun_repair(task, groups, seed, cap, diagnostic_cycle())
        with (patch.object(typed, 'ARMS', (*typed.ARMS, *earlier.POLICIES, PRIMARY)),
              patch.object(typed, 'CPO', (PRIMARY, 'cpo-adaptive'))):
            summary = typed.summary(trials)
        paths = {arm: digest([trial['arms'][arm] for trial in trials])
                 for arm in (*typed.ARMS, *earlier.POLICIES, PRIMARY)}
        diagnostic = [{**trial, 'arms': {arm: trial['arms'][arm] for arm in (PRIMARY, 'repair-two')}}
                      for trial in trials]
        results[selected] = {**summary, 'armPathsSha256': paths, 'diagnosticTrials': diagnostic}
    return results


def prepare():
    parent, cohorts, original = earlier.prepare()
    archive = checked_file('docs/opening-screen-repair-results-v1.json', REFERENCE)
    if digest(parent) != archive['designSha256'] or set(cohorts).intersection(FRESH_SEEDS):
        raise ValueError('The staged repair design changed or cohorts overlap')
    fresh = {seed: typed_policy.cohorts(seed) for seed in FRESH_SEEDS}
    design = {'protocol': 'cpo-opening-repair-diagnostic-v1', 'referenceReportSha256': REFERENCE,
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'searchCaps': parent['searchCaps'], 'primaryCap': parent['primaryCap'],
              'gepaVersion': parent['gepaVersion'], 'primary': PRIMARY, 'primaryCohort': 'fresh-seeds',
              'trainingProbeCap': PROBES, 'freshCohortSha256': {str(s): digest(d) for s, d in fresh.items()},
              'gate': parent['gate'], 'scope': ('Remove demonstrations only during training probes for the optional '
                                               'repair. Keep the full prompt for validation and qualification.')}
    return design, parent, cohorts, original, archive['results'], fresh


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, parent, cohorts, original, saved_repairs, fresh = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        cli.error('Use GEPA 0.1.4')
    if earlier.run_trials(parent, cohorts, original) != saved_repairs:
        raise ValueError('The published staged-repair traces changed')
    caps = design['searchCaps']
    results = {'prior-seeds': measure(cohorts, caps, original=original, saved_repairs=saved_repairs),
               'fresh-seeds': measure(fresh, caps)}
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
