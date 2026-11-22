"""Test whether paid validation agreement should prevent qualification."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import validation_repair_anchor as previous
from cpo._contract import digest
from cpo.certified_shared_validation_cycle import _screen as certified_screen, SCHEDULES
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run


prior = previous.prior
BASE = previous.BASE
PAID, SPARE = 'require-paid-repair', 'seek-repair-in-spare-cap'
POLICIES = (BASE, PAID, SPARE)
RECEIPT = 'docs/validation-repair-anchor-results-v1.json'
RECEIPT_SHA = 'b4412eb9955fed5675855af7a8c98022c8e688c8fb4cf57b005425a3bffdf6e0'


def witnessed_repair(incumbent, nominee, ledger):
    return any(prompt == incumbent and grade is False and ledger.get((nominee, case)) is True
               for (prompt, case), grade in ledger.items())


def guarded_screen(incumbent, candidates, rows, evaluate, cap, *, seek):
    ledger = {}

    def observe(prompt, row):
        observation = evaluate(prompt, row)
        if type(observation.passed) is not bool:
            raise ValueError('Validation requires exact boolean replies')
        ledger[prompt, row.id] = observation.passed
        return observation

    result, counts = certified_screen(incumbent, candidates, rows, observe, cap, widths=SCHEDULES['wide'], margin=0)
    nominee = result.finalist
    if nominee is None or any(row.critical for row in rows) or witnessed_repair(incumbent, nominee, ledger):
        return result, counts
    if seek:
        for row in rows:
            if (incumbent, row.id) in ledger:
                continue
            if cap - len(ledger) < 2:
                break
            if not observe(incumbent, row).passed and observe(nominee, row).passed:
                return FinalistResult(nominee, nominee, len(ledger)), counts
    return FinalistResult(incumbent, None, len(ledger)), None


def prepare():
    parent, panels, controls, references, _ = previous.prepare()
    read = prior.paired.frontier.cost.prior.baseline.read_reference
    receipt = read(RECEIPT, RECEIPT_SHA, parent)['results']
    plan = {**parent, 'protocol': 'paid-validation-agreement-v1', 'parentPlanSha256': digest(parent),
            'repairAnchorReceiptSha256': RECEIPT_SHA, 'agreementSourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'policies': POLICIES, 'primary': SPARE, 'primaryCohorts': previous.MMLU,
            'scope': 'Preserve original certified-wide search, qualification prefix, finalist, and case assignments. '
                     'A finalist has evidence of repair if it passed a validation case the incumbent failed. '
                     'The paid-only policy blocks qualification without such evidence. The spare-cap policy can '
                     'seek the evidence on unused validation cases and preserves the original qualification order '
                     'on admission. Compare both margins and all eight cohorts. Replay the MMLU GEPA attainers.',
            'gate': 'The primary policy at one gain must achieve a positive paired lower endpoint against '
                    'certified wide on both MMLU cohorts, with no increase in lookups, and meet or beat the '
                    'published split-safe GEPA ceiling at its own cost.'}
    return plan, panels, controls, references, receipt


def audit_trial(start, baseline, before, result, after, policy):
    old_validation = [(key, grade) for key, grade in before.items() if key[0] == 'validation']
    new_validation = [(key, grade) for key, grade in after.items() if key[0] == 'validation']
    extra = new_validation[len(old_validation):]
    if new_validation[:len(old_validation)] != old_validation or (policy == PAID and extra):
        raise ValueError('The guarded policy must preserve the entire original search prefix')
    nominee = baseline.search.finalist
    repair = witnessed_repair(start, nominee, {(prompt, case): grade for (_, prompt, case), grade in old_validation})
    if result.search.finalist is not None:
        if (result.search.finalist != nominee or result.qualification != baseline.qualification
                or not witnessed_repair(start, nominee, {(prompt, case): grade
                                                        for (_, prompt, case), grade in new_validation})):
            raise ValueError('Admission must prove a repair and preserve the original nomination and exact proof')
    elif nominee is None:
        if result != baseline or after != before:
            raise ValueError('Paths without a finalist must stay identical')
    elif repair or result.promoted or any(reply.prompt != start for reply in result.qualification.observations):
        raise ValueError('Only an unsupported finalist may be blocked before reading its qualification')
    return {'paidWitness': int(repair), 'extensions': int(bool(extra)), 'extraSearchLookups': len(extra),
            'rescuedNominees': int(bool(extra) and result.search.finalist is not None),
            'blockedNominees': int(nominee is not None and result.search.finalist is None),
            'blockedPromotions': int(baseline.promoted and not result.promoted)}


def measure(cohort, panels, plan, controls, reference, receipt):
    comparisons = reference['comparisons']
    native = comparisons[controls[1]]
    direct = cohort in previous.MMLU
    totals, vectors, native_scores, native_points, panel_paths = {}, {}, {}, {}, {}
    strata = {label: {} for label in controls.values()}
    retained = 0
    run = prior.paired.cycle.execute_path
    add = prior.paired.frontier.transfer.fitted.prior.add_vector
    paired = prior.frozen.paired_effects.paired_effect
    runners = {BASE: previous.certified.certified.run_certified_shared_validation_cycle,
               PAID: partial(_run, screen=partial(guarded_screen, seek=False)),
               SPARE: partial(_run, screen=partial(guarded_screen, seek=True))}
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        native_cells = {name: tuple((g, None, False) for g in row) for name, row in cells.items()}
        paths = {label: {policy: [] for policy in POLICIES} for label in controls.values()}
        for seed in plan['seeds']:
            start, roster, roles = prior.paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            retained += sum(cells[start][case] for case in roles[-1])
            if direct:
                _, held, cost = previous.attaining_trial(native['splitSafeCombined']['settingsBySubject'][subject],
                                                         (native_cells, start, roster, roles, seed))
                native_points.setdefault(subject, Counter()).update(holdoutPasses=sum(held), paidLookups=cost)
                add(native_scores.setdefault(subject, [0] * len(held)), held)
            for gain, label in controls.items():
                by_subject = vectors.setdefault(label, {}).setdefault(subject, {})
                args = cells, start, roster, roles, seed, plan['fullRosterCap'], gain
                for policy, runner in runners.items():
                    result, ledger = run(runner, *args)
                    metrics, grades, path = prior.paired.reference.point(cells, roles[-1], result, ledger)
                    paths[label][policy].append(path)
                    add(by_subject.setdefault(policy, [0] * len(grades)), grades)
                    extra = {}
                    if policy == BASE:
                        base_result, base_ledger = result, ledger
                    else:
                        extra = audit_trial(start, base_result, base_ledger, result, ledger, policy)
                    totals.setdefault(label, {}).setdefault(policy, Counter()).update(
                        **metrics, **extra, searchLookups=result.search.evaluations,
                        qualificationLookups=result.qualification_evaluations, deployments=int(result.promoted),
                    )
                if base_result.promoted:
                    validation = {(prompt, case): grade for (role, prompt, case), grade in base_ledger.items()
                                  if role == 'validation'}
                    profile = 'has-paid-repair' if witnessed_repair(start, base_result.prompt, validation) else 'no-paid-repair'
                    diff = sum(cells[base_result.prompt][case] - cells[start][case] for case in roles[-1])
                    strata[label].setdefault(profile, Counter()).update(deployments=1, holdoutPassChange=diff,
                                                                      improved=int(diff > 0), regressed=int(diff < 0))
        panel = f'{subject}/{model}'
        panel_paths[panel] = {label: {policy: digest(path) for policy, path in methods.items()}
                              for label, methods in paths.items()}
        for label, methods in panel_paths[panel].items():
            if methods[BASE] != receipt['traceHashes'][panel][label][BASE]:
                raise ValueError('Every certified-wide path must match the prior trial')

    if direct and native_points != native['attainingSubjectPoints']:
        raise ValueError('The per-subject native scores and costs must reproduce')
    for label, methods in totals.items():
        for subject, grades in native_scores.items():
            vectors[label][subject]['published-gepa'] = grades
        for policy, point in methods.items():
            point['nativeBounds'] = previous.gepa_bounds(comparisons, retained, point['paidLookups'])
            if policy != BASE:
                point['pairedAgainstCertified'] = paired(vectors[label], policy, BASE, plan)
            if direct:
                point['pairedAgainstPublishedGepa'] = paired(vectors[label], policy, 'published-gepa', plan)
        if sum(s['holdoutPassChange'] for s in strata[label].values()) != methods[BASE]['holdoutPasses'] - retained:
            raise ValueError('The deployment strata must account for the full improvement over retention')
    return {'comparisons': totals, 'certifiedDeploymentStrata': strata, 'traceHashes': panel_paths,
            'publishedGepaBySubject': native_points, 'retainedPasses': retained}


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
    results = {name: measure(name, panels[name], plan, controls, reference, receipt[name])
               for name, reference in references.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
