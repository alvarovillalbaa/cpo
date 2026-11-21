"""Measure shorter validation allowances for the later-first certificate race."""

import argparse
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_certificate_head_to_head as previous, recorded_certificate_lookahead as baseline
from cpo._contract import digest


REFERENCE = 'docs/recorded-certificate-head-to-head-results-v1.json'
REFERENCE_SHA256 = 'f7b50260bd3104bbb7e5e1750dbe75c0e1c86dc92006db92b803a30a26cd55e3'
FULL = 'later-first-one-panel'
FIXED = {f'{size}-sixths-panel': size for size in range(1, 6)}
QUOTED = {'target-reads': 0, 'target-plus-one': 1}
ARMS = (FULL, *FIXED, *QUOTED)
BANDS = ('sameDeployment', 'better', 'worse', 'changedWithEqualScore')
METRICS = ('trials', 'heldoutPassDelta', 'paidLookupDelta', 'extraValidationLookups')


def search(arm, incumbent, first, roster, rows, training, observe, ledger, *, cap, extra):
    if arm in FIXED:
        extra = extra * FIXED[arm] // 6
    elif arm in QUOTED:
        target = sum(ledger[incumbent, row.id].passed for row in rows) + 2
        extra = min(extra, target + QUOTED[arm])
    return previous.search_later(incumbent, first, roster, rows, training, observe, ledger,
                                 cap=cap, extra=extra, paired=False)


def attribute(initial, observed):
    old, old_trace, old_grades = initial
    point, trace, grades = observed
    delta = point['holdoutPasses'] - old['holdoutPasses']
    if old_trace[3] == trace[3]:
        if grades != old_grades:
            raise ValueError('The same deployment must yield the same held-out grades')
        band = 'sameDeployment'
    else:
        band = 'better' if delta > 0 else 'worse' if delta < 0 else 'changedWithEqualScore'
    values = (1, delta, point['paidLookups'] - old['paidLookups'], point.get('extraValidationLookups', 0))
    return {f'{band}.{key}': value for key, value in zip(METRICS, values, strict=True)}


def prepare():
    earlier, parent, math_data, transfer_data, _ = previous.prepare()
    reference = baseline.read_reference(REFERENCE, REFERENCE_SHA256, earlier)
    plan = {'protocol': 'recorded-certificate-allowance-v1', 'parentPlanSha256': digest(earlier),
            'parentReceiptSha256': REFERENCE_SHA256, 'gepaVersion': parent['gepaVersion'],
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'fixedAllowancesInSixthsOfPanelWidth': FIXED, 'quoteSlackAboveIncumbentPlusTwo': QUOTED,
            'scope': 'Measure every shorter whole-read cap on six-case validation panels, the same fractions '
                     'rounded down on eight-case panels, and two caps tied to the incumbent score. Preserve '
                     'the later-first scheduler, training reserve, and one qualification attempt. Attribute '
                     'lookup and quality differences against the zero-lookahead first certificate. For a '
                     'passing transfer arm, repeat the paired comparison with each subject omitted.'}
    return plan, parent, math_data, transfer_data, reference


def omit_subjects(plan, cohort, panels, result, arm):
    transfer = baseline.transfer
    first = baseline.core.FIRST
    vectors = result['caseVectorsBySubject']
    comparisons = {}
    if len(vectors) < 2:
        return comparisons
    for excluded in vectors:
        removed = [result['panels'][f'{subject}/{model}']['totals']
                   for label, subject, model, _ in panels if label == cohort and subject == excluded]
        totals = {method: {key: result['totals'][method][key] - sum(panel[method][key] for panel in removed)
                           for key in ('holdoutPasses', 'paidLookups')}
                  for method in (arm, *transfer.CONTROL_NAMES.values())}
        paired = {subject: {**rows, first: rows[arm]} for subject, rows in vectors.items() if subject != excluded}
        verdict = transfer.compare(plan, {**totals, first: totals[arm]}, paired)
        comparisons[excluded] = {'totals': totals, **verdict}
    return comparisons


def execute(plan, parent, math_data, transfer_data, reference):
    first, first_trial, old_trial = baseline.core.FIRST, baseline.core.trial, baseline.trial

    def trial(*arguments):
        arm = arguments[-1]
        initial = first_trial(*arguments[:-1], first)
        with patch.object(baseline, 'search_for_stronger', partial(search, arm)):
            observed = old_trial(*arguments)
        point, trace, grades = observed
        return {**point, **attribute(initial, observed)}, trace, grades

    with (patch.object(baseline, 'LIMITS', dict.fromkeys(ARMS, 1)), patch.object(baseline, 'trial', trial)):
        full = baseline.replay(parent, math_data, transfer_data)

    def collect(result, published):
        totals = {arm: {key: value for key, value in result['totals'][arm].items() if '.' not in key}
                  for arm in ARMS}
        comparisons = {arm: result['comparisons'][arm] for arm in ARMS}
        if totals[FULL] != published['totals'][FULL] or comparisons[FULL] != published['comparisons'][FULL]:
            raise ValueError('The published full-panel reference must reproduce')
        start = result['totals'][first]
        attribution = {}
        for arm in ARMS:
            row = result['totals'][arm]
            groups = {band: {key: row.get(f'{band}.{key}', 0) for key in METRICS}
                      for band in BANDS if row.get(f'{band}.trials', 0)}
            if (sum(v['heldoutPassDelta'] for v in groups.values()) != row['holdoutPasses'] - start['holdoutPasses']
                    or sum(v['paidLookupDelta'] for v in groups.values()) != row['paidLookups'] - start['paidLookups']
                    or sum(v['extraValidationLookups'] for v in groups.values()) != row.get('extraValidationLookups', 0)):
                raise ValueError('Attribution must balance against the first-certificate control')
            attribution[arm] = groups
        return {'firstCertificate': start, 'totals': totals, 'comparisons': comparisons, 'attribution': attribution}

    math = {name: {setting: collect(result, reference['math'][name][setting]) for setting, result in groups.items()}
            for name, groups in full['math'].items()}
    transfer = {}
    for name, result in full['transfer'].items():
        recorded = collect(result, reference['transfer'][name])
        for arm, verdict in recorded['comparisons'].items():
            if verdict['gate'] == 'passed':
                verdict['withoutSubject'] = omit_subjects(parent, name, transfer_data[0], result, arm)
        transfer[name] = recorded
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'math': math, 'transfer': transfer}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, parent, math_data, transfer_data, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = execute(plan, parent, math_data, transfer_data, reference)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
