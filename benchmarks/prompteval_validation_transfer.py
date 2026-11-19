"""Test the previously frozen smaller-panel policy on disjoint PromptEval subjects."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import prompteval_archive_cycles as archive, prompteval_continuous as continuous
from benchmarks import prompteval_proxy as proxy, prompteval_transfer as transfer
from benchmarks import prompteval_validation_size as selection, prompteval_witnesses as witnesses
from cpo._contract import digest, unique_object


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '813c13e13bfb81a58e83a1eb1e58cf87954e8601aa3e62c4848d583411bbcbd9'
CORPUS_SHA256 = '2c79f692d761cb816e0066269b1f330f7d961f885177f166e067221f10263243'
DESIGNS = {'candidate': (12, 52), 'full-panel': (24, 88), 'full-budget': (24, 171)}
CPO = 'cpo-cycle.runner-up'


def prepare():
    raw = (ROOT / 'docs/prompteval-validation-size-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('The frozen validation selection study differs')
    source_study = json.loads(raw, object_pairs_hook=unique_object)
    for report in source_study['runs']:
        if (tuple(report['fixedDesigns']['half-scaled-budget']) != DESIGNS['candidate'] or
                tuple(report['fixedDesigns']['full']) != DESIGNS['full-panel']):
            raise ValueError('The transfer must use the exact prior panel sizes and caps')
    source, sizes, fingerprint = transfer.read_source()
    tuning = {*proxy.SUBJECTS, *witnesses.CONFIRMATION_SUBJECTS}
    if fingerprint != CORPUS_SHA256 or tuning & sizes.keys():
        raise ValueError('Transfer source must match the archived snapshot and exclude all tuning subjects')
    base = transfer.plan(source, sizes, fingerprint)
    original = {**base, 'seeds': list(continuous.SEEDS), 'cycles': continuous.CYCLES,
                'qualificationRowsPerCycle': continuous.QUALIFY_ROWS, 'minimumQualificationGain': 1}
    budget = original['validationRows'] + original['trainRows'] + original['cycles'] * original['qualificationRowsPerCycle']
    if any(count - len(base['holdoutCaseIDs'][subject]) < budget for subject, count in sizes.items()):
        raise ValueError('Transfer needs room for the unchanged schedule and disjoint qualification')
    paths = ('benchmarks/prompteval_validation_size.py', 'benchmarks/prompteval_archive_cycles.py',
             'benchmarks/prompteval_round_reserve.py', 'benchmarks/prompteval_continuous.py', 'cpo/cycle.py',
             'cpo/challenger.py')
    plan = {'protocol': 'cpo-prompteval-validation-transfer-v1', 'sourceStudySha256': SOURCE_SHA256,
            'corpusSha256': CORPUS_SHA256, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scheduleSha256': digest(original), 'dependenciesSha256': {
                file: sha256((ROOT / file).read_bytes()).hexdigest() for file in paths},
            'designs': DESIGNS, 'subjects': list(sizes), 'tuningSubjects': sorted(tuning),
            'gepaVersion': original['gepaVersion'], 'gate': 'Clear both matched GEPA controls on every transfer panel',
            'priorExperiments': 'The transfer subjects were used by earlier fixed-pool studies.'}
    return plan, original, source


def paired(current, control):
    totals = {'holdoutPasses': 0, 'searchLookups': 0, 'qualificationLookups': 0}
    left, right = totals.copy(), totals.copy()
    pair_counts = Counter(wins=0, ties=0, losses=0)
    for candidate, reference in zip(current, control, strict=True):
        difference = candidate['holdoutPasses'] - reference['holdoutPasses']
        pair_counts['wins' if difference > 0 else 'losses' if difference < 0 else 'ties'] += 1
        for summary, episode in ((left, candidate), (right, reference)):
            summary['holdoutPasses'] += episode['holdoutPasses']
            for role in ('searchLookups', 'qualificationLookups'):
                summary[role] += sum(step[role] for step in episode['steps'])
    return {**selection.compare(left, right), 'episodes': pair_counts}


def replay(plan, original, source):
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        held = original['holdoutCaseIDs'][subject]
        episodes = {name: [selection.episode(matrix, held, seed, original, rows, cap) for seed in original['seeds']]
                    for name, (rows, cap) in DESIGNS.items()}
        totals = {name: {method: {'holdoutPasses': sum(x[method]['holdoutPasses'] for x in result),
                                  'paidLookups': sum(x[method]['evaluations'] for x in result)}
                         for method in result[0]} for name, result in episodes.items()}
        current = [episode[CPO] for episode in episodes['candidate']]
        comparisons = {f'{name}/{arm}': paired(current, [run[arm] for run in episodes[name]])
                       for name, controls in (('candidate', tuple(f'{arm}.runner-up' for arm in archive.METHODS[1:])),
                                              ('full-panel', (CPO,)),
                                              ('full-budget', tuple(f'{arm}.base' for arm in continuous.GEPA)))
                       for arm in controls}
        panels[f'{subject}/{model}'] = {'totals': totals, 'comparisons': comparisons,
                                       'episodeTraceSha256': {k: digest(v) for k, v in episodes.items()}}
    matched = [name for name, p in panels.items() if all(p['comparisons'][f'candidate/{arm}.runner-up']['qualified']
                                                         for arm in continuous.GEPA)]
    full = [name for name, p in panels.items() if all(p['comparisons'][f'full-budget/{arm}.base']['qualified']
                                                      for arm in continuous.GEPA)]
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels,
            'passesMatchedGate': len(matched) == len(panels), 'panelsClearingMatchedGate': matched,
            'panelsClearingFullBudgetGate': full}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, original, source = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, original, source)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
