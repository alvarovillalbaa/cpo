"""Find a training-supported validation nominee before independent qualification."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_adaptive_certificate_race as prior
from cpo._contract import digest
from cpo.expected_qualification import _pass_rate


transfer, math, core = prior.transfer, prior.math, prior.core
REFERENCE = 'docs/recorded-adaptive-certificate-race-results-v1.json'
REFERENCE_SHA256 = 'ac3dd8c6cc869481ec083768f08bbd21519f6e236df1e017f77b79ee5cf535ee'
VALIDATION_FIRST = 'joint-race-validation-first'
ADAPTIVE_ORDER = 'joint-race-adaptive-order'
MODES = (VALIDATION_FIRST, ADAPTIVE_ORDER)


def panel_order(quotes, mode):
    """With two unresolved proofs, prefer lower expected reads per chance of rejection."""
    (probability_v, reads_v, _), (probability_t, reads_t, _) = quotes
    if reads_v == 0 or (mode == ADAPTIVE_ORDER and reads_t > 0
                         and reads_t * (1 - probability_v) < reads_v * (1 - probability_t)):
        return 1, 0
    return 0, 1


def race(incumbent, roster, validation, training, observe, ledger, *, cap, mode, audit):
    panels = validation, training
    if not roster or not all(panels) or sum(map(len, panels)) > cap:
        return None
    case_hits, case_reads = Counter(), Counter()
    prompt_hits, prompt_reads = Counter(), Counter()

    def buy(panel, prompt, row):
        grade = observe(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Both certificates require exact boolean grades')
        case_hits[row.id] += grade
        case_reads[row.id] += 1
        prompt_hits[panel, prompt] += grade
        prompt_reads[panel, prompt] += 1
        audit['trainingReads' if panel else 'validationReads'] += 1
        return grade

    base = {row.id: buy(0, incumbent, row) for row in validation}
    if all(base.values()):
        return None
    protected = ({row.id for row in validation if row.critical and base[row.id]}, set())
    for row in training:
        buy(1, incumbent, row)
    targets = tuple(prompt_hits[panel, incumbent] + 1 for panel in range(2))
    if targets[1] > len(training):
        audit['perfectTrainingStops'] += 1
        return None

    active = dict.fromkeys(roster)
    while active:
        order = [sorted(rows, key=lambda row: (row.id not in protected[panel],
                                              Fraction(case_hits[row.id] + 1, case_reads[row.id] + 2)))
                 for panel, rows in enumerate(panels)]
        choices = {}
        for prompt in tuple(active):
            quotes = []
            for panel, rows in enumerate(order):
                hits, reads = prompt_hits[panel, prompt], prompt_reads[panel, prompt]
                unread = [row for row in rows if (prompt, row.id) not in ledger]
                schedule = tuple((row.id in protected[panel], _pass_rate(case_hits[row.id] + hits,
                                                                       case_reads[row.id] + reads))
                                 for row in unread)
                probability, expected = prior.prospects(schedule, targets[panel] - hits)
                quotes.append((probability, expected, unread))
            if not all(probability for probability, _, _ in quotes):
                del active[prompt]
                continue
            if not any(expected for _, expected, _ in quotes):
                return prompt, prompt_reads[0, prompt]
            reserve = sum(len(unread) for _, expected, unread in quotes if expected)
            if len(ledger) + reserve > cap:
                del active[prompt]
                continue
            first, second = panel_order(quotes, mode)
            probability, expected, unread = quotes[first]
            probability_2, expected_2, _ = quotes[second]
            cost = (expected + probability * expected_2) / (probability * probability_2)
            choices[prompt] = cost, first, unread[0], quotes[0][1] > 0
        if not choices:
            return None
        selected = min(choices, key=lambda prompt: choices[prompt][0])
        _, panel, row, unproved_validation = choices[selected]
        if panel and unproved_validation:
            audit['trainingBeforeValidationCertificate'] += 1
        if not buy(panel, selected, row) and row.id in protected[panel]:
            del active[selected]
    return None


def run_trial(cells, start, roster, cohorts, seed, cap, mode):
    audit = Counter()

    def certificates(incumbent, candidates, rows, training, observe, ledger, cap):
        result = race(incumbent, candidates, rows, training, observe, ledger, cap=cap, mode=mode, audit=audit)
        if result is not None:
            yield result

    with (patch.object(core, 'certificates', certificates), patch.object(core.prior, 'can_defer', lambda *_: False),
          patch.object(core.backup, 'select_with_training', lambda _incumbent, first, *args, **kwargs: first)):
        point, trace, grades = core.trial(cells, start, roster, cohorts, seed, cap, core.FIRST)
    if (point['searchLookups'] > cap or point['qualificationLookups'] > 2 * len(cohorts[2])
            or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']
            or point['searchLookups'] != audit['trainingReads'] + audit['validationReads']):
        raise ValueError('Both search certificates and the independent proof must reconcile to the paid ledger')
    return {**point, **audit}, trace, grades


def prepare():
    inherited, data, controls, baseline = prior.prepare()
    report = transfer.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, inherited)
    plan = {**{key: inherited[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                               'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-joint-candidate-race-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': REFERENCE_SHA256, 'methods': (*MODES, prior.UNIT, core.FIRST, prior.prior.ORDERED),
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Fund strict validation and training certificates before nominating any candidate. '
                     'Read incumbent validation and its reserved training half up front. Rank candidates '
                     'by expected reads per joint certificate using paid outcomes and independent quarter-bin '
                     'probabilities. Compare validation-first within a candidate with dynamically ordering '
                     'the more economical rejecting proof first. Qualify one candidate on the unchanged '
                     'independent panel. Check the original realized GEPA costs.'}
    return plan, data, controls, baseline, report['results']


def measure(plan, cells, settings, group, width, controls, baseline, reference, mode):
    changes, prior_totals = Counter(), Counter()
    original = core.trial

    def trial(*args):
        before, old, old_grades = prior.run_trial(*args[:-1], prior.UNIT)
        point, trace, grades = run_trial(*args[:-1], mode)
        prior_totals.update(before)
        if trace[3] == old[3] and grades != old_grades:
            raise ValueError('Identical deployments must reproduce all held-out grades')
        delta = sum(grades) - sum(old_grades)
        changes.update(trials=1, changedNominations=int(trace[2] != old[2]), changedDeployments=int(trace[3] != old[3]),
                       holdoutPassDelta=delta, grossPassGain=max(delta, 0), grossPassLoss=max(-delta, 0),
                       lookupDelta=point['paidLookups'] - before['paidLookups'])
        if transfer.HISTORICAL in point:
            changes['historicalCostDeltaNanodollars'] += point[transfer.HISTORICAL] - before[transfer.HISTORICAL]
        return point, trace, grades

    ordered = prior.prior.ORDERED

    def existing(*args):
        return prior.prior.run_trial(*args[:-1]) if args[-1] == ordered else original(*args)

    anchors = {**controls, 'totals': {**controls['totals'], ordered: baseline['anchors'][ordered]}}
    with (patch.object(transfer, 'PRIMARY', mode), patch.object(transfer, 'METHODS', (mode, core.FIRST, ordered)),
          patch.object(core, 'trial', existing), patch.object(transfer.parity.shortlist, 'trial', trial)):
        result = transfer.measure(plan, cells, settings, group, width, anchors)
    expected = {name: value for name, value in reference[prior.UNIT]['totals'].items() if name != 'traceSha256'}
    if (prior_totals != expected
            or any(point != baseline['totals'][label] for label, point in result['totals'].items() if label != mode)
            or any(value[core.FIRST] != baseline['comparisons'][key][core.FIRST]
                   for key, value in result['comparisons'].items())):
        raise ValueError('The original certificate scores, comparisons and native frontiers must reproduce')
    return {'totals': result['anchors'][mode], 'pairedChangesVsAdaptiveValidation': changes,
            'comparisons': {key: value[mode] for key, value in result['comparisons'].items()}}


def replay(plan, data, controls, baseline, reference):
    results = {}
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        results[dataset] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                name = f'{group}/{width}'
                results[dataset][name] = {mode: measure(plan, cells, settings, group, width, controls[dataset][name],
                                                          baseline[dataset][name], reference[dataset][name], mode)
                                          for mode in MODES}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


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
