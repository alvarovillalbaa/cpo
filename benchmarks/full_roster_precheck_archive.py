"""Verify paid-trace parity of the opt-in runner with its archived prototype."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import feedback_rejection_scout as scout
from benchmarks import full_roster_precheck_prospective as prospective
from benchmarks import promptolution_settled_episode_transfer as transfer
from benchmarks import settled_episode_api_parity as parity
from benchmarks import settled_episode_refit as refit
from cpo import feedback_episode as feedback
from cpo._contract import digest
from cpo.full_roster_precheck import run_full_roster_feedback_episode


PROTOTYPE = 'full-roster-validation-first'


def verify(corpus):
    old = prospective.locked('witness-nomination-cost-v1.json', prospective.ARCHIVE_SHA)
    if digest(old['plan']) != old['planSha256'] or version('gepa') != old['plan']['gepaVersion']:
        raise ValueError('Use the sealed benchmark and its pinned GEPA version')
    archive = transfer.donor.load_corpus(corpus.read_bytes())
    original = transfer.prepare()
    promptolution, language = {}, {}
    with patch.dict(transfer.RUNNERS, {transfer.FEEDBACK: run_full_roster_feedback_episode}):
        for task in original['tasks']:
            panel = archive[task]
            matrix = panel['correctness']
            held = sorted(Random(f"{original['holdoutSeed']}/{task}").sample(
                range(len(panel['caseIDs'])), transfer.donor.HOLDOUT,
            ))
            totals, traces = Counter(), []
            for seed in original['seeds']:
                windows = transfer.layout(original, task, seed, held)
                winner, costs, trace = transfer.play(original, matrix, windows, seed, transfer.FEEDBACK)
                traces.append(trace)
                totals.update(costs, holdoutPasses=sum(matrix[winner][case] == '1' for case in held))
            key = f'{transfer.FEEDBACK}/{PROTOTYPE}'
            point = {'episodes': len(traces), 'totals': totals, 'paidTraceSha256': digest(traces)}
            expected = old['promptolution']['tasks'][task]
            if totals != expected['totals'][key] or point['paidTraceSha256'] != expected['traceSha256'][key]:
                raise ValueError(f'The opt-in runner changed the prototype trace on {task}')
            promptolution[task] = point

    plan, context, baseline = refit.contract()
    fitted = json.loads(refit.transfer.read_locked('docs/settled-episode-refit-v1.json', parity.FIT_SHA))
    with patch.object(feedback, 'run_feedback_episode', run_full_roster_feedback_episode):
        for cohort in refit.discovery.COHORTS:
            target, (panels, *_) = refit.target(cohort, plan, context, baseline, fitted)
            locked = transfer.locked(f'docs/settled-episode-refit-transfer-{cohort.lower()}-v1.json',
                                     parity.LOCKS[cohort.lower()])
            if digest(target) != locked['planSha256']:
                raise ValueError('Use the sealed cohort layout')
            totals, trace, episodes = Counter(), sha256(), 0
            for subject, model, seed, cells, stages, start in refit.previous.episodes(target, panels):
                result, paid = scout.language_episode(cells, stages, start)
                totals.update(holdoutPasses=sum(cells[result.prompt][case] for case in stages[0][2][-1]),
                              paidLookups=len(paid),
                              overriddenCycles=sum(action != result.schedule for action in result.cycle_schedules))
                totals.update(f'{role}Lookups' for role, *_ in paid)
                trace.update(bytes.fromhex(digest((subject, model, seed, result.prompt, result.cycle_schedules, paid))))
                episodes += 1
            expected = old['language'][cohort]
            if (episodes != expected['episodes'] or totals != expected['totals'][PROTOTYPE]
                    or trace.hexdigest() != expected['traceSha256'][PROTOTYPE]):
                raise ValueError(f'The opt-in runner changed the prototype trace on {cohort}')
            language[cohort] = {'episodes': episodes, 'totals': totals, 'paidTraceSha256': trace.hexdigest()}
    return {'protocol': 'cpo-full-roster-precheck-archive-parity-v1', 'prototypeReceiptSha256': prospective.ARCHIVE_SHA,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'promptolution': promptolution, 'language': language, 'providerRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a fresh output path')
    result = verify(args.corpus)
    with args.out.open('x') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
