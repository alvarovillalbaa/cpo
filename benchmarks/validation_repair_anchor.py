"""Test shared validation anchored on an observed incumbent miss."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import certified_shared_validation as certified
from cpo._contract import digest
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run, _screen as strict_screen


prior = certified.prior
BASE = 'certified-wide'
METHODS = {'single-repair': 1, 'four-repair-cut': 4}
MMLU = ('earlier-screen-cohort', 'disjoint-transfer-cohort')
RECEIPT = 'docs/certified-shared-validation-results-v1.json'
RECEIPT_SHA = '2e358d1681804fc3987cae14272e9e6f2ba16c1624b26dfd4f1a1b0a76712241'


def repair_screen(incumbent, candidates, rows, evaluate, cap, *, repairs):
    if any(row.critical for row in rows):
        return strict_screen(incumbent, candidates, rows, evaluate, cap, expected=True)
    paid = 0

    def observe(prompt, row):
        nonlocal paid
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Validation requires exact boolean replies')
        paid += 1
        return grade

    for offset, witness in enumerate(rows):
        if not observe(incumbent, witness):
            break
    else:
        return FinalistResult(incumbent, None, paid), None

    roster = []
    for prompt in candidates[:cap - paid]:
        if observe(prompt, witness):
            roster.append(prompt)
            if len(roster) == repairs:
                break
    if not roster:
        return FinalistResult(incumbent, None, paid), None

    winner, base, score, measured = roster[0], 0, 1, 1
    extra = 1 if offset else 2
    if len(roster) > 1 and len(rows) > 1 and cap - paid >= len(roster) + extra - 1:
        # Favor an incumbent pass we already paid for. Reserve every challenger read.
        followup = rows[0] if offset else rows[1]
        base = 1 if offset else observe(incumbent, followup)
        measured = 2
        for prompt in roster:
            if observe(prompt, followup):
                winner, score = prompt, 2
                break
    return FinalistResult(winner, winner, paid), ((base, measured), (score, measured))


def prepare():
    parent, panels, controls, references = certified.prepare()
    read = prior.paired.frontier.cost.prior.baseline.read_reference
    receipt = read(RECEIPT, RECEIPT_SHA, parent)['results']
    plan = {**parent, 'protocol': 'validation-repair-anchor-v1', 'parentPlanSha256': digest(parent),
            'certifiedReceiptSha256': RECEIPT_SHA, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'repairs': METHODS, 'primary': 'four-repair-cut', 'primaryCohorts': MMLU,
            'scope': 'Open shared validation on the first paid incumbent miss. Compare the first repair '
                     'with a common second case among the first four repairs when it can be fully funded. '
                     'Use the incumbent precheck, original independent qualification and case splits. '
                     'Audit the recent certified-wide result and directly reproduce the published one-gain '
                     'split-safe GEPA winners on MMLU. Test fixed alternatives on all eight cohorts.',
            'gate': 'The primary policy must beat the affordable split-safe GEPA bound or equal its score '
                    'at lower cost on both MMLU cohorts at one gain. For a paired improvement claim, '
                    'the case-resampled lower endpoint against that control must be positive.'}
    return plan, panels, controls, references, receipt


def attaining_trial(setting, args):
    cells, start, roster, roles, seed = args
    if setting == prior.gepa.RETAIN:
        return start, tuple(cells[start][case][0] for case in roles[-1]), 0
    group, policy = setting.split(':', 1)
    mode, amount, rule = policy.split('/')
    arguments = prior.validation_width(args, prior.WIDTHS[group])
    cap = int(amount)
    with prior.split_safe_cache():
        point, trace, grades = prior.gepa.native_paths(arguments, mode, cap, cap)[rule][cap]
    return trace[3], grades, point['paidLookups']


def verify_witness(cells, start, roles, result, paid, gain):
    nominee = result.search.finalist
    if nominee is None:
        return
    passed = any(paid.get(('validation', start, str(case))) is False
                 and paid.get(('validation', nominee, str(case))) is True for case in roles[1])
    exact = sum(cells[nominee][case] - cells[start][case] for case in roles[2])
    if not passed or result.prompt != (nominee if exact >= gain else start):
        raise ValueError('Every nomination needs a paid paired repair and every deployment needs exact qualification')


def attribution(incumbent, old, native, cpo, gepa):
    if old.prompt == native:
        bucket = 'same-deployment'
    elif old.promoted:
        bucket = 'both-promoted' if incumbent != native else 'gepa-retained'
    elif not old.search.evaluations:
        bucket = 'precheck-stopped-cpo'
    elif old.search.finalist is None:
        bucket = 'no-cpo-nominee'
    else:
        bucket = 'cpo-proof-rejected'
    return bucket, {'paths': 1, 'gepaPassDifference': sum(gepa) - sum(cpo)}


def deployment_difference(base, candidate):
    if base.prompt == candidate.prompt:
        return 'same-deployment'
    if base.promoted and candidate.promoted:
        return 'both-promoted'
    return 'only-certified-promoted' if base.promoted else 'only-repair-policy-promoted'


def gepa_bounds(comparisons, retained, budget):
    attainable = [entry['splitSafeCombined']['holdoutPasses'] for entry in comparisons.values()
                  if entry['splitSafeCombined']['paidLookups'] <= budget]
    ceilings = [entry['splitSafeCombined']['holdoutPasses'] for entry in comparisons.values()
                if entry['cpo']['paidLookups'] >= budget]
    return {'lowerPasses': max([retained, *attainable]), 'upperPasses': min(ceilings, default=None)}


def measure(cohort, panels, plan, controls, reference, receipt):
    comparisons = reference['comparisons']
    one = comparisons[controls[1]]
    direct = cohort in MMLU
    totals, vectors = {}, {}
    native_by_subject, native_scores, breakdown, trace_hashes = {}, {}, {}, {}
    repair_breakdown = {label: {method: {} for method in METHODS} for label in controls.values()}
    retained = 0
    functions = {BASE: certified.certified.run_certified_shared_validation_cycle}
    functions.update({label: partial(_run, screen=partial(repair_screen, repairs=number))
                      for label, number in METHODS.items()})
    run = prior.paired.cycle.execute_path
    add = prior.paired.frontier.transfer.fitted.prior.add_vector
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        native_cells = {name: tuple((g, None, False) for g in row) for name, row in cells.items()}
        path = {label: {method: [] for method in functions} for label in controls.values()}
        for seed in plan['seeds']:
            start, roster, roles = prior.paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            retained += sum(cells[start][case] for case in roles[-1])
            for gain, label in controls.items():
                by_subject = vectors.setdefault(label, {}).setdefault(subject, {})
                for method, runner in functions.items():
                    result, paid = run(runner, cells, start, roster, roles, seed, plan['fullRosterCap'], gain)
                    point, grades, fingerprint = prior.paired.reference.point(cells, roles[-1], result, paid)
                    path[label][method].append(fingerprint)
                    totals.setdefault(label, {}).setdefault(method, Counter()).update(
                        **point, searchLookups=result.search.evaluations, qualificationLookups=result.qualification_evaluations,
                        nominees=int(result.search.finalist is not None), deployments=int(result.promoted),
                        openSearches=int(result.search.evaluations > 0),
                    )
                    add(by_subject.setdefault(method, [0] * len(grades)), grades)
                    if method == BASE:
                        base_result, base_point = result, point
                    else:
                        verify_witness(cells, start, roles, result, paid, gain)
                        bucket = deployment_difference(base_result, result)
                        repair_breakdown[label][method].setdefault(bucket, Counter()).update(
                            paths=1, passDifference=point['holdoutPasses'] - base_point['holdoutPasses'],
                            lookupDifference=point['paidLookups'] - base_point['paidLookups'],
                        )
                    if method == BASE and direct and gain == 1:
                        native, native_grades, native_cost = attaining_trial(
                            one['splitSafeCombined']['settingsBySubject'][subject],
                            (native_cells, start, roster, roles, seed),
                        )
                        if tuple(cells[native][case] for case in roles[-1]) != native_grades:
                            raise ValueError('The native deployment must match its complete held-out vector')
                        native_by_subject.setdefault(subject, Counter()).update(
                            holdoutPasses=sum(native_grades), paidLookups=native_cost,
                        )
                        add(native_scores.setdefault(subject, [0] * len(grades)), native_grades)
                        bucket, metrics = attribution(start, result, native, grades, native_grades)
                        breakdown.setdefault(bucket, Counter()).update(**metrics, gepaLookups=native_cost,
                                                                    certifiedLookups=point['paidLookups'])
        panel = f'{subject}/{model}'
        trace_hashes[panel] = {label: {method: digest(values) for method, values in traces.items()}
                               for label, traces in path.items()}
        for label, trace in trace_hashes[panel].items():
            if trace[BASE] != receipt['certifiedPanelPathHashes'][panel][label]:
                raise ValueError('The certified-wide paid paths must match before comparison')

    paired = prior.frozen.paired_effects.paired_effect
    for label, methods in totals.items():
        baseline = methods[BASE]
        original = receipt['comparisons'][label]
        if (baseline['holdoutPasses'], baseline['paidLookups']) != (original['holdoutPasses'], original['certifiedLookups']):
            raise ValueError('Original cost and quality must reproduce')
        for subject, grades in native_scores.items():
            vectors[label][subject]['attaining-gepa'] = grades
        for method, point in methods.items():
            point['gepaPassBoundsAtOwnBudget'] = gepa_bounds(comparisons, retained, point['paidLookups'])
            if method != BASE:
                point['pairedAgainstCertified'] = paired(vectors[label], method, BASE, plan)
                if sum(entry['passDifference'] for entry in repair_breakdown[label][method].values()) != (
                    point['holdoutPasses'] - baseline['holdoutPasses']
                ):
                    raise ValueError('The changed deployments must account for the full repair policy margin')
            if direct:
                point['pairedAgainstPublishedGepa'] = paired(vectors[label], method, 'attaining-gepa', plan)
    if direct:
        for subject, point in native_by_subject.items():
            if point != one['attainingSubjectPoints'][subject]:
                raise ValueError('Every native subject must reproduce its published exact cost and score')
        if sum(row['gepaPassDifference'] for row in breakdown.values()) != (
            one['splitSafeCombined']['holdoutPasses'] - totals[controls[1]][BASE]['holdoutPasses']
        ):
            raise ValueError('The deployment attribution must account for the entire native margin')
    return {'retainedStartPasses': retained, 'comparisons': totals, 'traceHashes': trace_hashes,
            'oneGainNativeBySubject': native_by_subject, 'certifiedWideVsPublishedGepa': breakdown,
            'repairVsCertifiedByDeployment': repair_breakdown}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels, controls, references, receipt = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh path and pinned GEPA')
    result = {cohort: measure(cohort, panels[cohort], plan, controls, reference, receipt[cohort])
              for cohort, reference in references.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': result}, out,
                  indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
