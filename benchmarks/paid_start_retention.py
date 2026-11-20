"""Test retaining the starting prompt using paired evidence already bought in an episode."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import case_difficulty_allocation as parent
from benchmarks import priced_gate_reachability as audit
from benchmarks import routed_score_allocation as route
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
AUDIT_REPORT = 'e32701bf2885ce910e871c2888b2ec06f2e044b5afcb5309ec704ef637d42b51'
METHODS = ('matched-pooled', 'qualification-corroborated')
CONTROLS = audit.CONTROLS
MIN_PAIRS = 4
MIN_NET_GAIN = 2


def paired_counts(start, final, ledger):
    left, right = (ledger.get(prompt, {}) for prompt in (start, final))
    matched = left.keys() & right.keys()
    return len(matched), sum(left[case] - right[case] for case in matched)


def retention(start, final, validation, qualification):
    val_pairs, val_gain = paired_counts(start, final, validation)
    qual_pairs, qual_gain = paired_counts(start, final, qualification)
    pooled = start != final and val_pairs + qual_pairs >= MIN_PAIRS and val_gain + qual_gain >= MIN_NET_GAIN
    corroborated = pooled and qual_gain > 0
    evidence = {'validationPairs': val_pairs, 'validationGainForStart': val_gain,
                'qualificationPairs': qual_pairs, 'qualificationGainForStart': qual_gain}
    return {METHODS[0]: start if pooled else final, METHODS[1]: start if corroborated else final}, evidence


def record(ledger, prompt, case, passed):
    if type(passed) is not bool:
        raise ValueError('This replay requires exact binary outcomes')
    if ledger.setdefault(prompt, {}).setdefault(int(case), passed) != passed:
        raise ValueError('Repeated deterministic evaluations must agree')


def captured_episode(matrix, held, seed, plan, start):
    split = route.ties.split
    episode = split.run
    cycle = split.fixed_pool_cycle
    archive = split.archive.archive
    validation, qualification = {}, {}

    def capture(*args):
        original_cycle, original_archive = cycle.run_fixed_pool_cycle, archive.qualify_archived

        def fresh(incumbent, candidates, rows, cohort, evaluate, *, qualify, **kwargs):
            def validate(prompt, row):
                reply = evaluate(prompt, row)
                record(validation, prompt, row.id, reply.passed)
                return reply

            def assess(prompt, row, repeat):
                if repeat != 0 or row.critical:
                    raise ValueError('The captured qualification expects unflagged, scalar rows and one repeat')
                passed = qualify(prompt, row, repeat)
                record(qualification, prompt, row.id, passed)
                return passed

            return original_cycle(incumbent, candidates, rows, cohort, validate, qualify=assess, **kwargs)

        def archived(incumbent, challenger, cohort, evaluate):
            def assess(prompt, case):
                passed = evaluate(prompt, case)
                record(qualification, prompt, case, passed)
                return passed

            return original_archive(incumbent, challenger, cohort, assess)

        with patch.object(cycle, 'run_fixed_pool_cycle', fresh), patch.object(archive, 'qualify_archived', archived):
            return episode(*args)

    with patch.object(split, 'run', capture):
        counts, trace = route.run(matrix, held, seed, plan, start, 'strict')
    validation_ids = {case for rows in validation.values() for case in rows}
    qualification_ids = {case for rows in qualification.values() for case in rows}
    if (set(held) & (validation_ids | qualification_ids) or validation_ids & qualification_ids
            or sum(map(len, validation.values())) != counts['searchPaid']
            or sum(map(len, qualification.values())) != counts['qualificationPaid']):
        raise ValueError('The captured evidence must be disjoint and match paid lookup counts')
    return counts, trace, validation, qualification


def prepare():
    previous, inputs = parent.prepare()
    audited = parent.checked_file('docs/priced-gate-reachability-results-v1.json', AUDIT_REPORT)
    paths = ('benchmarks/paid_start_retention.py', 'benchmarks/archive_complementarity_transfer.py',
             'benchmarks/routed_start_protection.py', 'benchmarks/routed_witness_split.py', 'cpo/fixed_pool_cycle.py')
    design = {'protocol': 'cpo-paid-start-retention-v1', 'parentDesignSha256': digest(previous),
              'pricedAuditReportSha256': AUDIT_REPORT, 'minimumMatchedPairs': MIN_PAIRS,
              'minimumNetGainForStart': MIN_NET_GAIN, 'policies': METHODS, 'controls': CONTROLS,
              'scope': ('Roll back to the start only if already paid, same-case evidence supports it. '
                        'Buy no new lookups and preserve all search and qualification decisions. '
                        'The corroborated arm also needs positive paired qualification evidence.'),
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}}
    return design, {name: (*item, audited['results'][name]['panels']) for name, item in inputs.items()}


def measure(panels, references, plan, audited):
    labels = (*CONTROLS, *METHODS)
    totals = {label: Counter() for label in labels}
    results, vectors, holdouts = {}, {label: {} for label in METHODS}, {}
    for panel in panels:
        subject, model, matrix = (panel[field] for field in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = route.CONFIRMATION.holdout(subject, len(matrix[0]))
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('Both model splits must share the holdout cases')
        starts = route.ties.costs.retained_prompts(matrix, held, plan['schedule'])
        uncertainty = route.CONFIRMATION.uncertainty
        finals, points = {label: [] for label in labels}, {}
        for label in route.PRIMARY:
            mode, cap = label.split('/')
            finals[label], points[label] = uncertainty.final_prompts(matrix, held, plan['schedule'], plan, mode, int(cap))

        counts, metrics, logs, diagnostics = Counter(), {m: Counter() for m in METHODS}, [], []
        for index, (seed, start) in enumerate(zip(plan['schedule']['seeds'], starts, strict=True)):
            used, trace, validation, qualification = captured_episode(matrix, held, seed, plan, str(start))
            counts.update(used)
            logs.append(trace)
            final = trace[-1]['decision']['selected']
            selected, evidence = retention(str(start), final, validation, qualification)
            finals['strict'].append(int(final))
            previous = audited[name]['episodes'][index]
            if previous['seed'] != seed or previous['cpoPaidLookups'] != used['searchPaid'] + used['qualificationPaid']:
                raise ValueError('The measured CPO episode differs from the priced audit')
            start_score = sum(matrix[start][case] == '1' for case in held)
            for label, choice in selected.items():
                finals[label].append(int(choice))
                rolled_back = choice != final
                gain = start_score - used['holdoutPasses'] if rolled_back else 0
                metrics[label].update(rollbacks=int(rolled_back), episodesGained=int(gain > 0),
                                      episodesLost=int(gain < 0), grossGains=max(gain, 0), grossLosses=max(-gain, 0),
                                      matchedStartRecoveries=sum(rolled_back and bound == audit.RETAIN_START
                                                                 for bound in previous['firstBound'].values()))
            if int(final) != start:
                diagnostics.append({'seed': seed, **evidence,
                                    'rollbackArms': [label for label, prompt in selected.items() if prompt != final]})

        paid = counts['searchPaid'] + counts['qualificationPaid']
        points['strict'] = {'holdoutPasses': counts['holdoutPasses'], 'paidLookups': paid, 'traceSha256': digest(logs)}
        for label in CONTROLS:
            route.ties.frontier.expect_reference(points[label], references[name][label])
        outcomes = {label: uncertainty.case_totals(matrix, held, values) for label, values in finals.items()}
        for label in METHODS:
            points[label] = {'holdoutPasses': sum(outcomes[label].values()), 'paidLookups': paid,
                             'choicesSha256': digest(finals[label]), **metrics[label]}
            paired = vectors[label].setdefault(subject, {control: [0] * len(held) for control in CONTROLS})
            for control, margins in paired.items():
                for i, case in enumerate(held):
                    margins[i] += outcomes[label][case] - outcomes[control][case]
        for label, point in points.items():
            totals[label].update({key: value for key, value in point.items() if type(value) is int})
        results[name] = {'methods': points, 'departedStart': diagnostics}

    comparisons = {}
    for label, summaries in vectors.items():
        ranges = route.transfer.ranges(summaries, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
        paid = totals[label]['paidLookups']
        savings = {control: 1 - paid / totals[control]['paidLookups'] for control in route.PRIMARY}
        limit = 100 - plan['minimumLookupSavingPercent']
        enough = all(100 * paid <= limit * totals[control]['paidLookups'] for control in route.PRIMARY)
        low, high = ranges['joint']
        gate = 'failed' if not enough or high < 0 else 'passed' if low >= 0 else 'inconclusive'
        comparisons[label] = {'gate': gate, 'lookupSavings': savings, 'pairedRanges': ranges}
    return {'totals': totals, 'comparisons': comparisons, 'panels': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    design, inputs = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for _, _, plan, _ in inputs.values()):
        parser.error('Use pinned GEPA 0.1.4')
    results = {cohort: measure(*item) for cohort, item in inputs.items()}
    with args.out.open('x') as stream:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, stream, sort_keys=True,
                  separators=(',', ':'))
        stream.write('\n')


if __name__ == '__main__':
    main()
