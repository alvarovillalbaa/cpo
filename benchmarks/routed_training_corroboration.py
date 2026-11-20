"""Transfer the AIME training check to archived MMLU starting-prompt departures."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_margin_corroboration as margin
from benchmarks import recorded_training_corroboration as training
from benchmarks import routed_validation_ties as ties
from cpo import Observation, Row
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
CONFIRMATION = ties.confirmation
MATH_SHA256 = '49d5266bfb32213c65b2f069676b3c394a2562df83a574702d55a861b1f337ad'
TIES_SHA256 = '783dafd77b24c294b4f63581be795a731331ce824b53af5a3508bbc60fc20c07'
POLICIES = ('training-only', 'strength-only', 'strength-first')
METHODS = ('strict', *POLICIES)
PRIMARY = CONFIRMATION.PRIMARY
PANEL_SIZE = 5


def reserve_panel(case_count, held, layouts, seed):
    """Fix one training panel outside every validation and qualification cohort."""
    reserved = set(held)
    reserved.update(case for layout in layouts for role in ('validation', 'qualify') for case in layout[role])
    original_train = {case for layout in layouts for case in layout['train']} - reserved
    rng = Random(f'mmlu-training-proof/{seed}')
    training = sorted(original_train)
    extra = sorted(set(range(case_count)) - reserved - original_train)
    rng.shuffle(training)
    rng.shuffle(extra)
    panel = (training + extra)[:PANEL_SIZE]
    if len(panel) != PANEL_SIZE:
        raise ValueError('Every episode requires a disjoint five-case panel')
    return tuple(panel)


def run(matrix, held, seed, plan, start, method):
    if method == 'strict':
        return ties.run(matrix, held, seed, plan, start, 'strict')
    baseline = ties.prior
    archive = baseline.archive
    scheduled, layouts = archive.smaller.narrow_schedule(
        *archive.continuous.schedule(len(matrix[0]), len(matrix), held, seed, plan['schedule']), plan['validationRows'])
    if scheduled != start:
        raise ValueError('Training evidence does not share the published start schedule')
    panel = reserve_panel(len(matrix[0]), held, layouts, seed)
    rows = tuple(Row(str(case), 'training') for case in panel)
    original = ties.split.routed_selection
    audit, receipts = Counter(), {}
    search_room = 0

    def select(*args, metric_limit, **kwargs):
        nonlocal search_room
        choice = original(*args, metric_limit=metric_limit, **kwargs)
        search_room = metric_limit - choice.evaluations
        return choice

    def qualify(incumbent, challenger, qual_rows, evaluate, *, repeats, minimum_gain, seed, evaluation_limit):
        if any((repeats != 1, minimum_gain != 1, evaluation_limit is not None)):
            raise ValueError('The margin transfer requires the frozen qualification budget and threshold')
        # Apply the extra proof at most once, after a fresh start challenger qualifies.
        applies = incumbent == start and not audit['initialPromotions'] and search_room >= 2 * len(rows)
        if not applies:
            return margin.certify_paired_qualification(incumbent, challenger, qual_rows, evaluate, seed=seed)

        def observe(prompt, row):
            key = (prompt, row.id)
            if prompt not in (incumbent, challenger) or row.id not in allowed or key in receipts:
                raise ValueError('The training proof repeated a read or left its reserved cases')
            reply = receipts[key] = matrix[int(prompt)][int(row.id)] == '1'
            return Observation(reply, {})

        def corroborate():
            supported = training.corroborate(incumbent, challenger, rows, observe, minimum_gain=1,
                                              remaining=search_room, seed=seed)
            audit.update(trainingChecks=1, trainingProved=int(supported))
            return supported

        return margin.qualify_with_support(incumbent, challenger, qual_rows, evaluate, corroborate, seed=seed,
                                           policy=method, audit=audit)

    allowed = {row.id for row in rows}
    with (patch.object(ties.split, 'routed_selection', select),
          patch.object(baseline, 'certify_paired_qualification', qualify)):
        totals, trace = ties.run(matrix, held, seed, plan, start, 'strict')
    if len(receipts) > 2 * len(rows) or audit['trainingChecks'] > 1 or audit['initialPromotions'] > 1:
        raise ValueError('A second challenger attempted to use the reserved panel')
    totals.update(searchLogical=len(receipts), searchPaid=len(receipts), trainingPaid=len(receipts))
    totals.update(audit)
    return totals, {'cycles': trace, 'trainingPanel': panel,
                    'paidTraining': [(prompt, case, value) for (prompt, case), value in receipts.items()]}


def prepare():
    reference, panels, strict, comparisons = ties.prepare('confirmation')
    math_report = (ROOT / 'docs/recorded-margin-corroboration-results-v1.json').read_bytes()
    ties_report = (ROOT / 'docs/routed-validation-ties-results-v1.json').read_bytes()
    if sha256(math_report).hexdigest() != MATH_SHA256 or sha256(ties_report).hexdigest() != TIES_SHA256:
        raise ValueError('The source evidence no longer agrees with its recorded digests')
    previous = json.loads(ties_report)['confirmation']
    if previous['planSha256'] != digest(reference):
        raise ValueError('The routed confirmation plan differs')
    paths = ('benchmarks/routed_training_corroboration.py', 'benchmarks/recorded_margin_corroboration.py',
             'benchmarks/recorded_training_corroboration.py', 'benchmarks/archive_complementarity_transfer.py',
             'benchmarks/routed_witness_split.py', 'cpo/fixed_pool_cycle.py', *reference['sourceSha256'])
    plan = {**{key: reference[key] for key in ('schedule', 'validationRows', 'searchCap', 'gepaVersion')},
            'protocol': 'cpo-routed-training-corroboration-v1', 'methods': METHODS, 'primary': 'training-only',
            'controls': PRIMARY, 'panelSize': PANEL_SIZE, 'minimumLookupSavingPercent': 10,
            'bootstrap': {k: reference['caseSensitivity'][k] for k in ('draws', 'seed')},
            'parentPlanSha256': digest(reference), 'parentReportSha256': TIES_SHA256, 'mathReportSha256': MATH_SHA256,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'scope': ('Qualify only the first fresh starting-prompt departure with the supplemental proof, '
                      'using disjoint cases and funded search capacity. Preserve archive qualification and GEPA controls.')}
    return plan, panels, strict, comparisons


def ranges(subjects, draws, seed):
    rng = Random(seed)
    labels = tuple(next(iter(subjects.values())))
    values = {key: [] for key in (*labels, 'joint')}
    for _ in range(draws):
        margins = Counter()
        for subject in sorted(subjects):
            panel = subjects[subject]
            count = len(panel[labels[0]])
            cases = rng.choices(range(count), k=count)
            margins.update({label: sum(vector[case] for case in cases) for label, vector in panel.items()})
        margins['joint'] = min(margins[label] for label in PRIMARY)
        for label, samples in values.items():
            samples.append(margins[label])
    return {label: ties.interval(samples) for label, samples in values.items()}


def replay(plan, panels, strict, references):
    results, totals = {}, {m: Counter() for m in (*METHODS, *PRIMARY, 'retain-start')}
    subjects = {m: {} for m in POLICIES}
    for panel in panels:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = CONFIRMATION.holdout(subject, len(matrix[0]))
        starts = ties.costs.retained_prompts(matrix, held, plan['schedule'])
        counts, logs, finals = ({m: factory() for m in METHODS} for factory in (Counter, list, list))
        for seed, start in zip(plan['schedule']['seeds'], starts, strict=True):
            for method in METHODS:
                count, log = run(matrix, held, seed, plan, str(start), method)
                counts[method].update(count)
                logs[method].append(log)
                cycles = log if method == 'strict' else log['cycles']
                finals[method].append(int(cycles[-1]['decision']['selected']))
        points = {m: {**count, 'paidLookups': count['searchPaid'] + count['qualificationPaid'],
                      'traceSha256': digest(logs[m])} for m, count in counts.items()}
        ties.frontier.expect_reference(points['strict'], strict[name])
        for label in PRIMARY:
            mode, cap = label.split('/')
            finals[label], points[label] = CONFIRMATION.uncertainty.final_prompts(
                matrix, held, plan['schedule'], plan, mode, int(cap))
            ties.frontier.expect_reference(points[label], references[name][label])
        finals['retain-start'] = starts
        outcomes = {m: CONFIRMATION.uncertainty.case_totals(matrix, held, prompts) for m, prompts in finals.items()}
        points['retain-start'] = {'holdoutPasses': sum(outcomes['retain-start'].values()), 'paidLookups': 0}
        if any(sum(outcomes[m].values()) != row['holdoutPasses'] for m, row in points.items()):
            raise ValueError('The holdout vectors differ from the recorded performance')
        for m, point in points.items():
            totals[m].update({k: v for k, v in point.items() if type(v) is int})
        for candidate, groups in subjects.items():
            controls = tuple(m for m in points if m != candidate)
            vectors = groups.setdefault(subject, {m: [0] * len(held) for m in controls})
            for label, values in vectors.items():
                for i, case in enumerate(held):
                    values[i] += outcomes[candidate][case] - outcomes[label][case]
        results[name] = points
    comparisons = {}
    for candidate, groups in subjects.items():
        paired = ranges(groups, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
        savings = {m: 1 - totals[candidate]['paidLookups'] / totals[m]['paidLookups'] for m in PRIMARY}
        cost_percent = 100 - plan['minimumLookupSavingPercent']
        supported = all(100 * totals[candidate]['paidLookups'] <= cost_percent * totals[m]['paidLookups'] for m in PRIMARY)
        lower, upper = paired['joint']
        gate = 'failed' if not supported or upper < 0 else 'passed' if lower >= 0 else 'inconclusive'
        comparisons[candidate] = {'caseSensitivityRanges': paired, 'lookupSavingFractions': savings, 'gate': gate}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': results, 'totals': totals, 'comparisons': comparisons}


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
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, *inputs)
    with args.out.open('x') as stream:
        json.dump(result, stream, sort_keys=True, separators=(',', ':'))
        stream.write('\n')


if __name__ == '__main__':
    main()
