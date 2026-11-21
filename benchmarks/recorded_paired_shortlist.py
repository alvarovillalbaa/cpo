"""Screen a complete challenger roster before exact validation and qualification."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_certificate_cost_frontier as cost
from cpo import Row, select_pool
from cpo._contract import digest


transfer = cost.transfer
adapter = cost.adapter
REFERENCE = 'docs/recorded-certificate-cost-frontier-results-v1.json'
REFERENCE_SHA256 = '756bac3d036a4fb07a9bcd3959f7c0599aca0e8257afa4507b0a22950e9e4ffb'
FIXED = 'paired-halves'
TIES = 'paired-halves-keep-ties'
ARMS = (FIXED, TIES)


def shortlist(incumbent, roster, rows, training, observe, ledger, *, cap, keep_ties, audit):
    if len(ledger) + sum((incumbent, row.id) not in ledger for row in rows) > cap:
        return incumbent
    passed = {row.id for row in rows if observe(incumbent, row).passed}
    if len(passed) == len(rows) or not roster:
        return incumbent
    protected = {row.id for row in rows if row.critical and row.id in passed}
    losses = [row for row in rows if row.id not in passed]
    gains = sorted((row for row in rows if row.id in passed), key=lambda row: row.id not in protected)
    screen = (losses[0], gains[0]) if gains else losses[:2]
    active = list(roster)
    reserve = max(sum((name, row.id) not in ledger for name in (incumbent, prompt) for row in training)
                  for prompt in active)
    grades = Counter()
    for depth, row in enumerate(screen, 1):
        if len(active) <= 2 or len(ledger) + len(active) + len(rows) - depth + reserve > cap:
            break
        before = len(ledger)
        for prompt in active:
            grades[prompt] += observe(prompt, row).passed
        audit['screenLookups'] += len(ledger) - before
        active = [prompt for prompt in active if (grades[prompt] + len(rows) - depth > len(passed)
                                                 and all(ledger[prompt, case].passed for case in protected
                                                         if (prompt, case) in ledger))]
        active.sort(key=grades.__getitem__, reverse=True)
        survivors = (len(active) + 1) // 2
        if keep_ties and survivors:
            cutoff = grades[active[survivors - 1]]
            active = [prompt for prompt in active if grades[prompt] >= cutoff]
        else:
            active = active[:survivors]

    finalists = []
    remaining = cap - len(ledger) - reserve
    for prompt in active:
        needed = sum((prompt, row.id) not in ledger for row in rows)
        if needed <= remaining:
            finalists.append(prompt)
            remaining -= needed
    if not finalists:
        return incumbent
    audit['completedShortlistSlots'] += len(finalists)
    before = len(ledger)
    result = select_pool((incumbent, *finalists), rows, observe, metric_limit=(len(finalists) + 1) * len(rows),
                         adaptive_rejection=True)
    audit['finalistValidationLookups'] += len(ledger) - before
    return result.prompt


def trial(cells, start, roster, cohorts, seed, cap, arm):
    training = tuple(Row(str(case), 'training') for case in cohorts[0][:len(cohorts[0]) // 2])
    audit = Counter()

    def choose(incumbent, candidates, rows, observe, ledger, *, method, cap):
        winner = shortlist(incumbent, candidates, rows, training, observe, ledger, cap=cap,
                           keep_ties=arm == TIES, audit=audit)
        return winner, False

    with (patch.object(adapter.math, 'select', choose),
          patch.object(adapter.backup, 'strongest_backup', lambda *args, **kwargs: None)):
        point, trace, grades = adapter.run_trial(cells, start, roster, cohorts, seed, cap,
                                                 adapter.prior.CANDIDATE, adapter.EXPECTED)
    return {**point, **audit}, trace, grades


def prepare():
    frontier_plan, groups, original = cost.prepare()
    reference = cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, frontier_plan)
    plan = {**{key: frontier_plan[key] for key in ('gepaVersion', 'bootstrapSeed', 'bootstrapDraws', 'searchCap',
                                                  'minimumSearchCap', 'seeds', 'challengers', 'caseCounts')},
            'protocol': 'recorded-paired-shortlist-v1', 'parentPlanSha256': digest(frontier_plan),
            'parentReceiptSha256': REFERENCE_SHA256, 'policies': ARMS,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Screen challengers on the first incumbent miss, then survivors on the first incumbent '
                     'pass with critical passes first. When all incumbent grades fail, use the first two misses. '
                     'Compare fixed halves and keeping a tie at the cut. Resolve the shortlist by exact '
                     'validation with the existing training reserve and one qualification attempt. Keep '
                     'the original archived rosters and compare with the same realized-cost GEPA frontier.'}
    return plan, groups, original, reference['results']


def measure_cohort(plan, panels, original, reference):
    retain = cost.frontier.RETAIN
    totals = {retain: reference['totals'][retain]}
    by_subject = {subject: {retain: rows[retain]} for subject, rows in original['caseVectorsBySubject'].items()}
    details = {}
    for _, subject, model, matrix in panels:
        name = f'{subject}/{model}'
        points, scores = cost.measure_panel(subject, matrix, plan, original['panels'][name])
        with (patch.object(transfer, 'METHODS', ARMS), patch.object(transfer.study, 'trial', trial)):
            measured, cases = transfer.measure_panel(matrix, subject, plan)
        details[name] = measured
        rows = by_subject[subject]
        for label, point in {**points, **measured}.items():
            totals.setdefault(label, Counter()).update({k: v for k, v in point.items() if k != 'traceSha256'})
            grades = scores[label] if label in scores else cases[label]
            old = rows.get(label, [0] * len(grades))
            rows[label] = [a + b for a, b in zip(old, grades, strict=True)]
    settings = tuple(label for label in totals if label not in (*ARMS, retain))
    if any(totals[label] != reference['totals'][label] for label in settings):
        raise ValueError('The exact GEPA cost frontier must reproduce at every cap')
    if any(sum(sum(rows[label]) for rows in by_subject.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('The paired case totals must reproduce every score')
    comparisons = cost.frontier.compare(totals, by_subject, policies=ARMS, draws=plan['bootstrapDraws'],
                                        seed=plan['bootstrapSeed'], groups={'either-mode': settings})
    return {'totals': {arm: totals[arm] for arm in ARMS},
            'comparisons': {arm: row['either-mode'] for arm, row in comparisons.items()}, 'panels': details}


def execute(plan, groups, original, reference):
    results = {}
    for name, panels in groups.items():
        results[name] = {cohort: measure_cohort(plan, [panel for panel in panels if panel[0] == cohort], archived,
                                               reference[name][cohort]) for cohort, archived in original[name].items()}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, original, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = execute(plan, groups, original, reference)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
