"""Verify the packaged settled episode against sealed archived decisions and costs."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import settled_episode_refit as refit
from cpo import Observation, Row
from cpo._contract import digest
from cpo.settled_episode import EpisodeCycle, run_settled_episode


FIT_SHA = '722c4170fc156acd1b0e9f499f3619b2a5edb539aea946d1272d4369ae8f435f'
LOCKS = {
    'bounded-bbh': '7c8451cbc72c8f9269ec42360c13ad6339d388baf65bb50f6fe861bb1e1f89a3',
    'bounded-lmentry': 'e4624f1b16d0000f67266dcb2b0c90f6cdd47898e3664385ed4c940d7626f25f',
    'bounded-mmlu': '581bfae8b75dc897326c1d3e376c1f72aaf29388f4f0cad24643ca7a91d9caf6',
    'four-case-mmlu': 'd762a35942403485f1142e7090c9cf693b4b531fd1867ac816a921e7609d1dd5',
    'tie-bbh': 'f4c6d4fda704ba7e210457f0ca2e5adffb5c518b102359d6ee098cf77fb72765',
    'tie-lmentry': '728d3620b241d7835bfddc9075e8610f5e3855c144bb1a1b139360a83fea4bc1',
    'additional-mmlu': '85fd60522ba28610af3fd120382e9bd9c4c321ceb95697c452c29ee5d5d59e74',
}


def compare(plan, panels, models, static):
    original, reordered = refit.engines(plan, models, static)
    reference_runners = {**original, **reordered}
    outer_cap = max(limit for _, _, _, limit in plan['controls'])
    table = plan['revisedActions'][refit.SETTLED]
    totals, decisions, trace = Counter(), Counter(), sha256()
    for subject, model, seed, cells, stages, start in refit.previous.episodes(plan, panels):
        state, probe = refit.previous.probe(refit.EAGER, plan['probeModes'], cells, stages, start)
        action = table[int(state)]
        expected_probe = probe[:refit.probe_cost(table, int(not probe[0][2]), int(probe[0][2]), settled=True)]
        expected_paid = [('training', prompt, str(case), grade) for prompt, case, grade in expected_probe]
        incumbent, expected_cycles = start, []
        for local_seed, roster, roles in stages:
            result, paid = refit.native.paired.cycle.execute_path(
                reference_runners[action], cells, incumbent, roster, roles, local_seed, outer_cap, 1,
            )
            expected_cycles.append(result)
            expected_paid.extend((*key, grade) for key, grade in paid.items())
            incumbent = result.prompt

        actual_paid = []

        def grade(prompt, row):
            passed = bool(cells[prompt][int(row.id)])
            actual_paid.append((row.family, prompt, row.id, passed))
            return passed

        def qualify(prompt, row, repeat):
            if repeat != 0:
                raise ValueError('Archive qualification grades have one repeat')
            return grade(prompt, row)

        training = tuple(Row(str(case), 'training') for case in stages[0][2][0][:2])
        cycles = tuple(
            EpisodeCycle(tuple(roster), tuple(Row(str(case), 'validation') for case in roles[1]),
                         tuple(Row(str(case), 'qualification') for case in roles[2]), local_seed)
            for local_seed, roster, roles in stages
        )
        result = run_settled_episode(
            start, training, cycles, lambda prompt, row: Observation(grade(prompt, row), {}),
            probe=grade, qualify=qualify,
        )
        if (result.prompt != incumbent or result.schedule != action or result.cycles != tuple(expected_cycles)
                or result.training_evaluations != len(expected_probe) or result.evaluations != len(actual_paid)
                or actual_paid != expected_paid):
            raise ValueError(f'Packaged episode diverged for {subject}/{model}/{seed}')
        totals.update(holdoutPasses=sum(cells[result.prompt][case] for case in stages[0][2][-1]),
                      paidLookups=result.evaluations, trainingLookups=result.training_evaluations)
        decisions[result.schedule] += 1
        trace.update(bytes.fromhex(digest((subject, model, seed, result.prompt, actual_paid))))
    return {'episodes': sum(decisions.values()), 'totals': totals, 'decisions': decisions,
            'paidTraceSha256': trace.hexdigest()}


def verify():
    transfer = refit.transfer
    plan, context, baseline = refit.contract()
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Replay requires the pinned GEPA version')
    fitted = json.loads(transfer.read_locked('docs/settled-episode-refit-v1.json', FIT_SHA))
    results = {}
    for cohort in refit.discovery.COHORTS:
        name = cohort.lower()
        target, (panels, models, static, *_) = refit.target(cohort, plan, context, baseline, fitted)
        archived = json.loads(transfer.read_locked(f'docs/settled-episode-refit-transfer-{name}-v1.json', LOCKS[name]))
        if digest(target) != archived['planSha256'] or digest(archived['plan']) != archived['planSha256']:
            raise ValueError(f'The original plan must reproduce for {cohort}')
        point = compare(target, panels, models, static)
        prior = archived['results']
        if (point['totals'] != prior['policies'][refit.SETTLED]
                or point['decisions'] != prior['decisions'][refit.SETTLED]
                or point['episodes'] != prior['episodes']):
            raise ValueError(f'The archived totals must reproduce for {cohort}')
        results[cohort] = point
    files = (Path(__file__).resolve(), transfer.ROOT / 'cpo/settled_episode.py')
    return {'fitReceiptSha256': FIT_SHA, 'transferReceiptSha256': LOCKS,
            'sourceSha256': {str(file.relative_to(transfer.ROOT)): sha256(file.read_bytes()).hexdigest()
                             for file in files},
            'providerRequests': 0, 'cohorts': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a fresh receipt path')
    report = verify()
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
