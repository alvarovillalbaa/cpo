"""Preserve frozen routing decisions while skipping grades that cannot change the action."""

import argparse
from collections import Counter
from dataclasses import replace
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import cohort_budgeted_archive_routing as previous
from cpo._contract import digest
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.paired_qualification import QualificationDecision, QualificationObservation
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run


routing, transfer = previous.previous, previous.transfer
FIT = 'docs/cohort-budgeted-archive-routing-fit-v1.json'
FIT_SHA = '03efa6bac5004515cc8c1b72a01bcf7b404803416312974e536e6cda3aec4dcf'
TABLES = (previous.POOLED, *previous.POLICIES)
OPTIMIZED = {name: f'{name}-short-circuit' for name in TABLES}
PRIMARY = OPTIMIZED[previous.BUDGETED]
STATIC = previous.STATIC
RECEIPTS = dict(zip(previous.COHORTS, (
    'b041b5484893aab20a958ff090ec0cd74443c82a2355929e85f11e5cdedc821a',
    '367098d3bac39f2a8f48a924a367e269e080f567bb4a1e357e8703a63ec42dbe',
    '7b8adc11bb8262c95baf79bbff9872b322168ff43fb59b097d614da3ccbcd701',
    '14137163117f7726fbe699ab8edc776d9467a1c7c23544967a2c768a5aea86f3',
    'cf2de90ed9ccd08d83402082aaed175e83ad22205ff10588c1938c62546d5adc',
    'cc58305458e3bb444e6ecbe990170d84f92b2920c250a80cf1fe49a93a90f162',
    '2750bb5e71174e445b2c9c20c989cd8385c5c84e951f9ce3a9a3b797d6fbe2fc',
), strict=True))


def optimized_cycle(incumbent, candidates, validation, qualification, evaluate, *,
                    metric_limit, qualify, minimum_gain, seed, actions, fallback):
    """Execute a one-gain routing table and retain the exact proof for every nominee."""
    candidates, validation, rows = tuple(candidates), tuple(validation), tuple(qualification)
    ids = {row.id for row in (*validation, *rows)}
    if not validation or not rows or len(ids) != len(validation) + len(rows):
        raise ValueError('Validation and qualification must be nonempty, distinct and disjoint')
    if incumbent in candidates or len(candidates) != len(set(candidates)):
        raise ValueError('The pool needs distinct challengers besides the incumbent')
    if type(metric_limit) is not int or metric_limit < len(validation) or type(minimum_gain) is not int or minimum_gain != 1:
        raise ValueError('This routed comparison requires a funded panel and one independent gain')
    if not candidates:
        return FixedPoolCycleResult(FinalistResult(incumbent, None, 0),
                                    QualificationDecision('rejected', incumbent, (), 0, 0))
    lookup = tuple((actions.get(f'{i}/0', fallback), actions.get(f'{i}/1', fallback)) for i in range(1, len(rows) + 1))
    searchable = [i for i, pair in enumerate(lookup, 1) if any(name != transfer.RETAIN for name in pair)]
    limit = searchable[-1] if searchable else 0
    prefix = {}
    for row in rows[:limit]:
        passed = qualify(incumbent, row, 0)
        if type(passed) is not bool:
            raise ValueError('Qualification requires exact boolean outcomes')
        prefix[row.id] = passed
        if not passed:
            break
    else:
        observations = tuple(QualificationObservation(incumbent, row, 0, True) for row in prefix)
        decision = QualificationDecision('rejected', incumbent, observations, -len(rows), len(rows) - len(prefix))
        return FixedPoolCycleResult(FinalistResult(incumbent, None, 0), decision)

    def qualified(prompt, row, repeat):
        if prompt == incumbent and repeat == 0 and row.id in prefix:
            return prefix[row.id]
        return qualify(prompt, row, repeat)

    def screen(base, roster, panel, observe, cap):
        rejected = FinalistResult(base, None, 0)
        miss_action, pass_action = lookup[len(prefix) - 1]
        if miss_action == pass_action:
            engine = routing.SCREENS[miss_action]
            return (rejected, None) if engine is None else engine(base, roster, panel, observe, cap)

        first_row = panel[0]
        first = observe(base, first_row)
        if type(first.passed) is not bool:
            raise ValueError('The paid validation feature must be an exact boolean')
        engine = routing.SCREENS[pass_action if first.passed else miss_action]
        if engine is None:
            return replace(rejected, evaluations=1), None
        paid = 1

        def cache(prompt, row):
            nonlocal paid
            if prompt == base and row.id == first_row.id:
                return first
            paid += 1
            return observe(prompt, row)

        selected, counts = engine(base, roster, panel, cache, cap)
        if paid > cap:
            raise ValueError('The profiled screen must fund the probe within its original search cap')
        return replace(selected, evaluations=paid), counts

    return _run(incumbent, candidates, validation, rows, evaluate, metric_limit=metric_limit,
                qualify=qualified, minimum_gain=minimum_gain, seed=seed, screen=screen)


