"""Compare whole-schedule Halving certification with round-by-round certification."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_fallback_routing as routing
from cpo._contract import digest
from cpo.halving import HalvingSearch
from cpo.halving import lookahead


ROOT = routing.ROOT
CAPS = (8, 16, 32)
ROUND, WHOLE = 'rounds', 'lookahead'
SELECTORS = {ROUND: HalvingSearch, WHOLE: lookahead.LookaheadHalving}


def prepare():
    prior, refs, bbh, mmlu = routing.prepare()
    native_file = ROOT / routing.transfer.SOURCE
    raw = native_file.read_bytes()
    if sha256(raw).hexdigest() != routing.transfer.SOURCE_SHA:
        raise ValueError('The native control frontier differs from its published receipt')
    paths = (Path(__file__).resolve(), Path(lookahead.__file__).resolve())
    plan = {'protocol': 'witness-halving-lookahead-v1', 'parentPlanSha256': digest(prior),
            'sourceSha256': {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest() for path in paths},
            'archiveReferences': prior['references'], 'nativeBBHAndLMentrySha256': routing.transfer.SOURCE_SHA,
            'physicalLookupCaps': CAPS, 'logicalHalvingLimit': 8, 'pairedCaseDraws': prior['pairedCaseDraws'],
            'resamplingSeed': prior['resamplingSeed'],
            'candidate': 'Skip deterministic eliminations and read first-round grades until at most 512 '
                         'completions remain. Then minimize worst search depth to prove the exact final winner. '
                         'Break ties by cumulative work across equally weighted binary completions, then by cell order.',
            'comparison': 'Preserve the original witness search, fallback eligibility, independent admission and holdout.'}
    return plan, refs, bbh, mmlu, json.loads(raw)


def measure(inputs, panels, reference, base_cap, cohorts):
    schedule, policy = inputs['schedule'], inputs['qualificationBank']
    active = {**schedule, 'evaluationLookupLimit': base_cap}
    replay = routing.transfer
    points = [f'{mode}/{cap}' for mode in SELECTORS for cap in CAPS]
    subjects = {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        held = replay.REPLAY.transfer.holdout(subject, len(matrix[0]))
        identity = tuple(panel['caseIDs'][index] for index in held) if 'caseIDs' in panel else panel['caseOrderSha256']
        group = subjects.setdefault(subject, {'cohort': cohorts[subject], 'identity': identity, 'held': held,
                                               'decisionsPerCase': 0,
                                               'baseline': Counter(), 'points': {point: Counter() for point in points},
                                               'cases': {point: [0] * len(held) for point in points}})
        if (group['held'], group['identity']) != (held, identity):
            raise ValueError('Model panels must agree on aligned holdout columns')
        group['decisionsPerCase'] += len(schedule['seeds'])
        baseline = Counter()

        def score(prompt):
            return [matrix[int(prompt)][case] == '1' for case in held]

        for seed in schedule['seeds']:
            incumbent, layouts = replay.REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, active)
            selected, paid, _, grades, proof = replay.play(matrix, held, incumbent, layouts, active, policy, replay.witness)
            base = score(selected)
            baseline.update(holdoutPasses=sum(base), paidLookups=paid)
            if proof:
                continue
            complete = {}
            for mode, selector in SELECTORS.items():
                for cap in CAPS:
                    search = selector(metric_limit=cap, paid=grades)
                    final, proof_cost = routing.capped.transfer_trial(
                        matrix, held, incumbent, layouts, active, policy, search)
                    point = f'{mode}/{cap}'
                    changes = [int(new) - int(old) for new, old in zip(score(final), base, strict=True)]
                    group['cases'][point] = [left + right for left, right in zip(group['cases'][point], changes, strict=True)]
                    group['points'][point].update(addedPasses=sum(changes), validationLookups=search.evaluations,
                                                  proofLookups=proof_cost, exhausted=int(search.exhausted), episodes=1)
                    if cap == CAPS[-1]:
                        if search.exhausted:
                            raise ValueError('The full-cap comparison must finish every episode')
                        complete[mode] = final, proof_cost
            if complete[ROUND] != complete[WHOLE]:
                raise ValueError('Whole-schedule certification changed a full-cap deployment or proof')
        expected = reference[f'{subject}/{model}'][replay.BASE]
        if any(baseline[key] != expected[key] for key in baseline):
            raise ValueError('The witness baseline differs from the published archive')
        group['baseline'].update(baseline)
    return subjects


def summarize(groups, plan):
    baseline = sum_counters(unit['baseline'] for unit in groups.values())
    result = {}
    for cap in CAPS:
        rounds, whole = f'{ROUND}/{cap}', f'{WHOLE}/{cap}'
        points = {}
        for point in (rounds, whole):
            paid = sum_counters(unit['points'][point] for unit in groups.values())
            points[point.split('/')[0]] = {**paid, 'holdoutPasses': baseline['holdoutPasses'] + paid['addedPasses'],
                                          'paidLookups': baseline['paidLookups'] + paid['validationLookups'] + paid['proofLookups']}
        votes = {name: {'decisionsPerCase': unit['decisionsPerCase'],
                        'cases': {ROUND: unit['cases'][rounds], WHOLE: unit['cases'][whole]}}
                 for name, unit in groups.items()}
        with patch.object(routing.paired, 'BASELINE', ROUND):
            bands = routing.paired.paired_ranges(votes, WHOLE, plan)
        result[cap] = {**points, 'pairedVsRounds': bands}
    return {'witnessBaseline': baseline, 'points': result}


def sum_counters(rows):
    total = Counter()
    for row in rows:
        total.update(row)
    return total


def affordable_native(table, candidate):
    eligible = [(name, row) for name, row in table.items()
                if name.startswith('gepa-') and row['paidLookups'] <= candidate['paidLookups']]
    name, point = min(eligible, key=lambda item: (-Fraction(item[1]['macroAccuracy']), item[1]['paidLookups'], item[0]))
    return {'arm': name, **point, 'candidatePassDifference': candidate['holdoutPasses'] - point['holdoutPasses']}


def execute(plan, refs, bbh, mmlu, native):
    inputs, archive, prior = bbh
    base_cap = prior['plan']['conditions'][routing.transfer.BASE]['searchCap']
    subjects = measure(inputs, archive, prior['panels'], base_cap,
                       {panel['subject']: panel['subject'].split('-', 1)[0] for panel in archive})
    mmlu_plan, inputs, cohorts, prior = mmlu
    data = [panel for panels in cohorts.values() for panel in panels]
    subjects.update(measure(inputs, data, {key: row for phase in prior.values() for key, row in phase['panels'].items()},
                            mmlu_plan['baseSearchCap'], dict.fromkeys((p['subject'] for p in data), 'mmlu')))
    scopes = {cohort: summarize({key: val for key, val in subjects.items() if val['cohort'] == cohort}, plan)
              for cohort in ('bbh', 'lmentry', 'mmlu')}
    scopes['bbh-lmentry'] = summarize({key: val for key, val in subjects.items() if val['cohort'] != 'mmlu'}, plan)

    for cohort in ('bbh', 'lmentry', 'mmlu'):
        baseline = scopes[cohort]['points'][16][ROUND]
        if cohort != 'mmlu':
            expected = refs[routing.CAP_REPORT]['fallbackDeltas'][cohort]['certified/16']
            fields = ('addedPasses', 'proofLookups', 'validationLookups')
        else:
            expected = refs[routing.MMLU_REPORT]['pooled']['totals'][routing.mmlu.CANDIDATE]
            fields = ('holdoutPasses', 'paidLookups')
        if any(baseline[key] != expected[key] for key in fields):
            raise ValueError('Round-order Halving differs from its cap-16 control')
    for cohort, table in (('bbh-lmentry', native['totals']),
                          ('mmlu', refs[routing.MMLU_REPORT]['pooled']['totals'])):
        for ablation in scopes[cohort]['points'].values():
            for method in (ROUND, WHOLE):
                ablation[method]['affordableNative'] = affordable_native(table, ablation[method])
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'fullCapDeploymentParity': True,
            'scopes': scopes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    report = execute(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
