"""Buy the incumbent's evidence before running the same paid-repair screen."""

import argparse
from collections import Counter
from dataclasses import replace
from functools import partial
from hashlib import sha256
import json
from pathlib import Path

from benchmarks import paid_validation_agreement as previous
from benchmarks.validation_repair_anchor import gepa_bounds
from cpo._contract import digest
from cpo.certified_shared_validation_cycle import SCHEDULES
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run


prior = previous.prior
REFERENCE = 'docs/paid-validation-agreement-results-v1.json'
REFERENCE_SHA = '1661ef5380888d37fa2aff1c339d3ba1541899591dd895aadac0e46067055ebe'


def incumbent_first_screen(incumbent, candidates, rows, evaluate, cap):
    widths = SCHEDULES['wide']
    shared_rows = rows[:len(widths)]
    full_charge = sum(1 + min(len(candidates), width) for width in widths[:len(shared_rows)])
    ordinary = partial(previous.guarded_screen, seek=False)
    if not candidates or cap < full_charge or any(row.critical for row in rows):
        return ordinary(incumbent, candidates, rows, evaluate, cap)

    prepaid = {}
    for row in shared_rows:
        observation = evaluate(incumbent, row)
        if type(observation.passed) is not bool:
            raise ValueError('Validation requires exact boolean replies')
        prepaid[row.id] = observation
        if not observation.passed:
            break
    else:
        return FinalistResult(incumbent, None, len(prepaid)), None

    paid = len(prepaid)

    def observe(prompt, row):
        nonlocal paid
        if prompt == incumbent and row.id in prepaid:
            return prepaid[row.id]
        paid += 1
        return evaluate(prompt, row)

    result, evidence = ordinary(incumbent, candidates, rows, observe, cap)
    return replace(result, evaluations=paid), evidence


def prepare():
    parent, panels, controls, references, _ = previous.prepare()
    read = prior.paired.frontier.cost.prior.baseline.read_reference
    receipt = read(REFERENCE, REFERENCE_SHA, parent)['results']
    plan = {**parent, 'protocol': 'incumbent-first-paid-repair-v1', 'parentPlanSha256': digest(parent),
            'paidRepairReceiptSha256': REFERENCE_SHA, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Preserve the paid-repair qualification rule and every admitted finalist. With enough '
                     'budget to fund all possible shared rounds, evaluate the incumbent on the same shared '
                     'case prefix through its first miss. Reject immediately if there can be no repair. '
                     'Otherwise reuse the exact prepaid replies in the original screen. Preserve the '
                     'original path on critical panels and narrower budgets. Charge every physical reply.',
            'gate': 'Every admission, independent qualification receipt and held-out grade must reproduce. '
                    'Measure per-cohort search savings and increases at both qualification margins, and '
                    'compare the same GEPA menu at the new realized budgets.'}
    return plan, panels, controls, references, receipt


def compare_trial(cells, start, roster, roles, seed, cap, gain):
    run = prior.paired.cycle.execute_path
    args = cells, start, roster, roles, seed, cap, gain
    guarded = partial(_run, screen=partial(previous.guarded_screen, seek=False))
    candidate = partial(_run, screen=incumbent_first_screen)
    old, old_ledger = run(guarded, *args)
    new, new_ledger = run(candidate, *args)
    if (old.search.prompt, old.search.finalist, old.qualification) != (
        new.search.prompt, new.search.finalist, new.qualification
    ):
        raise ValueError('Admission, deployment and the qualification receipt must reproduce exactly')
    for role, prompt, _ in new_ledger.keys() - old_ledger.keys():
        if role != 'validation' or prompt != start:
            raise ValueError('Only an incumbent validation prepayment may be new')
    before, old_grades, old_path = prior.paired.reference.point(cells, roles[-1], old, old_ledger)
    after, new_grades, new_path = prior.paired.reference.point(cells, roles[-1], new, new_ledger)
    if old_grades != new_grades:
        raise ValueError('Every individual held-out grade must reproduce')
    saved = before['paidLookups'] - after['paidLookups']
    point = {'holdoutPasses': before['holdoutPasses'], 'oldLookups': before['paidLookups'],
             'incumbentFirstLookups': after['paidLookups'], 'oldSearchLookups': old.search.evaluations,
             'incumbentFirstSearchLookups': new.search.evaluations, 'deployments': int(new.promoted), 'paths': 1,
             'pathsSavingLookups': int(saved > 0), 'pathsAddingLookups': int(saved < 0),
             'savedLookupCount': max(0, saved), 'addedLookupCount': max(0, -saved)}
    return point, old_path, new_path


def measure(panels, plan, controls, reference, receipt):
    totals = {label: Counter() for label in controls.values()}
    retained = 0
    panel_paths = {}
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        traces = {label: ([], []) for label in controls.values()}
        for seed in plan['seeds']:
            start, roster, roles = prior.paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            retained += sum(cells[start][case] for case in roles[-1])
            for gain, label in controls.items():
                point, old, fresh = compare_trial(cells, start, roster, roles, seed, plan['fullRosterCap'], gain)
                totals[label].update(point)
                traces[label][0].append(old)
                traces[label][1].append(fresh)
        name = f'{subject}/{model}'
        panel_paths[name] = {}
        for label, (old, fresh) in traces.items():
            if digest(old) != receipt['traceHashes'][name][label][previous.PAID]:
                raise ValueError('Every paid-repair comparison path must match the sealed predecessor')
            panel_paths[name][label] = digest(fresh)

    for label, totals_at_margin in totals.items():
        original = receipt['comparisons'][label][previous.PAID]
        if (totals_at_margin['holdoutPasses'], totals_at_margin['oldLookups'], totals_at_margin['oldSearchLookups']) != (
            original['holdoutPasses'], original['paidLookups'], original['searchLookups']
        ):
            raise ValueError('The archived result must reproduce before repricing')
        budget = totals_at_margin['incumbentFirstLookups']
        totals_at_margin['splitSafeGepaBounds'] = gepa_bounds(reference['comparisons'], retained, budget)
    return {'comparisons': totals, 'incumbentFirstPanelPaths': panel_paths}


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
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh output path')
    results = {name: measure(panels[name], plan, controls, reference, receipt[name])
               for name, reference in references.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results}, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
