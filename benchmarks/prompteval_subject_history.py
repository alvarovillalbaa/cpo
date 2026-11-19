"""Compare same-model ranking from disjoint source subjects with cold search."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import pool, prompteval_proxy as proxy, prompteval_transfer as transfer
from benchmarks import prompteval_witnesses as witnesses
from cpo import Observation, Row, select_pool
from cpo._contract import digest


PROFILE_SEED = 61211
SOURCE_DEPTHS = (4, 8)
PRIMARY = 'cpo-source-four'
COLD = ('cpo-minibatch', 'gepa-sequential', 'gepa-batched')
REFERENCES = ('cpo-seeded-two', 'cpo-target-two', *COLD, 'gepa-sequential-source', 'gepa-batched-source')
SOURCE_ARMS = {PRIMARY: 4, 'cpo-source-eight': 8, 'cpo-source-rerank': 4,
               'gepa-sequential-source': 4, 'gepa-batched-source': 4}


def prepare(phase):
    historical, source_sizes, source_hash = transfer.read_source()
    target, target_sizes, target_hash = (witnesses.read_source('confirmation') if phase == 'development'
                                        else proxy.read_source())
    if set(source_sizes).intersection(target_sizes) or historical['observedRepoRevision'] != target['observedRepoRevision']:
        raise ValueError('Source and target subjects must differ and share the same template dataset revision')
    base = transfer.plan(target, target_sizes, target_hash)
    source_cases = {}
    for subject, count in source_sizes.items():
        excluded = set(transfer.holdout(subject, count))
        permitted = [case for case in range(count) if case not in excluded]
        source_cases[subject] = Random(f'{PROFILE_SEED}:{subject}').sample(permitted, max(SOURCE_DEPTHS))
    root = Path(__file__).resolve().parents[1]
    source_hashes = {Path(mod.__file__).relative_to(root).as_posix(): sha256(Path(mod.__file__).read_bytes()).hexdigest()
                     for mod in (proxy, witnesses)}
    source_hashes[Path(__file__).relative_to(root).as_posix()] = sha256(Path(__file__).read_bytes()).hexdigest()
    plan = {**base, 'protocol': 'prompteval-disjoint-subject-history-v1', 'phase': phase,
            'subjects': list(target_sizes), 'historicalCorpusSha256': source_hash, 'historyCases': source_cases,
            'sourceDepths': list(SOURCE_DEPTHS), 'primary': PRIMARY, 'controls': list(REFERENCES),
            'arms': [*REFERENCES, *(arm for arm in SOURCE_ARMS if arm not in REFERENCES)],
            'challengeWidth': 2, 'rerankWidth': 4,
            'accounting': 'Source profiles are charged once per model and equally across its target subjects',
            'sourceSha256': {**base['sourceSha256'], **source_hashes}}
    return plan, historical, target


def make_profiles(history, cases, models):
    profiles = {}
    for model in models:
        panels = [panel for panel in history['panels'] if panel['model'] == model]
        if {panel['subject'] for panel in panels} != cases.keys():
            raise ValueError('Every model needs the full source profile')
        profiles[model] = {}
        for depth in SOURCE_DEPTHS:
            observations = [(panel['subject'], str(template), case, vector[case] == '1')
                            for panel in panels for template, vector in enumerate(panel['correctness'])
                            for case in cases[panel['subject']][:depth]]
            totals = dict.fromkeys((prompt for _, prompt, _, _ in observations), 0)
            for _, prompt, _, passed in observations:
                totals[prompt] += passed
            profiles[model][depth] = {'scores': totals, 'evaluations': len(observations),
                                      'sourceSha256': digest(observations)}
    return profiles


def evaluate(arm, profile, matrix, trial, holdout, plan):
    candidates, train, validation = (trial[name] for name in ('candidates', 'train', 'validation'))
    permitted = set(train + validation)
    if permitted.intersection(holdout) or set(train).intersection(validation):
        raise ValueError('Target training, validation, and holdout must be separate')
    observed = {}

    def observe(prompt, row):
        if prompt not in candidates or row not in permitted:
            raise ValueError('Lookup left its sealed candidate or case pool')
        key = prompt, row
        if key not in observed:
            if len(observed) >= plan['evaluationLookupLimit']:
                raise ValueError('A split exceeded its target lookup cap')
            observed[key] = matrix[int(prompt)][row] == '1'
        return observed[key]

    incumbent, *ranked = candidates
    if profile is not None:
        ranked.sort(key=profile['scores'].__getitem__, reverse=True)
    if arm.startswith('gepa-'):
        prompt = transfer.optimize_gepa(incumbent, ranked, train, validation, observe,
                                        batched=arm.startswith('gepa-batched'), seed=trial['seed'])
    else:
        if arm == 'cpo-source-rerank':
            ranked = ranked[:plan['rerankWidth']]
        if arm in ('cpo-target-two', 'cpo-source-rerank'):
            ranked.sort(key=lambda prompt: sum(observe(prompt, case) for case in train[:plan['probeSize']]),
                        reverse=True)
        selection = select_pool([incumbent, *ranked[:plan['challengeWidth']]],
                                [Row(str(row), 'task') for row in validation],
                                lambda prompt, row: Observation(observe(prompt, int(row.id)), {}),
                                metric_limit=plan['evaluationLookupLimit']-len(observed), adaptive_rejection=True)
        prompt = selection.prompt
        if not all((prompt, case) in observed for case in validation):
            raise ValueError('CPO selected a prompt without a complete target validation')
    return {'candidate': prompt, 'evaluations': len(observed),
            'searchSha256': digest([(prompt, row, passed) for (prompt, row), passed in observed.items()]),
            'holdoutPasses': sum(matrix[int(prompt)][row] == '1' for row in holdout)}


def charged_comparison(totals, arm, reference):
    a, b = totals[arm], totals[reference]
    cost, baseline = (item['evaluations'] + item['allocatedSourceLookups'] for item in (a, b))
    gap = a['holdoutPasses'] - b['holdoutPasses']
    return {'passDelta': gap, 'chargedLookupDelta': cost-baseline,
            'qualified': gap >= 0 and cost <= baseline and (gap > 0 or 10 * cost <= 9 * baseline)}


def execute(plan, history, target):
    if plan['gepaVersion'] != version('gepa'):
        raise ValueError('Use the pinned GEPA version')
    profiles = make_profiles(history, plan['historyCases'], plan['models'])
    panels = {}
    for panel in target['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        holdout = plan['holdoutCaseIDs'][subject]
        trials = []
        for seed in plan['seeds']:
            trial = transfer.compare(matrix, holdout, seed)
            trial['arms'] = {arm: trial['arms'][arm] for arm in COLD}
            for arm in plan['arms']:
                if arm not in COLD:
                    trial['arms'][arm] = evaluate(arm, profiles[model].get(SOURCE_ARMS.get(arm)),
                                                  matrix, trial, holdout, plan)
            trials.append(trial)
        totals, _ = pool.summarize(trials, PRIMARY, REFERENCES)
        for arm, total in totals.items():
            source_cost = profiles[model][SOURCE_ARMS[arm]]['evaluations'] if arm in SOURCE_ARMS else 0
            per_panel, remainder = divmod(source_cost, len(plan['subjects']))
            # Attribute all lookups exactly once, including any indivisible remainder.
            total['allocatedSourceLookups'] = per_panel + int(plan['subjects'].index(subject) < remainder)
        comparisons = {arm: {ref: charged_comparison(totals, arm, ref) for ref in REFERENCES}
                       for arm in SOURCE_ARMS if arm not in REFERENCES}
        panels[f'{subject}/{model}'] = {'totals': totals, 'comparisons': comparisons, 'trials': trials}
    return {'plan': plan, 'planSha256': digest(plan), 'sourceProfiles': profiles, 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('development', 'retrospective-transfer'), required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, history, target = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    report = execute(plan, history, target)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
