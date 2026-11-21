"""Compare evidence from both incumbent outcomes before cutting the shortlist."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_paired_shortlist as previous
from cpo import select_pool
from cpo._contract import digest


PAIRED = 'both-witnesses-before-cut'
SINGLE = 'one-witness-three-finalists'
ARMS = (PAIRED, SINGLE)
REFERENCE = 'docs/recorded-paired-shortlist-results-v1.json'
REFERENCE_SHA256 = '3594bbdaadf7c3b939d9af37b8f7ee1f5d648d4d88304305b7814a7d882bff54'
original_shortlist = previous.shortlist


def screen_finalists(roster, first, second, target, case_count, protected, observe, ledger, audit):
    finalist_limit = 3 if second is None else 2
    leaders = []
    before = len(ledger)
    first_grades = {prompt: observe(prompt, first).passed for prompt in roster}
    ordered = sorted(roster, key=first_grades.__getitem__, reverse=True)
    for order, prompt in enumerate(ordered):
        initial = first_grades[prompt]
        if initial + case_count - 1 < target:
            continue
        rank = (initial, initial, -order)
        if second is not None:
            optimistic = (initial + 1, initial, -order)
            if len(leaders) == finalist_limit and optimistic <= leaders[-1][0]:
                audit['skippableSecondWitnesses'] += 1
                continue
            other = observe(prompt, second).passed
            if (not other and second.id in protected) or initial + other + case_count - 2 < target:
                continue
            rank = (initial + other, initial, -order)
        leaders.append((rank, prompt))
        leaders.sort(reverse=True)
        del leaders[finalist_limit:]
    audit['screenLookups'] += len(ledger) - before
    return [prompt for _, prompt in leaders]


def search(incumbent, roster, rows, training, observe, ledger, *, cap, arm, audit):
    if len(ledger) + sum((incumbent, row.id) not in ledger for row in rows) > cap:
        return incumbent
    if len(roster) <= 2 or len(rows) < 2:
        return original_shortlist(incumbent, roster, rows, training, observe, ledger, cap=cap,
                                  keep_ties=False, audit=audit)
    passed = {row.id for row in rows if observe(incumbent, row).passed}
    if len(passed) == len(rows):
        return incumbent
    protected = {row.id for row in rows if row.critical and row.id in passed}
    misses = [row for row in rows if row.id not in passed]
    passes = sorted((row for row in rows if row.id in passed), key=lambda row: row.id not in protected)
    first = misses[0]
    second = (passes or misses[1:])[0] if arm == PAIRED else None
    depth, finalist_limit = (2, 2) if second is not None else (1, 3)
    reserve = max(sum((name, row.id) not in ledger for name in (incumbent, prompt) for row in training)
                  for prompt in roster)
    if len(ledger) + depth * len(roster) + finalist_limit * (len(rows) - depth) + reserve > cap:
        return original_shortlist(incumbent, roster, rows, training, observe, ledger, cap=cap,
                                  keep_ties=False, audit=audit)
    finalists = screen_finalists(roster, first, second, len(passed) + 1, len(rows), protected,
                                 observe, ledger, audit)
    if not finalists:
        return incumbent
    before = len(ledger)
    result = select_pool((incumbent, *finalists), rows, observe, metric_limit=(len(finalists) + 1) * len(rows),
                         adaptive_rejection=True)
    audit['completedShortlistSlots'] += len(finalists)
    audit['finalistValidationLookups'] += len(ledger) - before
    return result.prompt


def prepare():
    parent, groups, original, controls = previous.prepare()
    reference = previous.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, parent)
    plan = {**parent, 'protocol': 'recorded-shortlist-screen-order-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': REFERENCE_SHA256, 'policies': (*previous.ARMS, *ARMS),
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Measure all challengers on the same miss and pass before retaining two, skipping the '
                     'second grade only if the candidate cannot enter the top two. Compare one common miss '
                     'with three finalists under the same training and qualification policy. Reproduce '
                     'both earlier shortlists and the same matched-cost GEPA frontier.'}
    return plan, groups, original, controls, reference['results']


def execute(plan, groups, original, controls, reference):
    old_trial, old_arms = previous.trial, previous.ARMS

    def trial(*arguments):
        arm = arguments[-1]
        if arm in old_arms:
            return old_trial(*arguments)

        def choose(*args, cap, keep_ties, audit):
            return search(*args, cap=cap, arm=arm, audit=audit)

        with patch.object(previous, 'shortlist', choose):
            return old_trial(*arguments)

    with (patch.object(previous, 'ARMS', plan['policies']), patch.object(previous, 'trial', trial)):
        report = previous.execute(plan, groups, original, controls)
    for name, cohorts in report['results'].items():
        for cohort, result in cohorts.items():
            frozen = reference[name][cohort]
            for field in ('totals', 'comparisons'):
                if any(result[field][arm] != frozen[field][arm] for arm in old_arms):
                    raise ValueError('The original shortlist totals and comparisons must reproduce')
            for panel, result_by_arm in result['panels'].items():
                if any(result_by_arm[arm] != frozen['panels'][panel][arm] for arm in old_arms):
                    raise ValueError('The original shortlist panel and path hash must reproduce')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, original, controls, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = execute(plan, groups, original, controls, reference)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
