"""After the primary finalist fails, prioritize a backup with a witnessed repair."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import case_difficulty_allocation as parent
from benchmarks import finalist_screen_budget as finalist
from benchmarks import posterior_model_transfer as previous
from benchmarks import routed_score_allocation as route
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
POLICIES = ('complementary-backup', 'additional-miss-backup')
CONTROLS = (*previous.CPO, *previous.CONTROLS)
_shortlist = finalist.shortlist
_screen = finalist.screen


def screen(incumbent, candidates, rows, evaluate, *, metric_limit, width, screen_rows, mode, audit, complementary):
    """Change only the backup tie break in the original two-probe race."""
    rows = tuple(rows)
    ledger = {}

    def measure(prompt, row):
        result = evaluate(prompt, row)
        ledger[prompt, row.id] = result.passed
        return result

    def shortlist(candidates, probes, observe, *, size, lazy):
        nominal = _shortlist(candidates, probes, observe, size=size, lazy=lazy)
        if size != 2 or len(nominal) != 2:
            return nominal
        first, backup = nominal
        initial_reads = {row.id for row in probes}
        witness = next((row for row in rows if row.id not in initial_reads and not ledger[incumbent, row.id]
                        and (not complementary or ledger.get((first, row.id)) is False)), None)
        if witness is None:
            return nominal
        tied_at = sum(ledger[backup, row.id] for row in probes)

        def suffix(prompt):
            return sum((prompt, row.id) not in ledger for row in rows)

        tied = [prompt for prompt in candidates if prompt != first
                and sum(ledger.get((prompt, row.id), True) for row in probes) >= tied_at]
        if len(tied) == 1:
            return nominal
        audit.update(availableBackupTies=1)
        for prompt in tied:
            unread = tuple(row for row in probes if (prompt, row.id) not in ledger)
            cost = len(unread) + ((prompt, witness.id) not in ledger)
            fallback = suffix(backup) + (cost if prompt != backup else 0)
            reserve = suffix(first) + max(fallback, suffix(prompt))
            if len(ledger) + reserve > metric_limit:
                continue
            before = len(ledger)
            hits = sum(observe(prompt, row).passed for row in probes)
            repaired = hits == tied_at and observe(prompt, witness).passed
            audit.update(tieBreakLookups=len(ledger) - before)
            if repaired:
                audit.update(changedBackup=int(prompt != backup))
                return first, prompt
        return nominal

    with patch.object(finalist, 'shortlist', shortlist):
        return _screen(incumbent, candidates, rows, measure, metric_limit=metric_limit, width=width,
                       screen_rows=screen_rows, mode=mode, audit=audit)


def prepare():
    prior, inputs = parent.prepare()
    own = Path(__file__).resolve()
    return {'protocol': 'cpo-complementary-backup-v1', 'parentDesignSha256': digest(prior),
            'cohorts': prior['cohorts'], 'runnerSha256': sha256(own.read_bytes()).hexdigest(),
            'primary': POLICIES[0], 'policies': POLICIES, 'controls': CONTROLS,
            'scope': ('After the original shortlist primary fails, use one additional miss to break a tie '
                      'for the single backup. Prefer a case with a paid miss from both the incumbent and '
                      'failed finalist. The ablation uses the first other incumbent miss instead. Each '
                      'branch funds the full exact backup, with the same cap and separate qualification.')}, inputs


def measure(panels, references, plan):
    totals = {arm: Counter() for arm in (*CONTROLS, *POLICIES)}
    results, vectors, holdouts = {}, {arm: {} for arm in POLICIES}, {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held, points, outcomes = previous.measure(panel, plan)
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('Both models must share the holdout cases')
        for arm, point in points.items():
            expected = references[name][arm]
            if any(point[key] != expected[key] for key in parent.FIELDS if key in expected):
                raise ValueError(f'Control differs from its archived receipt: {name}/{arm}')

        starts = route.ties.costs.retained_prompts(matrix, held, plan['schedule'])
        for arm in POLICIES:
            def select(*args, **kwargs):
                return screen(*args, **kwargs, complementary=arm == POLICIES[0])

            counts, logs = Counter(), []
            with patch.object(finalist, 'screen', select):
                for seed, start in zip(plan['schedule']['seeds'], starts, strict=True):
                    usage, trace = route.run(matrix, held, seed, plan, str(start), 'strict')
                    counts.update(usage)
                    logs.append(trace)
            finals = [int(trace[-1]['decision']['selected']) for trace in logs]
            cases = route.CONFIRMATION.uncertainty.case_totals(matrix, held, finals)
            if sum(cases.values()) != counts['holdoutPasses']:
                raise ValueError('Candidate holdout score differs from its selected prompts')
            points[arm] = {**counts, 'paidLookups': counts['searchPaid'] + counts['qualificationPaid'],
                           'traceSha256': digest(logs)}
            paired = vectors[arm].setdefault(subject, {control: [0] * len(held) for control in CONTROLS})
            for name_control, vector in paired.items():
                for i, case in enumerate(held):
                    vector[i] += cases[case] - outcomes[name_control][case]
        fields = (*parent.FIELDS, 'availableBackupTies', 'tieBreakLookups', 'changedBackup')
        results[name] = {arm: {key: point[key] for key in fields if key in point} for arm, point in points.items()}
        for arm, point in results[name].items():
            totals[arm].update({key: count for key, count in point.items() if type(count) is int})

    comparisons = {}
    for arm, groups in vectors.items():
        ranges = route.transfer.ranges(groups, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
        budget = totals[arm]['paidLookups']
        savings = {name: 1 - budget / totals[name]['paidLookups'] for name in route.GEPA}
        ceiling = 100 - plan['minimumLookupSavingPercent']
        funded = all(100 * budget <= ceiling * totals[name]['paidLookups'] for name in route.PRIMARY)
        low, high = ranges['joint']
        outcome = 'failed' if not funded or high < 0 else 'passed' if low >= 0 else 'inconclusive'
        comparisons[arm] = {'gate': outcome, 'pairedRanges': ranges, 'lookupSavings': savings}
    return {'panels': results, 'totals': totals, 'comparisons': comparisons}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, inputs = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for _, _, plan in inputs.values()):
        cli.error('Use the pinned GEPA version')
    result = {cohort: measure(*data) for cohort, data in inputs.items()}
    with args.out.open('x') as stream:
        json.dump({'design': design, 'designSha256': seal, 'results': result}, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