def prepare(cohort):
    inherited, discovery, pooled = previous.training_plan()
    fit = previous.read_json(FIT, FIT_SHA)
    if digest(inherited) != fit['planSha256'] or digest(fit['plan']) != fit['planSha256']:
        raise ValueError('The fitted table must match its source plan')
    base, panels, _ = previous.target_plan(cohort, fit, discovery)
    path = f'docs/cohort-budgeted-archive-routing-{cohort.lower()}-v1.json'
    reference = previous.read_json(path, RECEIPTS[cohort])
    if reference['planSha256'] != digest(base):
        raise ValueError('The prior results must match the exact transfer configuration')
    models = {previous.POOLED: pooled['models'][previous.POOLED], **fit['models']}
    plan = {**base, 'protocol': 'short-circuit-archive-routing-v1',
            'parentReceiptSha256': RECEIPTS[cohort], 'constrainedFitSha256': FIT_SHA,
            'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'primaryByCohort': dict.fromkeys(previous.COHORTS, PRIMARY),
            'scope': 'Use the three frozen routing tables with no refitting. Skip the incumbent validation '
                     'probe when both outcomes select the same screen. Stop the qualification precheck when '
                     'all remaining first-miss positions choose retention. Preserve nominated and deployed '
                     'prompts and every admitted qualification receipt. Reprice the complete split-safe menu.'}
    return plan, panels, models, pooled['models'][STATIC], reference['results']


def make_runners(models, static):
    ordinary = {name: routing.fitted_runner(previous.POOLED, {STATIC: static, previous.POOLED: model}, Counter())
                for name, model in models.items()}
    compact = {OPTIMIZED[name]: partial(optimized_cycle, actions=model['actions'], fallback=static['actions'][routing.OPEN])
               for name, model in models.items()}
    return ordinary, compact


def audit(panels, plan, ordinary, compact, reference):
    run = transfer.native.paired.cycle.execute_path
    point = transfer.native.paired.reference.point
    fingerprints, savings = {}, {name: Counter() for name in TABLES}
    for subject, model, matrix in panels:
        cells, _ = transfer.case_cells(matrix)
        traces = {name: [] for name in (*ordinary, *compact)}
        for seed in plan['seeds']:
            start, roster, roles = transfer.layouts.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
            args = cells, start, roster, roles, seed, plan['fullRosterCap'], 1
            for name, runner in ordinary.items():
                old, before = run(runner, *args)
                fresh, after = run(compact[OPTIMIZED[name]], *args)
                if (old.prompt, old.search.finalist) != (fresh.prompt, fresh.search.finalist):
                    raise ValueError('Nomination and deployment must match the frozen routing table')
                if old.search.finalist is not None and old.qualification != fresh.qualification:
                    raise ValueError('Every nominated path must keep its full exact qualification receipt')
                if not after.items() <= before.items() or any(prompt != start for _, prompt, _ in before.keys() - after.keys()):
                    raise ValueError('Only original incumbent grades can be omitted')
                if fresh.qualification.observations != old.qualification.observations[:fresh.qualification_evaluations]:
                    raise ValueError('Rejected incumbent evidence must remain an ordered prefix')
                validation = old.search.evaluations - fresh.search.evaluations
                proof = old.qualification_evaluations - fresh.qualification_evaluations
                savings[name].update(validationSaved=validation, qualificationSaved=proof,
                                     changedPaths=int(bool(validation or proof)), episodes=1)
                traces[name].append(point(cells, roles[-1], old, before)[2])
                traces[OPTIMIZED[name]].append(point(cells, roles[-1], fresh, after)[2])
        panel = f'{subject}/{model}'
        fingerprints[panel] = {name: digest(path) for name, path in traces.items()}
        if any(fingerprints[panel][name] != reference['panelPathHashes'][panel]['gain-1'][name] for name in ordinary):
            raise ValueError('All frozen routing traces must reproduce before any savings claim')
    return fingerprints, savings


def measure(plan, panels, models, static, reference):
    ordinary, compact = make_runners(models, static)
    traces, savings = audit(panels, plan, ordinary, compact, reference)
    runners = {**ordinary, **compact, STATIC: routing.fitted_runner(STATIC, {STATIC: static}, Counter())}
    compare = transfer.compare_attainers
    effect = {}

    def control(panels, plan, vectors, schedules, expected, primary):
        paired = transfer.native.frozen.paired_effects.paired_effect
        effect.update(paired(vectors, PRIMARY, STATIC, plan))
        return compare(panels, plan, vectors, schedules, expected, primary)

    with patch.multiple(transfer, RUNNERS=runners, verify_witness=routing.verify_qualification, compare_attainers=control):
        report = transfer.measure(panels, plan)
    if report['nativeSubjectTotalsSha256'] != reference['nativeSubjectTotalsSha256']:
        raise ValueError('The complete native menu must reproduce before repricing')
    for panel, path in traces.items():
        if any(report['panelPathHashes'][panel]['gain-1'][name] != value for name, value in path.items()):
            raise ValueError('The audited and priced runs must match every trace')
    points = report['cpo']['gain-1']
    report['primaryGatePassed'] &= (points[PRIMARY]['paidLookups'] <= points[STATIC]['paidLookups']
                                    and effect['pairedRange95'][0] > 0)
    for name, candidate in OPTIMIZED.items():
        if points[name]['paidLookups'] - points[candidate]['paidLookups'] != (
            savings[name]['validationSaved'] + savings[name]['qualificationSaved']
        ):
            raise ValueError('Savings must reconcile to every omitted callback')
    return {**report, 'exactSavingsByTable': savings, 'primaryPairedAgainstStatic': effect}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=previous.COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels, models, static, reference = prepare(args.cohort)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh path and pinned GEPA')
    result = measure(plan, panels, models, static, reference)
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': result}, out,
                  indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
