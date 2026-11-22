"""Measure the full subject-tuned GEPA ceiling at deferred CPO's budget."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import pairwise
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_deferred_certificate_gepa_frontier as matched
from cpo._contract import digest


cycle, frontier, native_cost = matched.deferred, matched.frontier, matched.native_cost
SOURCE_REPORT = 'docs/deferred-certificate-gepa-frontier-results-v1.json'
SOURCE_SHA256 = 'c8dd4548189087fdecbfc8a7b43edc647e8361e19cf7fcfb9a5bea02652b4e05'
RETAIN = cycle.RETAIN


def prepare():
    parent, groups, receipt, policies, _ = matched.prepare()
    read = native_cost.prior.baseline.read_reference
    reference = read(SOURCE_REPORT, SOURCE_SHA256, parent)
    _, _, _, native = cycle.prepare()
    by_subject = frontier.transfer.fitted.prior
    paths = (Path(__file__), Path(matched.__file__), Path(native_cost.__file__), Path(frontier.__file__),
             Path(frontier.matched.__file__), Path(by_subject.__file__), Path(by_subject.ceiling.__file__),
             Path(native_cost.adapter.math.gepa.__file__))
    plan = {**parent, 'protocol': 'deferred-certificate-subject-ceiling-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': SOURCE_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'scope': 'Use all native settings, including settings unaffordable across the full cohort, '
                     'when assigning one setting per subject. Match total search and qualification '
                     'lookups to CPO. Share the native search between qualification variants only '
                     'when its inputs and requests match. Reproduce all earlier native totals and '
                     'subject ceilings before calculating the full-roster ceiling.'}
    return plan, groups, receipt, policies, reference['results'], native


def reuse_native_search(optimize):
    """Reuse one deterministic search inside a single recorded trial."""
    transcripts = {}

    def replay(start, roster, training, validation, observe, spent, *, paid_limit, batched, seed):
        identity = start, tuple(roster), tuple(training), tuple(validation), paid_limit, batched, seed
        if identity in transcripts:
            result, events = transcripts[identity]
            for operation, args, expected in events:
                actual = observe(*args) if operation == 'observe' else spent()
                if type(actual) is not type(expected) or actual != expected:
                    raise ValueError('Reused native search must receive identical paid replies and spend')
            return result

        events = []

        def record_observation(prompt, case):
            passed = observe(prompt, case)
            events.append(('observe', (prompt, case), passed))
            return passed

        def record_spend():
            amount = spent()
            events.append(('spent', (), amount))
            return amount

        result = optimize(start, roster, training, validation, record_observation, record_spend,
                          paid_limit=paid_limit, batched=batched, seed=seed)
        transcripts[identity] = result, events
        return result

    return replay


def native_paths(arguments, mode, low, high):
    search = native_cost.adapter.math.gepa
    with patch.object(search, 'optimize_by_paid_reads', reuse_native_search(search.optimize_by_paid_reads)):
        one, two = frontier.matched.native_paths(arguments, mode, low, high)
        with patch.object(native_cost, 'run', frontier.gepa_threshold):
            threshold = native_cost.budget_paths(arguments, mode, low, high)
    return {'gain-1': one, 'gain-2': two, frontier.THRESHOLD: threshold}


def measure_panel(subject, matrix, plan, receipt, policies):
    cells = {str(i): tuple(map(int, row)) for i, row in enumerate(matrix)}
    native_cells = {prompt: tuple((grade, None, False) for grade in row) for prompt, row in cells.items()}
    totals = {label: Counter() for label in (*policies.values(), RETAIN)}
    deltas, audit = {}, Counter()
    paths = {label: [] for label in policies.values()}
    low, high, cap = plan['minimumSearchCap'], plan['searchCap'], plan['fullRosterCap']
    for seed in plan['seeds']:
        start, roster, cohorts = frontier.transfer.archive.transfer.schedule(
            subject, len(matrix[0]), len(matrix), seed, plan,
        )
        totals[RETAIN].update(holdoutPasses=sum(cells[start][case] for case in cohorts[-1]), paidLookups=0)
        for gain, label in policies.items():
            result, paid = cycle.execute_path(cycle.run_deferred_certificate_cycle, cells, start, roster,
                                              cohorts, seed, cap, gain)
            totals[label].update(holdoutPasses=sum(cells[result.prompt][case] for case in cohorts[-1]),
                                 paidLookups=len(paid))
            paths[label].append(digest([(*key, passed) for key, passed in paid.items()]))
        arguments = native_cells, start, roster, cohorts, seed
        for mode in native_cost.MODES:
            wrapped = native_paths(arguments, mode, low, high)
            audit.update({rule: len(replayed) for rule, replayed in wrapped.items()})
            for rule, replayed in wrapped.items():
                changes = deltas.setdefault((mode, rule), {})
                for lower, upper in pairwise((*replayed, high + 1)):
                    point, _, grades = replayed[lower]
                    if (point['searchLookups'] > lower or point['qualificationLookups'] > 2 * len(cohorts[2])
                            or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']
                            or point['holdoutPasses'] != sum(grades)):
                        raise ValueError('A native path left the seal’s search, qualification, or score bounds')
                    changes.setdefault(lower, Counter()).update({key: point[key] for key in native_cost.METRICS})
                    changes.setdefault(upper, Counter()).subtract({key: point[key] for key in native_cost.METRICS})
    if any(digest(path) != receipt[label]['deferred'] for label, path in paths.items()):
        raise ValueError('The full-roster cycle must reproduce every model panel’s recorded callback hashes')
    for (mode, rule), changes in deltas.items():
        current = Counter()
        for cap in range(low, high + 1):
            current.update(changes.get(cap, {}))
            totals[f'{mode}/{cap}/{rule}'] = current.copy()
    return totals, audit


def measure_cohort(panels, plan, receipt, policies, previous, native):
    totals, subjects, audit = {}, {}, Counter()
    for subject, model, matrix in panels:
        name = f'{subject}/{model}'
        panel, checked = measure_panel(subject, matrix, plan, receipt['panelPathHashes'][name], policies)
        audit.update(checked)
        subject_totals = subjects.setdefault(subject, {})
        for label, point in panel.items():
            totals.setdefault(label, Counter()).update(point)
            subject_totals.setdefault(label, Counter()).update(point)
    controls = tuple(label for label in totals if label.startswith('gepa-'))
    expected = {label: point for label, point in native['totals'].items() if label.startswith('gepa-')}
    if {label: totals[label] for label in controls} != expected:
        raise ValueError('Every native GEPA setting must match its published full-cohort cost and score')
    if any(totals[label] != point for label, point in previous['totals'].items()):
        raise ValueError('The previous fixed comparison, retained starts and CPO policies must reproduce')
    by_subject_ceiling = frontier.transfer.fitted.prior.by_subject_ceiling
    anchors = native['subjectTunedGepaHindsight']
    budgets = {label: native['totals'][label]['paidLookups'] for label in anchors}
    if by_subject_ceiling(subjects, controls, budgets) != anchors:
        raise ValueError('The earlier subject budgets must reproduce their exact attaining schedules')
    budgets = {label: totals[label]['paidLookups'] for label in policies.values()}
    ceilings = by_subject_ceiling(subjects, controls, budgets)
    results = {}
    for label, point in ceilings.items():
        choices = point['settingsBySubject']
        contributions = {subject: {'gepaSetting': setting, 'gepa': subjects[subject][setting],
                                   'cpo': subjects[subject][label]}
                         for subject, setting in choices.items()}
        if any(sum(entry['gepa'][key] for entry in contributions.values()) != point[key]
               for key in native_cost.METRICS) or point['paidLookups'] > budgets[label]:
            raise ValueError('The chosen per-subject schedule must attain its ceiling within the CPO budget')
        results[label] = {'cpo': totals[label], 'gepa': point,
                          'holdoutPassDifference': totals[label]['holdoutPasses'] - point['holdoutPasses'],
                          'bySubject': contributions}
    return {'comparisons': results, 'nativeSettings': len(controls), 'wrappedPaths': audit,
            'subjectTotalsSha256': digest(subjects)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, receipts, policies, reference, native = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    results = {name: measure_cohort(panels, plan, receipts[name], policies, reference[name], native[name])
               for name, panels in groups.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
