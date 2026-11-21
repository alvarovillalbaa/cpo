"""Reserve validation cases for finalists without adding evaluation roles."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_disjoint_finalist_witness as prior
from cpo import select_pool
from cpo._contract import digest


core, math, transfer = prior.core, prior.math, prior.transfer
REFERENCE = 'docs/recorded-disjoint-finalist-witness-results-v1.json'
REFERENCE_SHA256 = '4477a150394f9ac23225c873e42bbfb38e4d2e883be5da0f81ea35a64c3148dc'
TAILS = {'one-case-validation-tail': 1, 'two-case-validation-tail': 2}


def remaining_certificate(prompt, rows, target, protected, ledger):
    paid = {row.id: ledger[prompt, row.id].passed for row in rows if (prompt, row.id) in ledger}
    unread = [row for row in rows if row.id not in paid]
    remaining = protected - paid.keys()
    if any(case in paid and not paid[case] for case in protected) or sum(paid.values()) + len(unread) < target:
        return None
    return target - sum(paid.values()), remaining, unread


def finish_certificate(prompt, quote, observe):
    if quote is None:
        return False
    needed, protected, unread = quote
    order = sorted(unread, key=lambda row: row.id not in protected)
    for index, row in enumerate(order):
        if needed <= 0 and not protected:
            return True
        if needed > len(order) - index:
            return False
        passed = observe(prompt, row).passed
        if type(passed) is not bool:
            raise ValueError('Validation requires exact boolean grades')
        if row.id in protected:
            if not passed:
                return False
            protected.remove(row.id)
        needed -= passed
    return needed <= 0 and not protected


def select_tail(incumbent, roster, rows, observe, ledger, *, cap, width, audit):
    """Nominate on the reserved tail and prove a full-panel gain against the incumbent."""
    if not 0 < width < len(rows) or cap < len(rows):
        raise ValueError('The race requires a funded validation panel with a nonempty prefix and tail')
    prefix, tail = rows[:-width], rows[-width:]
    candidates = (incumbent, *roster)

    def full_race():
        # The incumbent is always read first, so these cached reads are safe to credit.
        credit = sum((incumbent, row.id) in ledger for row in rows)
        limit = cap if len(candidates) * len(rows) <= cap else cap - len(ledger) + credit
        audit['fullRaceFallbacks'] += 1
        if limit < len(rows):
            return incumbent
        return select_pool(candidates, rows, observe, metric_limit=limit, adaptive_rejection=True).prompt

    first = select_pool(candidates, prefix, observe, metric_limit=cap - width, adaptive_rejection=True).prompt
    if first == incumbent:
        return full_race()
    alternate = core.backup.strongest_backup(incumbent, first, roster, prefix, ledger, partial=True)
    finalists = (first,) if alternate is None else (first, alternate)
    base = {row.id: observe(incumbent, row).passed for row in rows}
    target = 1 + sum(base.values())
    if target > len(rows):
        return incumbent
    protected = {row.id for row in rows if row.critical and base[row.id]}
    quotes = {prompt: remaining_certificate(prompt, rows, target, protected, ledger) for prompt in finalists}
    feasible = [prompt for prompt in finalists if quotes[prompt] is not None]
    reserve = sum(len(quotes[prompt][2]) for prompt in feasible)
    if not feasible or len(ledger) + reserve > cap:
        return full_race()

    before = len(ledger)
    tail_passes = {prompt: sum(observe(prompt, row).passed for row in tail) for prompt in feasible}
    audit.update(finalistTailLookups=len(ledger) - before, comparedPairs=int(len(feasible) == 2))
    for prompt in sorted(feasible, key=tail_passes.__getitem__, reverse=True):
        quote = remaining_certificate(prompt, rows, target, protected, ledger)
        if finish_certificate(prompt, quote, observe):
            audit['tailNominations'] += int(prompt != first)
            return prompt
    return full_race()


def run_trial(cells, start, roster, cohorts, seed, cap, width):
    audit = Counter()

    def select(incumbent, candidates, rows, observe, ledger, *, method, cap):
        return select_tail(incumbent, candidates, rows, observe, ledger, cap=cap, width=width, audit=audit), False

    calibrated = prior.prior
    with (patch.object(math, 'select', select), patch.object(core.prior, 'can_defer', lambda *_: False),
          patch.object(core.backup, 'select_with_training', lambda _, first, *args, **kwargs: first)):
        point, trace, grades = calibrated.adapter.run_trial(cells, start, roster, cohorts, seed, cap,
                                                             prior.parent.BASELINE, calibrated.adapter.EXPECTED)
    if (point['searchLookups'] > cap or point['qualificationLookups'] > 2 * len(cohorts[2])
            or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']):
        raise ValueError('The tail and full certificate must fit the original budgets')
    return {**point, **audit}, trace, grades


def paired_trial(args, width, baseline, changes):
    old, old_trace, old_grades = baseline
    point, trace, grades = run_trial(*args, width)
    if trace[2] == old_trace[2] and (trace[3] != old_trace[3] or grades != old_grades):
        raise ValueError('The same nominee must get the same independent decision and held-out grades')
    delta = sum(grades) - sum(old_grades)
    changes.update(trials=1, changedNominations=int(trace[2] != old_trace[2]),
                   changedDeployments=int(trace[3] != old_trace[3]), passDelta=delta,
                   grossGain=max(delta, 0), grossLoss=max(-delta, 0),
                   lookupDelta=point['paidLookups'] - old['paidLookups'],
                   searchLookupDelta=point['searchLookups'] - old['searchLookups'])
    if transfer.HISTORICAL in point:
        changes['historicalCostDeltaNanodollars'] += point[transfer.HISTORICAL] - old[transfer.HISTORICAL]
    return point, trace, grades


def prepare():
    inherited, *inputs = prior.prepare()
    report = transfer.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, inherited)
    plan = {**{key: inherited[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                               'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-validation-tail-finalists-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': REFERENCE_SHA256, 'tailWidths': TAILS,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Reserve the last one or two validation cases for two strict prefix finalists. '
                     'Order them by paid tail scores, then prove a strict gain on the original full '
                     'validation panel. Fall back to the full race with paid grades if neither finalist '
                     'can certify. Preserve the search cap, independent qualification, and archived '
                     'holdout. Replay the same math and language panels and their native controls. '
                     'Check the math margin against the full race by case ID and by omitted incumbent.'}
    return plan, inputs, report


def paired_math_sensitivity(plan, data, results):
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        size = len(next(iter(cells.values())))
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                by_case = {mode: [0] * size for mode in TAILS}
                by_start = {mode: Counter() for mode in TAILS}
                for start, roster, cohorts, seed in transfer.trials(cells, settings, group, width):
                    args = cells, start, roster, cohorts, seed, plan['searchCap']
                    _, _, original, _ = prior.prior.run_trial(*args, ())
                    for mode, tail_width in TAILS.items():
                        _, _, revised = run_trial(*args, tail_width)
                        by_start[mode][start] += sum(revised) - sum(original)
                        for case, old, new in zip(cohorts[-1], original, revised, strict=True):
                            by_case[mode][case] += new - old
                comparisons = results[dataset][f'{group}/{width}']
                for mode, vector in by_case.items():
                    delta = comparisons[mode]['pairedChanges']['passDelta']
                    if sum(vector) != delta or sum(by_start[mode].values()) != delta:
                        raise ValueError('Case and incumbent sensitivities must reconcile to the actual pass change')
                    rng = Random(plan['bootstrapSeed'])
                    draws = [sum(rng.choices(vector, k=size)) for _ in range(plan['bootstrapDraws'])]
                    comparisons[mode]['pairedCaseRange95VsFullRace'] = math.interval(draws)
                    comparisons[mode]['passDeltaByIncumbent'] = by_start[mode]
                    if len(by_start[mode]) > 1:
                        omitted = [delta - count for count in by_start[mode].values()]
                        comparisons[mode]['passDeltaRangeOmittingOneIncumbent'] = [min(omitted), max(omitted)]


def replay(plan, inputs, reference):
    with patch.object(prior, 'WIDTHS', TAILS), patch.object(prior, 'paired_trial', paired_trial):
        report = prior.replay(plan, *inputs)
    # The native language anchors retain the same fixed-cap costs and scores.
    for cohort, result in report['language'].items():
        for arm in (prior.prior.NEVER, *prior.language.CONTROL_NAMES.values(), 'retain-start'):
            if result['totals'][arm] != reference['language'][cohort]['totals'][arm]:
                raise ValueError('The language costs must match the earlier finalist replay')
    paired_math_sensitivity(plan, inputs[0], report['math'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, inputs, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, inputs, reference)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
