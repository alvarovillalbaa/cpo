"""Choose between strict validation finalists on disjoint reserved cases."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_calibrated_training_route as prior
from benchmarks import recorded_first_certificate_transfer as language
from cpo import Row
from cpo._contract import digest


parent, transfer, math, core = prior.parent, prior.transfer, prior.math, prior.core
MATH_REFERENCE = 'docs/recorded-calibrated-training-route-results-v1.json'
MATH_SHA256 = '1bbe3cd66272b46c638b7dfa698361e0257c369b545086394f9a63c1c21d193d'
LANGUAGE_REFERENCE = 'docs/recorded-first-certificate-transfer-results-v1.json'
LANGUAGE_SHA256 = '42e3bb7943311efd6784ce5e9494c6aa2c35a8d712f253af2198c71fbff3b748'
WIDTHS = {'two-case-finalist-witness': 2, 'four-case-finalist-witness': 4}


def choose(incumbent, first, candidates, rows, witness, observe, ledger, cells, *, cap, audit):
    if first == incumbent:
        return first
    alternate = core.backup.strongest_backup(incumbent, first, candidates, rows, ledger, partial=True)
    if alternate is None or not witness:
        return first
    prompts = first, alternate
    reserve = sum((prompt, row.id) not in ledger for prompt in prompts for row in witness)
    if len(ledger) + reserve > cap:
        return first
    rates, prices = parent.estimate(prompts, rows, ledger, cells)
    before = len(ledger)
    replaced = parent.settle(prompts, witness, observe, ledger, rates, prices, minimum_gain=1)
    audit.update(pairedWitnesses=1, witnessLookups=len(ledger) - before, replacements=int(replaced))
    return alternate if replaced else first


def run_trial(cells, start, roster, cohorts, seed, cap, width):
    original = math.select
    audit = Counter()
    training = cohorts[0]
    witness = tuple(Row(str(case), 'selection-witness') for case in training[len(training) // 2:][:width])
    if len(witness) != width:
        raise ValueError('The planned disjoint witness does not fit in the reserved training cases')

    def select(incumbent, candidates, rows, observe, ledger, **kwargs):
        first, tied = original(incumbent, candidates, rows, observe, ledger, **kwargs)
        winner = choose(incumbent, first, candidates, rows, witness, observe, ledger, cells, cap=cap, audit=audit)
        return winner, tied and winner == first

    with (patch.object(math, 'select', select), patch.object(core.prior, 'can_defer', lambda *_: False),
          patch.object(core.backup, 'select_with_training', lambda _, first, *args, **kwargs: first)):
        point, trace, grades = prior.adapter.run_trial(cells, start, roster, cohorts, seed, cap,
                                                        parent.BASELINE, prior.adapter.EXPECTED)
    if (point['searchLookups'] > cap or point['qualificationLookups'] > 2 * len(cohorts[2])
            or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']
            or audit['witnessLookups'] > 2 * width):
        raise ValueError('The witness and independent proof must stay within their budgets')
    return {**point, **audit}, trace, grades


def paired_trial(args, width, baseline, changes):
    before, old, old_grades = baseline
    point, trace, grades = run_trial(*args, width)
    if (point['searchLookups'] != before['searchLookups'] + point.get('witnessLookups', 0)
            or (trace[2] == old[2] and (trace[3] != old[3] or grades != old_grades
                                       or point['qualificationLookups'] != before['qualificationLookups']))):
        raise ValueError('Only the new witness and its change of nominee may affect the original path')
    gain = sum(grades) - sum(old_grades)
    changes.update(trials=1, changedDeployments=int(trace[3] != old[3]), passDelta=gain,
                   grossGain=max(gain, 0), grossLoss=max(-gain, 0), lookupDelta=point['paidLookups'] - before['paidLookups'])
    if transfer.HISTORICAL in point:
        changes['historicalCostDeltaNanodollars'] += point[transfer.HISTORICAL] - before[transfer.HISTORICAL]
    return point, trace, grades


def prepare():
    inherited, data, controls, baseline, _, _ = prior.prepare()
    report = transfer.cost.prior.baseline.read_reference(MATH_REFERENCE, MATH_SHA256, inherited)
    lang_plan, panels = language.prepare()
    lang_report = transfer.cost.prior.baseline.read_reference(LANGUAGE_REFERENCE, LANGUAGE_SHA256, lang_plan)
    plan = {**{key: inherited[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                               'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-disjoint-finalist-witness-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': MATH_SHA256, 'languagePlanSha256': digest(lang_plan),
            'languageReceiptSha256': LANGUAGE_SHA256, 'witnessWidths': WIDTHS,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Keep the strict validation race and its strongest already certified backup. '
                     'Pick the backup only when it strictly beats the winner on the first two or four '
                     'cases from the unused second half of training. Price only the exact proof prefix. '
                     'Qualify the resulting nominee once on the original independent panel. Freeze both '
                     'rules on the same math trials and 26 language panels. Reproduce the math cost '
                     'frontiers and the language panels at their original common search cap.'}
    return plan, data, controls, baseline, report['results'], (lang_plan, panels, lang_report['cohorts'])


def measure_math(plan, cells, settings, group, width, controls, baseline, reference, mode):
    changes, never = Counter(), Counter()
    original = core.trial

    def trial(*args):
        before = prior.run_trial(*args[:-1], ())[:3]
        never.update(before[0])
        return paired_trial(args[:-1], WIDTHS[mode], before, changes)

    def existing(*args):
        return parent.run_trial(*args[:-1]) if args[-1] == parent.ORDERED else original(*args)

    anchors = {**controls, 'totals': {**controls['totals'], parent.ORDERED: baseline['anchors'][parent.ORDERED]}}
    with (patch.object(transfer, 'PRIMARY', mode), patch.object(transfer, 'METHODS', (mode, core.FIRST, parent.ORDERED)),
          patch.object(core, 'trial', existing), patch.object(transfer.parity.shortlist, 'trial', trial)):
        result = transfer.measure(plan, cells, settings, group, width, anchors)
    if (never != reference['totals'][prior.NEVER]
            or any(point != baseline['totals'][label] for label, point in result['totals'].items() if label != mode)
            or any(row[core.FIRST] != baseline['comparisons'][key][core.FIRST]
                   for key, row in result['comparisons'].items())):
        raise ValueError('The original math decisions, costs and GEPA frontier must reproduce')
    return {'totals': result['anchors'][mode], 'pairedChanges': changes,
            'comparisons': {key: value[mode] for key, value in result['comparisons'].items()}}


def language_ranges(vectors, controls, plan):
    rng = Random(plan['bootstrapSeed'])
    samples = {(mode, control): [] for mode in WIDTHS for control in controls}
    for _ in range(plan['bootstrapDraws']):
        scores = Counter()
        for subject in sorted(vectors):
            panel = vectors[subject]
            size = len(panel[prior.NEVER])
            weights = tuple(Counter(rng.randrange(size) for _ in range(size)).items())
            for mode, values in panel.items():
                scores[mode] += sum(values[case] * count for case, count in weights)
        for (mode, control), values in samples.items():
            values.append(scores[mode] - scores[control])
    return {mode: {control: math.interval(samples[mode, control]) for control in controls} for mode in WIDTHS}


def replay_language(plan, panels, reference):
    native = (*language.CONTROL_NAMES.values(), 'retain-start')
    methods = (prior.NEVER, *WIDTHS, *native)
    results, vectors, changes = {}, {}, {}
    for cohort, subject, model, matrix in panels:
        actual, scores = language.measure_panel(matrix, subject, plan)
        published = reference[cohort]['panels'][f'{subject}/{model}']['totals']
        if actual != published:
            raise ValueError('Language control trajectories must match their published panel digests')
        cells = {str(index): tuple((int(passed), None, False) for passed in vector) for index, vector in enumerate(matrix)}
        total = results.setdefault(cohort, {arm: Counter() for arm in methods})
        cohort_changes = changes.setdefault(cohort, {mode: Counter() for mode in WIDTHS})
        panels_by_subject = vectors.setdefault(cohort, {})
        by_case = panels_by_subject.setdefault(subject, {arm: [0] * len(scores[core.FIRST]) for arm in methods})
        for arm in native:
            total[arm].update({key: value for key, value in actual[arm].items() if key != 'traceSha256'})
            by_case[arm] = [old + new for old, new in zip(by_case[arm], scores[arm], strict=True)]
        for seed in plan['seeds']:
            start, roster, cohorts = language.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
            args = cells, start, roster, cohorts, seed, plan['searchCap']
            before = prior.run_trial(*args, ())[:3]
            observed = {prior.NEVER: before, **{mode: paired_trial(args, width, before, cohort_changes[mode])
                                                for mode, width in WIDTHS.items()}}
            for arm, (point, _, grades) in observed.items():
                total[arm].update(point)
                by_case[arm] = [old + new for old, new in zip(by_case[arm], grades, strict=True)]
    for cohort, total in results.items():
        if any(total[arm]['holdoutPasses'] != sum(sum(panel[arm]) for panel in vectors[cohort].values()) for arm in methods):
            raise ValueError('Language control scores and subject vectors must reconcile')
    return {cohort: {'totals': total, 'pairedChanges': changes[cohort],
                     'pairedRangesAtCommonSearchCap': language_ranges(vectors[cohort], (prior.NEVER, *native), plan)}
            for cohort, total in results.items()}


def replay(plan, data, controls, baseline, reference, language_inputs):
    results = {}
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        results[dataset] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                name = f'{group}/{width}'
                results[dataset][name] = {mode: measure_math(plan, cells, settings, group, width, controls[dataset][name],
                                                               baseline[dataset][name], reference[dataset][name], mode)
                                          for mode in WIDTHS}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'math': results, 'language': replay_language(*language_inputs)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
