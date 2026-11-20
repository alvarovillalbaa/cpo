"""Verify decision-equivalent finalist bounds on three sealed archives."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import balanced_finalist_race as race
from benchmarks import finalist_score_bounds as bounds
from benchmarks import independent_mmlu_cost_frontier as frontier
from benchmarks import routed_finalist_model_transfer as transfer
from benchmarks.independent_mmlu_transfer import read_json
from benchmarks.prompteval_transfer import holdout
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
PHASES = ('bbh-lmentry', 'mmlu', 'model-transfer')
POLICIES = ('balanced-six', 'wide-after-two-misses')
MODES = ('exact', 'eager-bounds', 'deferred-bounds')
TRANSFER_SHA256 = 'c1eb91255cdfd0d124695f1d9710552bdb49ce54ad86db446e8af8984a3444a7'
FIELDS = ('holdoutPasses', 'paidLookups', 'qualificationPaid')


def prepare(phase):
    if phase == 'model-transfer':
        head = transfer.design()
        raw = (ROOT / 'docs/routed-finalist-model-transfer-results-v1.json').read_bytes()
        corpus = (ROOT / 'benchmarks/data/routed-finalist-model-transfer-v1.json').read_bytes()
        report = read_json(raw)
        if (sha256(raw).hexdigest() != TRANSFER_SHA256 or report['planSha256'] != digest(head)
                or report['corpusSha256'] != sha256(corpus).hexdigest()):
            raise ValueError('The frozen transfer score snapshot or its report differs')
        panels, source_sha = read_json(corpus)['panels'], TRANSFER_SHA256
        keys = ('cpo-always-wide', 'cpo-two-miss', 'gepa-batched-52', 'gepa-sequential-52')
    else:
        head, panels, _ = race.prepare(phase)
        raw = (ROOT / 'docs/balanced-finalist-race-results-v1.json').read_bytes()
        report = read_json(raw)[phase]
        source_sha = transfer.PARENT_SHA256
        if sha256(raw).hexdigest() != source_sha or report['planSha256'] != digest(head):
            raise ValueError('The earlier finalist race report differs')
        keys = (*POLICIES, 'gepaBatched', 'gepaSequential')
    references = {name: {label: panel['methods'][key] for label, key in
                         zip((*POLICIES, 'gepaBatched', 'gepaSequential'), keys, strict=True)}
                  for name, panel in report['panels'].items()}
    plan = {
        'protocol': 'cpo-finalist-bound-replay-v1', 'phase': phase, 'sourceReportSha256': source_sha,
        'parentPlanSha256': digest(head), 'policies': list(POLICIES), 'modes': list(MODES),
        **{key: head[key] for key in ('schedule', 'searchCap', 'validationRows', 'gepaVersion')},
        'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in (
            'benchmarks/finalist_bound_replay.py', 'benchmarks/finalist_score_bounds.py',
            'benchmarks/balanced_finalist_race.py', 'benchmarks/archive_complementarity_transfer.py', 'cpo/pool.py')},
        'scope': ('Fund the same shortlist and exact winner objective. Use only paid replies to resolve bounds. '
                  'Require every nominee, promotion, and qualification trace to match the original race.'),
    }
    return plan, panels, references


def run(matrix, held, seed, plan, policy, mode):
    if mode == 'exact':
        return race.run(matrix, held, seed, plan, policy)
    lookups = Counter(incumbentLookups=0, screenLookups=0, finalistLookups=0)

    def select(incumbent, candidates, rows, evaluate, *, metric_limit, width, screen_rows):
        return bounds.select_by_bounds(incumbent, candidates, rows, evaluate, metric_limit=metric_limit,
                                       width=width, screen_rows=screen_rows, defer_incumbent=mode == 'deferred-bounds',
                                       audit=lookups)

    with patch.object(race, 'balanced_screen', select):
        totals, trace = race.run(matrix, held, seed, plan, policy)
    totals.update(lookups)
    return totals, trace


def choices(trace):
    return [(step['decision']['incumbent'], step['decision']['challenger'], step['decision']['selected'],
             step['decision']['archiveNominee'], step['decision']['archivePromoted'],
             step['paidQualification'], step['observedQualification']) for step in trace]


def panel_results(matrix, held, plan, reference):
    result = {label: {k: reference[label][k] for k in ('holdoutPasses', 'paidLookups')}
              for label in ('gepaBatched', 'gepaSequential')}
    for policy in POLICIES:
        totals = {mode: Counter() for mode in MODES}
        traces = {mode: [] for mode in MODES}
        compared = {mode: Counter() for mode in MODES[1:]}
        for seed in plan['schedule']['seeds']:
            baseline, original = run(matrix, held, seed, plan, policy, 'exact')
            totals['exact'].update(baseline)
            traces['exact'].append(original)
            original_path = choices(original)
            for mode in MODES[1:]:
                point, trace = run(matrix, held, seed, plan, policy, mode)
                if (choices(trace) != original_path or point['holdoutPasses'] != baseline['holdoutPasses']
                        or point['qualificationPaid'] != baseline['qualificationPaid']
                        or point.get('wideCycles') != baseline.get('wideCycles')):
                    raise ValueError('A bound race changed the frozen search or qualification decisions')
                totals[mode].update(point)
                traces[mode].append(trace)
                compared[mode].update(less=int(point['searchPaid'] < baseline['searchPaid']),
                                      more=int(point['searchPaid'] > baseline['searchPaid']),
                                      tied=int(point['searchPaid'] == baseline['searchPaid']))
        result[policy] = {}
        for mode, count in totals.items():
            point = dict(count, paidLookups=count['searchPaid'] + count['qualificationPaid'],
                         traceSha256=digest(traces[mode]))
            if mode == 'exact':
                frontier.expect_reference(point, reference[policy])
            else:
                point['episodeLookupComparison'] = dict(compared[mode])
            result[policy][mode] = point
    return result


def replay(plan, data, reference):
    panels, totals = {}, {policy: {mode: Counter() for mode in MODES} for policy in POLICIES}
    totals.update({label: Counter() for label in ('gepaBatched', 'gepaSequential')})
    for panel in data:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = holdout(subject, len(matrix[0]))
        results = panel_results(matrix, held, plan, reference[name])
        for label in ('gepaBatched', 'gepaSequential'):
            totals[label].update(results[label])
        for policy in POLICIES:
            for mode, values in results[policy].items():
                totals[policy][mode].update({key: values[key] for key in FIELDS})
        panels[name] = results
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels, 'totals': totals}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--phase', choices=PHASES, required=True)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Execution requires the current seal and a fresh report path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
