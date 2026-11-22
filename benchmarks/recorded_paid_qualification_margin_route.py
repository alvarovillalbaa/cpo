"""Test whether paid validation can select an independent qualification margin."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_qualification_margin_language_transfer as language
from cpo._contract import digest


matched, prior = language.matched, language.prior
cost, frontier = prior.cost, prior.frontier
LANGUAGE_RESULT = 'docs/recorded-qualification-margin-language-transfer-results-v1.json'
LANGUAGE_SHA256 = '48fbb94ac5e99fa020a867d3642bba2c35f4456d2ad14e9dbad5795a9ad345be'
ONE, TWO = prior.BASELINE, prior.CANDIDATE
REGRESSION = 'two-gains-after-paid-regression'
HIGH_INCUMBENT = 'two-gains-after-four-incumbent-passes'
ROUTES = (REGRESSION, HIGH_INCUMBENT)


def prepare():
    mmlu, groups, _, _, margins = matched.prepare()
    transfer, languages = language.prepare()
    read = cost.prior.baseline.read_reference
    mmlu_results = read(language.PARENT_REPORT, language.PARENT_SHA256, mmlu)['results']
    language_results = read(LANGUAGE_RESULT, LANGUAGE_SHA256, transfer)['results']
    settings = ('caseCounts', 'seeds', 'challengers', 'searchCap', 'minimumSearchCap', 'gepaVersion',
                'bootstrapSeed', 'bootstrapDraws')
    if any(mmlu[key] != transfer[key] for key in settings):
        raise ValueError('The original case, seed and budget schedules must agree')
    paths = (Path(__file__), Path(prior.__file__), Path(language.__file__))
    plan = {**{key: mmlu[key] for key in settings}, 'protocol': 'recorded-paid-qualification-margin-route-v1',
            'mmluReceiptSha256': language.PARENT_SHA256, 'languageReceiptSha256': LANGUAGE_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'screenCap': transfer['screenCap'], 'policies': (ONE, TWO, *ROUTES),
            'scope': 'Keep every original cap-13 validation nominee and vary only the independent '
                     'qualification margin. Require two gains after an observed regression, or after '
                     'the incumbent scores at least four on its six paid validation cases. Compare '
                     'each rule with fixed margins using paired held-out case resampling. Report the '
                     'strongest measured affordable native point descriptively from the sealed curves. '
                     'Both rules reuse these previously scored archive cohorts.'}
    anchors = {cohort: results['totals'] for cohort, results in {**mmlu_results, **language_results}.items()}
    for cohort, row in margins.items():
        anchors[cohort] = {**anchors[cohort], ONE: row['totals'][ONE]}
    return plan, {**groups, **languages}, anchors


def use_two(policy, incumbent, nominee, rows, ledger):
    if nominee == incumbent:
        return False
    if policy == REGRESSION:
        return any((nominee, row.id) in ledger and ledger[incumbent, row.id].passed
                   and not ledger[nominee, row.id].passed for row in rows)
    if policy == HIGH_INCUMBENT:
        return sum(ledger[incumbent, row.id].passed for row in rows) >= 4
    raise ValueError('Unknown paid validation route')


def routed_trial(args, policy, cap):
    two_gains = False
    original = prior.early.select
    one_gain = prior.adapter.qualify_with_prefix

    def search(incumbent, candidates, rows, observe, ledger, **settings):
        nonlocal two_gains
        nominee = original(incumbent, candidates, rows, observe, ledger, **settings)
        two_gains = use_two(policy, incumbent, nominee, rows, ledger)
        return nominee

    def qualify(*args):
        return (prior.minimum_two if two_gains else one_gain)(*args)

    with (patch.object(prior.early, 'select', search),
          patch.object(prior.adapter, 'qualify_with_prefix', qualify)):
        result = prior.early.trial(args, 'complete-panel', cap)
    return result, two_gains


def measure_panel(subject, matrix, plan):
    cells = {str(index): tuple((int(passed), None, False) for passed in row) for index, row in enumerate(matrix)}
    totals, vectors, counts = {}, {}, {label: Counter() for label in ROUTES}
    traces = {label: [] for label in plan['policies']}
    for seed in plan['seeds']:
        start, roster, cohorts = prior.transfer.fixed.archive.transfer.schedule(
            subject, len(matrix[0]), len(matrix), seed, plan)
        args = cells, start, roster, cohorts, seed
        one = prior.early.trial(args, 'complete-panel', plan['screenCap'])
        with patch.object(prior.adapter, 'qualify_with_prefix', prior.minimum_two):
            two = prior.early.trial(args, 'complete-panel', plan['screenCap'])
        if one[1][:3] != two[1][:3] or one[0]['searchLookups'] != two[0]['searchLookups']:
            raise ValueError('Both qualification margins must keep the exact validation nominee and search cost')
        outcomes = {ONE: one, TWO: two}
        for label in ROUTES:
            result, stronger = routed_trial(args, label, plan['screenCap'])
            if result != (two if stronger else one):
                raise ValueError('The route must reproduce its chosen independent proof path exactly')
            counts[label].update(nominationsUsingTwo=int(stronger),
                                 changedDeployments=int(result[1][3] != one[1][3]),
                                 promotions=int(result[1][3] != start))
            outcomes[label] = result
        for label, (point, trace, grades, _) in outcomes.items():
            totals.setdefault(label, Counter()).update({key: point[key] for key in cost.METRICS})
            prior.transfer.fixed.fitted.prior.add_vector(vectors.setdefault(label, [0] * len(grades)), grades)
            traces[label].append(trace)
    return totals, vectors, counts, {label: digest(trace) for label, trace in traces.items()}


def replay_cohort(panels, plan, anchor):
    totals, subjects, details = {}, {}, {}
    counts = {label: Counter() for label in ROUTES}
    for subject, model, matrix in panels:
        points, vectors, audit, traces = measure_panel(subject, matrix, plan)
        rows = subjects.setdefault(subject, {})
        for label, point in points.items():
            totals.setdefault(label, Counter()).update(point)
            grades = vectors[label]
            prior.transfer.fixed.fitted.prior.add_vector(rows.setdefault(label, [0] * len(grades)), grades)
        for label, details_by_route in audit.items():
            counts[label].update(details_by_route)
        details[f'{subject}/{model}'] = {'routeCounts': audit, 'traceSha256': traces}
    if any(totals[label] != anchor[label] for label in (ONE, TWO)):
        raise ValueError('Both fixed qualification margins must reproduce the published scores and costs')
    results = {}
    for label in ROUTES:
        metrics = totals[label]
        native = {name: point for name, point in anchor.items()
                  if (name.endswith(('/gain-1', '/gain-2')) or name == frontier.RETAIN)
                  and point['paidLookups'] <= metrics['paidLookups']}
        label_native = min(native, key=lambda name: (-native[name]['holdoutPasses'], native[name]['paidLookups'], name))
        comparisons = {}
        for control in (ONE, TWO):
            vectors = {subject: {ONE: rows[control], TWO: rows[label]} for subject, rows in subjects.items()}
            comparisons[control] = {
                **language.paired_effect(vectors, plan),
                'lookupDifference': metrics['paidLookups'] - totals[control]['paidLookups'],
            }
        results[label] = {'fixedMarginComparisons': comparisons,
                          'affordableNativePoint': {'setting': label_native, **native[label_native]}}
    return {'totals': totals, 'routes': counts, 'comparisons': results, 'panels': details,
            'caseVectorsSha256': digest(subjects)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, references = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    results = {cohort: replay_cohort(panels, plan, references[cohort]) for cohort, panels in groups.items()}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
