"""Compare threshold-prechecked CPO with equally prechecked GEPA."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import pairwise
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_paid_qualification_margin_route as anchors
from benchmarks import threshold_prechecked_cycle_replay as replay
from cpo import Observation, Row
from cpo._contract import digest
from cpo.threshold_prechecked_cycle import run_threshold_prechecked_cycle


matched, prior, cost, frontier = anchors.matched, anchors.prior, anchors.cost, anchors.frontier
transfer = prior.transfer.fixed
RECEIPT = 'docs/threshold-prechecked-cycle-replay-results-v1.json'
RECEIPT_SHA256 = 'a24018a237cb8ffec3341a3cbba52a62db0068710d836885565c3f19fea21c02'
POLICIES = {1: anchors.ONE, 2: anchors.TWO}
THRESHOLD = 'gain-2-threshold-precheck'


def prepare():
    parent, groups, _ = replay.prepare()
    schedule, _, reference = anchors.prepare()
    receipt = cost.prior.baseline.read_reference(RECEIPT, RECEIPT_SHA256, parent)
    pinned = (cost.transfer.ROOT / 'requirements-benchmark.txt').read_text().strip()
    sources = (Path(__file__), Path(cost.__file__), Path(cost.adapter.__file__),
               Path(matched.__file__), Path(prior.__file__), Path(frontier.__file__),
               Path(cost.adapter.math.__file__), Path(cost.adapter.backup.__file__),
               Path(cost.adapter.math.gepa.__file__), Path(transfer.fitted.prior.__file__))
    plan = {**parent, 'protocol': 'threshold-precheck-gepa-frontier-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': RECEIPT_SHA256,
            'referencePlanSha256': digest(schedule),
            'referenceReceiptSha256': (schedule['mmluReceiptSha256'], schedule['languageReceiptSha256']),
            'minimumSearchCap': schedule['minimumSearchCap'], 'searchCap': schedule['searchCap'],
            'bootstrapSeed': schedule['bootstrapSeed'], 'bootstrapDraws': schedule['bootstrapDraws'],
            'gepaVersion': schedule['gepaVersion'], 'pinnedWheel': pinned,
            'gepaModes': cost.MODES, 'gepaProofRules': ('gain-1', 'gain-2', THRESHOLD),
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in sources},
            'scope': 'Give both GEPA modes the same threshold precheck. Preserve the frozen cohorts and '
                     'all old native controls. Compare at each CPO arm’s realized budget, reselecting '
                     'the strongest affordable common setting or retained starts on every case draw. '
                     'Also report the subject-tuned GEPA hindsight ceiling.'}
    return plan, groups, reference, receipt['results']


def gepa_threshold(arguments, mode, cap):
    cells, start, roster, (train, validation, qualification, held), seed = arguments
    rows = tuple(Row(str(case), 'qualification') for case in qualification)
    proof, search, prefix = {}, {}, {}

    def qualify(prompt, row, repeat):
        key = prompt, row.id
        if repeat or key in proof or row not in rows or prompt not in (start, nominee):
            raise ValueError('Each qualification reply must be independent and paid once')
        proof[key] = bool(cells[prompt][int(row.id)][0])
        return proof[key]

    def observe(prompt, case):
        if prompt not in (start, *roster) or case not in (*train, *validation):
            raise ValueError('Native search left its prompt or case roster')
        key = prompt, case
        if key not in search:
            if len(search) >= cap:
                raise ValueError('Native search exceeded its paid cap')
            search[key] = bool(cells[prompt][case][0])
        return search[key]

    nominee = deployed = start
    misses, upper = 0, len(rows)
    for row in rows:
        passed = qualify(start, row, 0)
        prefix[row.id] = passed
        upper -= passed
        misses += not passed
        if upper < 2:
            break
        if misses == 2:
            break
    if upper >= 2:
        math = cost.adapter.math
        nominee, _ = math.gepa.optimize_by_paid_reads(
            start, roster, train, validation, observe, lambda: len(search),
            paid_limit=cap, batched=math.GEPA[mode.removesuffix('-precheck')], seed=seed,
        )
        if nominee != start:
            paid_validation = ([passed for (prompt, case), passed in search.items()
                                if prompt == name and case in validation] for name in (start, nominee))
            counts = tuple((sum(grades), len(grades)) for grades in paid_validation)
            proof_result = prior.minimum_two(start, nominee, rows, qualify, prefix, counts, seed, cost.adapter.EXPECTED)
            deployed = proof_result.prompt
    grades = tuple(cells[deployed][case][0] for case in held)
    point = {'holdoutPasses': sum(grades), 'searchLookups': len(search),
             'qualificationLookups': len(proof), 'paidLookups': len(search) + len(proof)}
    return point, (seed, start, nominee, deployed, upper), grades


def cpo_trials(cells, start, roster, cohorts, seed, cap):
    validation = tuple(Row(str(case), 'validation') for case in cohorts[1])
    qualification = tuple(Row(str(case), 'qualification') for case in cohorts[2])
    for gain, label in POLICIES.items():
        calls = []

        def read(role, prompt, row):
            grade = bool(cells[prompt][int(row.id)][0])
            calls.append((role, prompt, row.id, grade))
            return grade

        def qualify(prompt, row, repeat):
            if repeat:
                raise ValueError('The archived qualification uses one reply per prompt and case')
            return read('qualification', prompt, row)

        result = run_threshold_prechecked_cycle(
            start, roster, validation, qualification, lambda p, r: Observation(read('validation', p, r), {}),
            metric_limit=cap, qualify=qualify, minimum_gain=gain, seed=seed,
        )
        grades = tuple(cells[result.prompt][case][0] for case in cohorts[-1])
        yield label, {'holdoutPasses': sum(grades), 'paidLookups': len(calls)}, grades, digest(calls)


def measure_panel(subject, matrix, plan, expected):
    cells = {str(i): tuple((int(grade), None, False) for grade in row) for i, row in enumerate(matrix)}
    totals, vectors, stats = {}, {}, Counter()
    changes = {}
    paths = {label: [] for label in POLICIES.values()}
    low, high = plan['minimumSearchCap'], plan['searchCap']

    def tally(label, point, grades):
        totals.setdefault(label, Counter()).update({key: point[key] for key in cost.METRICS})
        transfer.fitted.prior.add_vector(vectors.setdefault(label, [0] * len(grades)), grades)

    def mark_boundary(mode, rule, cap, point, grades, sign):
        spends, counts = changes.setdefault((mode, rule), {}).setdefault(cap, (Counter(), [0] * len(grades)))
        spends.update({key: sign * point[key] for key in cost.METRICS})
        transfer.fitted.prior.add_vector(counts, (sign * grade for grade in grades))

    for seed in plan['seeds']:
        start, roster, cohorts = transfer.archive.transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
        arguments = cells, start, roster, cohorts, seed
        for label, point, grades, path in cpo_trials(*arguments, plan['screenCap']):
            tally(label, point, grades)
            paths[label].append(path)
        keep = tuple(cells[start][case][0] for case in cohorts[-1])
        tally(frontier.RETAIN, {'holdoutPasses': sum(keep), 'paidLookups': 0}, keep)
        for mode in cost.MODES:
            one, two = matched.native_paths(arguments, mode, low, high)
            with patch.object(cost, 'run', gepa_threshold):
                efficient = cost.budget_paths(arguments, mode, low, high)
            if efficient.keys() != (two.keys() if efficient[low][0]['searchLookups'] else {low, high}):
                raise ValueError('Threshold prechecking may only remove all native search boundaries')
            stats.update(legacyNativePaths=2 * len(two), thresholdNativePaths=len(efficient))
            for lower, upper in pairwise((*two, high + 1)):
                point, trace, grades = efficient.get(lower, efficient[low])
                old, old_trace, old_grades = two[lower]
                if (trace[3] != old_trace[3] or grades != old_grades
                        or (trace[4] >= 2 and (trace[:3] != old_trace[:3]
                                              or point['searchLookups'] != old['searchLookups']))
                        or point['searchLookups'] > lower
                        or point['qualificationLookups'] > 2 * len(cohorts[2])
                        or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']):
                    raise ValueError('The new native precheck must preserve results and account for paid replies')
                for rule, (measured, _, scores) in (('gain-1', one[lower]), ('gain-2', two[lower]),
                                                   (THRESHOLD, (point, trace, grades))):
                    mark_boundary(mode, rule, lower, measured, scores, 1)
                    mark_boundary(mode, rule, upper, measured, scores, -1)

    for (mode, rule), boundaries in changes.items():
        spends, counts = Counter(), [0] * len(vectors[frontier.RETAIN])
        for cap in range(low, high + 1):
            if cap in boundaries:
                point, grades = boundaries[cap]
                spends.update(point)
                transfer.fitted.prior.add_vector(counts, grades)
            label = f'{mode}/{cap}/{rule}'
            totals[label], vectors[label] = spends.copy(), counts.copy()
    if {label: digest(path) for label, path in paths.items()} != expected:
        raise ValueError('Both CPO arms must reproduce their published paid callback paths')
    return totals, vectors, stats


def replay_cohort(panels, plan, reference, receipt):
    totals, subjects, by_subject = {}, {}, {}
    stats = Counter()
    for subject, model, matrix in panels:
        points, vectors, checked = measure_panel(subject, matrix, plan, receipt['panelPathHashes'][f'{subject}/{model}'])
        stats.update(checked)
        grades = subjects.setdefault(subject, {})
        costs = by_subject.setdefault(subject, {})
        for label, point in points.items():
            totals.setdefault(label, Counter()).update(point)
            costs.setdefault(label, Counter()).update(point)
            transfer.fitted.prior.add_vector(grades.setdefault(label, [0] * len(vectors[label])), vectors[label])
    policies = tuple(POLICIES.values())
    legacy = tuple(label for label in totals if label not in (*policies, frontier.RETAIN) and not label.endswith(THRESHOLD))
    optimized = tuple(label for label in totals if label.endswith(THRESHOLD))
    if any(totals[label] != reference[label] for label in (*legacy, frontier.RETAIN)):
        raise ValueError('The complete original GEPA curves and retained starts must reproduce')
    if any(totals[label] != receipt['thresholdPrecheck'][label] for label in policies):
        raise ValueError('The published CPO costs and scores must reproduce')
    if any(sum(sum(rows[label]) for rows in subjects.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('Every point must account for its held-out grades')
    for label in optimized:
        original = label.removesuffix(THRESHOLD) + 'gain-2'
        if any(rows[label] != rows[original] for rows in subjects.values()):
            raise ValueError('Matching held-out totals must preserve individual case vectors')

    controls = {'either': (*legacy, *optimized),
                'same-two-gain-precheck': optimized,
                'historical-wrappers': legacy}
    comparisons = frontier.compare(totals, subjects, policies=policies, draws=plan['bootstrapDraws'],
                                   seed=plan['bootstrapSeed'], groups=controls)
    hindsight = transfer.fitted.prior.by_subject_ceiling(
        by_subject, controls['either'], {label: totals[label]['paidLookups'] for label in policies})
    gates = {label: row['either']['holdoutPassDifference'] > 0 and row['either']['pairedRange95'][0] >= 0
             for label, row in comparisons.items()}
    return {'totals': totals, 'comparison': comparisons, 'passedArchiveGate': gates,
            'subjectTunedGepaHindsight': hindsight, 'caseVectorsSha256': digest(subjects), **stats}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, reference, receipt = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    results = {name: replay_cohort(panels, plan, reference[name], receipt[name]) for name, panels in groups.items()}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results}, output,
                  indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
