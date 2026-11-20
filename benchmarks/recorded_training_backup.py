"""Consider a paid validation runner-up when the first nominee lacks training support."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_math_validation_ties as math
from benchmarks import recorded_training_corroboration as prior
from cpo import Row
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
PARENT_SHA256 = '18e481bbe6f9b3c385245517dd43d3aa161a37368735a67810e3c65ff0e9e7db'
AFTER = 'training-after'
BEFORE = 'training-before'
BACKUPS = {'full-backup': False, 'certified-backup': True}
PRECHECK = 'certified-precheck'
PRECHECKED = {PRECHECK: 'certified-backup', **{f'{name}-precheck': name for name in math.GEPA}}
CONTROLS = ('strict', AFTER, *math.GEPA, 'retain-start')
POLICIES = (BEFORE, *BACKUPS, PRECHECK)
METHODS = (*CONTROLS, *POLICIES, *(name for name in PRECHECKED if name != PRECHECK))


def strongest_backup(incumbent, first, roster, rows, ledger, *, partial):
    """Use previously paid evidence to find the best other strict validation gain."""
    base = {row.id: ledger[incumbent, row.id].passed for row in rows}
    protected = {row.id for row in rows if row.critical and base[row.id]}
    winner, score = None, sum(base.values())
    for prompt in roster:
        if prompt == first:
            continue
        evidence = {row.id: ledger[prompt, row.id].passed for row in rows if (prompt, row.id) in ledger}
        if (not partial and len(evidence) != len(rows)) or not all(evidence.get(case) is True for case in protected):
            continue
        passed = sum(evidence.values())
        if passed > score:
            winner, score = prompt, passed
    return winner


def select_with_training(incumbent, first, roster, validation, training, observe, ledger, *,
                         cap, seed, mode, audit):
    def supports(prompt):
        missing = sum((p, row.id) not in ledger for row in training for p in (incumbent, prompt))
        if len(ledger) + missing > cap:
            audit.update(unfundedChecks=1)
            return False
        before = len(ledger)
        supported = prior.corroborate(incumbent, prompt, training, observe, minimum_gain=1,
                                      remaining=2 * len(training), seed=seed)
        audit.update(trainingChecks=1, trainingVetoes=int(not supported), trainingLookups=len(ledger) - before)
        return supported

    if first == incumbent or supports(first):
        return first
    if mode in BACKUPS:
        backup = strongest_backup(incumbent, first, roster, validation, ledger, partial=BACKUPS[mode])
        if backup is not None:
            audit.update(availableBackups=1)
            if supports(backup):
                audit.update(backupNominations=1)
                return backup
    return incumbent


def run_prechecked(cells, start, roster, cohorts, seed, arm, cap):
    """Prepay incumbent qualification replies until the first miss or proven futility."""
    early = {}
    for case in cohorts[2]:
        early[case] = bool(cells[start][case][0])
        if not early[case]:
            break
    stopped = all(early.values())
    if stopped:
        total, trace, values = math.run_trial(cells, start, roster, cohorts, seed, 'retain-start', cap)
    else:
        original = math.certify_paired_qualification

        def qualify(incumbent, challenger, rows, evaluate, *, seed):
            def read(prompt, row, repeat):
                case = int(row.id)
                if prompt == start and repeat == 0 and case in early:
                    return early[case]
                return evaluate(prompt, row, repeat)

            return original(incumbent, challenger, rows, read, seed=seed)

        with patch.object(math, 'certify_paired_qualification', qualify):
            total, trace, values = run_trial(cells, start, roster, cohorts, seed, PRECHECKED[arm], cap)
    total['qualificationLookups'] += len(early)
    total['paidLookups'] += len(early)
    total.update(precheckLookups=len(early), precheckStops=int(stopped))
    if 'historicalCostNanodollars' in total:
        total['historicalCostNanodollars'] += sum(cells[start][case][1] for case in early)
        total['historicalErrors'] += sum(cells[start][case][2] for case in early)
    return total, (*trace[:4], digest((list(early.items()), trace[4]))), values


def run_trial(cells, start, roster, cohorts, seed, arm, cap):
    if arm in PRECHECKED:
        return run_prechecked(cells, start, roster, cohorts, seed, arm, cap)
    if arm == AFTER:
        return prior.run_trial(cells, start, roster, cohorts, seed, 'half-training-support', cap)
    if arm in CONTROLS:
        return math.run_trial(cells, start, roster, cohorts, seed, arm, cap)
    original = math.select
    audit = Counter()
    training = tuple(Row(str(case), 'training') for case in cohorts[0][:len(cohorts[0]) // 2])

    def select(incumbent, candidates, rows, observe, ledger, *, method, cap):
        first, _ = original(incumbent, candidates, rows, observe, ledger, method=method, cap=cap)
        chosen = select_with_training(incumbent, first, candidates, rows, training, observe, ledger,
                                      cap=cap, seed=seed, mode=arm, audit=audit)
        return chosen, False

    with patch.object(math, 'select', select):
        total, trace, values = math.run_trial(cells, start, roster, cohorts, seed, 'strict', cap)
    audit.update(backupPromotions=int(audit['backupNominations'] > 0 and trace[3] != start))
    return {**total, **audit}, trace, values


def prepare():
    parent, data, _ = prior.prepare()
    raw = (ROOT / 'docs/recorded-training-corroboration-results-v1.json').read_bytes()
    report = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_SHA256 or report['planSha256'] != digest(parent):
        raise ValueError('The archived training-veto comparison differs from its published seal')
    paths = ('benchmarks/recorded_training_backup.py', 'benchmarks/recorded_training_corroboration.py',
             'benchmarks/recorded_math_validation_ties.py', 'cpo/pool.py', 'cpo/paired_qualification.py')
    plan = {**{key: parent[key] for key in ('gepaVersion', 'datasets', 'challengerCounts', 'incumbentGroups',
                                           'searchCap', 'bootstrapSeed', 'bootstrapDraws',
                                           'minimumLookupSavingPercent')},
            'protocol': 'cpo-recorded-training-backup-v1', 'priorPlanSha256': digest(parent),
            'priorReportSha256': PARENT_SHA256,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'methods': METHODS, 'backupPolicies': BACKUPS, 'precheckedMethods': PRECHECKED,
            'scope': ('Use the first half of the existing training panel before independent qualification. '
                      'Compare an exact reordering of the veto with checking one validation-proven alternate. '
                      'Prioritize paid strict gains and reserve the complete training proof under the original cap. '
                      'Apply an incumbent-only qualification precheck to CPO and both GEPA controls.')}
    return plan, data, report['results']


def measure(cells, settings, group, width, plan, reference):
    size = len(next(iter(cells.values())))
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    totals, journals = {m: Counter() for m in METHODS}, {m: [] for m in METHODS}
    vectors = {m: [0] * size for m in METHODS}
    changes = {m: Counter() for m in POLICIES}
    for seed in settings['seeds']:
        cohorts = math.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            available = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(available, len(available))[:width]
            outcomes = {}
            for arm in METHODS:
                point, trace, values = run_trial(cells, start, roster, cohorts, seed, arm, plan['searchCap'])
                totals[arm].update(point)
                journals[arm].append(trace)
                outcomes[arm] = trace[3], point['holdoutPasses']
                for case, passed in zip(cohorts[-1], values, strict=True):
                    vectors[arm][case] += passed
            if outcomes[BEFORE] != outcomes[AFTER]:
                raise ValueError('Changing the order of the two gates changed the deployed prompt')
            if any(outcomes[arm] != outcomes[original] for arm, original in PRECHECKED.items()):
                raise ValueError('The incumbent precheck changed the deployed prompt')
            for arm in POLICIES:
                delta = outcomes[arm][1] - outcomes[AFTER][1]
                changes[arm].update(trialsImproved=int(delta > 0), trialsRegressed=int(delta < 0),
                                    grossGain=max(0, delta), grossLoss=max(0, -delta))
    points = {arm: {**count, 'traceSha256': digest(journals[arm])} for arm, count in totals.items()}
    for arm in CONTROLS:
        name = 'half-training-support' if arm == AFTER else arm
        if points[arm] != reference['totals'][name]:
            raise ValueError('The frozen comparison path, score or lookup count differs')
    if any(sum(vectors[arm]) != totals[arm]['holdoutPasses'] for arm in METHODS):
        raise ValueError('The case vectors differ from the reported scores')
    comparisons = {}
    controls = (AFTER, *math.GEPA)
    for arm in POLICIES:
        compared = controls if arm == BEFORE else (*controls, BEFORE)
        ranges = math.paired_ranges(vectors, arm, compared, plan)
        comparisons[arm] = math.comparison(arm, totals, ranges, plan)
    same_precheck = {rival: f'{rival}-precheck' for rival in math.GEPA}
    matched_totals = {**totals, **{rival: totals[arm] for rival, arm in same_precheck.items()}}
    matched_vectors = {**vectors, **{rival: vectors[arm] for rival, arm in same_precheck.items()}}
    matched_ranges = math.paired_ranges(matched_vectors, PRECHECK, math.GEPA, plan)
    matched = math.comparison(PRECHECK, matched_totals, matched_ranges, plan)
    return {'totals': points, 'comparisons': comparisons, 'changesFromTrainingAfter': changes,
            'matchedPrecheckComparison': {**matched, 'controls': same_precheck},
            'reorderedDecisionsChecked': len(journals[BEFORE]),
            'precheckedDecisionsChecked': len(journals[BEFORE]) * len(PRECHECKED),
            'trialsPerMethod': reference['trialsPerMethod']}


def replay(plan, sources, references):
    results = {}
    for name, settings in plan['datasets'].items():
        cells = math.load_cells(name, sources[name]['record'])
        results[name] = {f'{group}/{width}': measure(cells, settings, group, width, plan,
                                                    references[name][f'{group}/{width}'])
                         for group in plan['incumbentGroups'] for width in plan['challengerCounts']}
    return {'plan': plan, 'planSha256': digest(plan), 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, sources, references = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, sources, references)
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
