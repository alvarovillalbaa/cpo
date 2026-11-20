"""Test early coverage rejection on a fixed bank of recorded provider outcomes."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import combinations
import json
from pathlib import Path
from random import Random

from benchmarks import gepa_paid_cap_transfer, recorded_archive_restart as restart, recorded_promotion_strata
from cpo._contract import digest
from cpo.coverage_confirmation import confirm_covered_gain


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_PLAN = '7f98953c09f9eea5ec69fbd0b2b4f09ec635169440411eb266421d54ed9e5d4e'
CAPS = (24, 36)
GEPA = ('gepa-sequential', 'gepa-batched')
PRIMARY = 'coverage-first'
METHODS = ('exact-only', 'late-coverage', PRIMARY, *GEPA)


def prepare():
    import field_validation_replay as source

    parent, data, _ = restart.prepare()
    if digest(parent) != ARCHIVE_PLAN:
        raise ValueError('Recorded archive differs from its frozen plan')
    paths = (Path(__file__), ROOT / 'cpo/coverage_confirmation.py',
             ROOT / 'benchmarks/gepa_paid_cap_transfer.py', ROOT / 'benchmarks/recorded_promotion_strata.py',
             ROOT / 'cpo/challenger.py', ROOT / 'benchmarks/prompteval_transfer.py')
    tasks = {}
    for task, ((root, rows, matrix, provider, _), graph, initial, _) in data.items():
        pool = sorted((restart.reachable(graph, root) & matrix.keys()) - {initial})
        strata = {key: recorded_promotion_strata.risk_stratum(task, row)
                  for key, row in rows.items() if row['critical']}
        cases = json.loads((source.ARCHIVE / f'{task}-strict-plan.json').read_bytes())['datasets']['holdout']
        external = {row['id']: row['critical'] for row in cases}
        if external.keys() & rows.keys() or any(values.keys() != external.keys() for values in provider.values()):
            raise ValueError('Provider holdout must be separate and complete for each archived prompt')
        if any(matrix[prompt].keys() != rows.keys() for prompt in (initial, *pool)):
            raise ValueError('The fixed pool requires a complete recorded development matrix')
        tasks[task] = (rows, matrix, provider, initial, pool, strata, external)
    plan = {
        'protocol': 'cpo-recorded-coverage-confirmation-v1', 'gepaVersion': parent['gepaVersion'],
        'archivePlanSha256': ARCHIVE_PLAN, 'sourcePlanSha256': parent['sourcePlanSha256'],
        'sourceSha256': {str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest() for path in paths},
        'methods': METHODS, 'primary': PRIMARY, 'caps': CAPS, 'cohortSizes': [3, 4, 2, 3],
        'holdoutOrder': 'Every three-case combination with one seeded assignment of the other nine cases.',
        'seedStart': 84631, 'seedStride': 73, 'gate': {'maxCriticalLosses': 0, 'savingsPercentIfTied': 10},
        'gepaMetric': 'Exact pass plus field credit on failures below one full pass per complete panel.',
        'poolSize': {task: len(values[4]) + 1 for task, values in tasks.items()},
        'taskSha256': {task: digest(values) for task, values in tasks.items()},
    }
    return plan, tasks


def race(initial, roster, validation, strata, evaluate, spent, *, cap, method):
    baseline = {case: evaluate(initial, case)[0] for case in validation}
    protected = {case for case in strata if baseline[case]}
    score, winner, offered = sum(baseline.values()), initial, 0
    groups = set(strata.values())
    for candidate in roster:
        if score == len(validation) or spent() + len(validation) > cap:
            break
        observed = {}

        def read(case):
            observed[case] = evaluate(candidate, case)[0]
            return observed[case]

        offered += 1
        measured = confirm_covered_gain(baseline, score, protected, strata if method == PRIMARY else {}, {}, read)
        if measured is None:
            continue
        if method == 'late-coverage' and {group for case, group in strata.items() if observed[case]} != groups:
            continue
        winner, score = candidate, measured
    return winner, offered


def compare(data, held, seed, cap):
    metadata, matrix, _, initial, pool, risk, _ = data
    generator = Random(seed)
    cases = sorted(metadata.keys() - set(held))
    generator.shuffle(cases)
    train, validation, qualification = cases[:3], cases[3:7], cases[7:]
    roster = generator.sample(pool, len(pool))
    strata = {case: risk[case] for case in validation if case in risk}
    allowed = set(train + validation)
    prompts = {initial, *roster}
    arms = {}
    for method in METHODS:
        journal = {}

        def evaluate(prompt, case):
            if prompt not in prompts or case not in allowed:
                raise ValueError('Search accessed evidence outside the fixed pool or search cohorts')
            key = prompt, case
            if key not in journal:
                if len(journal) == cap:
                    raise ValueError('Search exceeded its paid lookup cap')
                journal[key] = matrix[prompt][case]
            return journal[key]

        if method in GEPA:
            def metric(prompt, case):
                passed, fields = evaluate(prompt, case)
                return 1.0 if passed else fields / ((len(metadata[case]['expected']) + 1) * (len(metadata) + 1))

            nominee, offered = gepa_paid_cap_transfer.optimize_by_paid_reads(
                initial, roster, train, validation, metric, lambda: len(journal), paid_limit=cap,
                batched=method == 'gepa-batched', seed=seed,
            )
        else:
            nominee, offered = race(initial, roster, validation, strata, evaluate, lambda: len(journal),
                                    cap=cap, method=method)
        selected, _, cost, _ = restart.qualify(initial, nominee, metadata, matrix, qualification)
        arms[method] = {'prompt': selected, 'nominee': nominee, 'offered': offered, 'search': len(journal),
                        'qualification': cost, 'total': len(journal) + cost,
                        'outcomes': {case: matrix[selected][case][0] for case in held}}
    return arms, validation, qualification


def summarize(data, cap, schedule, plan):
    metadata, _, provider, initial, _, risk, external = data
    totals = {method: Counter(passes=0, search=0, qualification=0, total=0, offered=0, selectedNew=0)
              for method in METHODS}
    controls = {
        method: Counter(passDelta=0, lookupsSaved=0, criticalLosses=0, nomineeChanges=0,
                        lossesOutsideValidationStrata=0, lossesOutsideQualificationStrata=0)
        for method in METHODS if method != PRIMARY
    }
    pairs = {method: set() for method in controls}
    traces = []
    for index, held in enumerate(schedule):
        arms, validation, qualification = compare(data, held, plan['seedStart'] + index * plan['seedStride'], cap)
        validation_strata = {risk[key] for key in validation if key in risk}
        qualification_strata = {risk[key] for key in qualification if key in risk}
        traces.append(arms)
        for method, arm in arms.items():
            totals[method].update(passes=sum(arm['outcomes'].values()), selectedNew=int(arm['prompt'] != initial),
                                  **{key: arm[key] for key in ('search', 'qualification', 'total', 'offered')})
        current = arms[PRIMARY]
        for method, counts in controls.items():
            other = arms[method]
            if current['prompt'] != other['prompt']:
                pairs[method].add((current['prompt'], other['prompt']))
            losses = [key for key in held if metadata[key]['critical']
                      and other['outcomes'][key] and not current['outcomes'][key]]
            counts.update(passDelta=sum(current['outcomes'].values()) - sum(other['outcomes'].values()),
                          lookupsSaved=other['total'] - current['total'],
                          criticalLosses=len(losses),
                          lossesOutsideValidationStrata=sum(risk[key] not in validation_strata for key in losses),
                          lossesOutsideQualificationStrata=sum(risk[key] not in qualification_strata for key in losses),
                          nomineeChanges=int(current['nominee'] != other['nominee']))
    for method, counts in controls.items():
        complete = [(provider[a], provider[b]) for a, b in pairs[method] if a in provider and b in provider]
        counts.update(distinctProviderPairs=len(pairs[method]), completeProviderPairs=len(complete),
                      observedProviderPassDelta=sum(sum(panel[key][0] - ref[key][0] for key in external)
                                                    for panel, ref in complete),
                      observedProviderCriticalLosses=sum(critical and ref[key][0] and not panel[key][0]
                                                         for panel, ref in complete for key, critical in external.items()))
        gain, savings = counts['passDelta'], counts['lookupsSaved']
        gate = plan['gate']
        saves_on_tie = gain == 0 and 100 * savings >= gate['savingsPercentIfTied'] * totals[method]['total']
        counts['clearedReplayGate'] = counts['criticalLosses'] <= gate['maxCriticalLosses'] and (
            gain > 0 and savings >= 0 or saves_on_tie
        )
    return {'splits': len(schedule), 'totals': totals, 'comparisons': controls, 'tracesSha256': digest(traces)}


def run(plan, tasks):
    results = {}
    for name, data in tasks.items():
        schedule = list(combinations(sorted(data[0]), 3))
        results[name] = {str(cap): summarize(data, cap, schedule, plan) for cap in plan['caps']}
    return {'plan': plan, 'planSha256': digest(plan), 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, tasks = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = run(plan, tasks)
    with args.out.open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
