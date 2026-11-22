"""Test whether paid validation can select a regression-free qualification guard."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import regression_free_qualification_replay as protected
from cpo import deferred_certificate_cycle as ordinary
from cpo._contract import digest
from cpo.regression_free_qualification import certify_regression_free_qualification


guard, cycle, frontier = protected.prior, protected.cycle, protected.frontier
RECEIPT = 'docs/regression-free-qualification-results-v1.json'
RECEIPT_SHA256 = '7d76ffee3205d12e494b00e069b2c7c5c81e60a627262c8d679e624d306f7990'
ONE, ALWAYS = 'cap-19/gain-1', guard.NO_REGRESSION
OBSERVED = 'guard-after-observed-regression'
UNVERIFIED = 'guard-unless-preservation-proved'
ROUTES = (OBSERVED, UNVERIFIED)
FINISH = ordinary._finish


def prepare():
    parent, groups, baseline, ceilings, native = protected.prepare()
    read = frontier.cost.prior.baseline.read_reference
    receipt = read(RECEIPT, RECEIPT_SHA256, parent)
    paths = (Path(__file__), Path(protected.__file__), Path(ordinary.__file__),
             guard.ROOT / 'cpo/regression_free_qualification.py')
    plan = {**parent, 'protocol': 'deferred-certificate-guard-routing-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': RECEIPT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'scope': 'Keep the original validation search, one-gain precheck and nominees. '
                     'Use the regression-free exact proof after observing any paid validation loss, '
                     'or whenever the validation certificate has not proved preservation. '
                     'Compare both routes with both fixed proof policies, rerun all published paths, '
                     'and use matching GEPA budget bounds from the sealed archives.',
            'gate': 'Use at most the cheaper fixed policy’s lookups with a nonnegative lower paired '
                    '95% endpoint against both fixed policies on the same cohort.'}
    return plan, groups, baseline, receipt['results'], ceilings, native


def validation_status(incumbent, nominee, grades):
    retained_passes = [row for (prompt, row), passed in grades.items() if prompt == incumbent and passed]
    paired = [grades.get((nominee, row)) for row in retained_passes]
    if False in paired:
        return 'observed-regression'
    if None in paired:
        return 'unverified-preservation'
    return 'preserved'


def guard_needed(policy, status):
    if policy == OBSERVED:
        return status == 'observed-regression'
    return status != 'preserved'


def run_routed(arguments, policy):
    def routed(incumbent, roster, validation, qualification, evaluate, *, qualify, **settings):
        grades = {}

        def observe(prompt, row):
            reply = evaluate(prompt, row)
            grades[prompt, row.id] = reply.passed
            return reply

        def finish(start, nominee, rows, read, history, counts, minimum, seed):
            if minimum != 1:
                raise ValueError('This route compares one-gain qualification rules')
            status = validation_status(start, nominee, grades)
            if guard_needed(policy, status):
                return certify_regression_free_qualification(
                    start, nominee, rows, qualify,
                    incumbent_prefix=tuple(reply.passed for reply in history), validation_counts=counts, seed=seed,
                )
            return FINISH(start, nominee, rows, read, history, counts, minimum, seed)

        with patch.object(ordinary, '_finish', finish):
            return ordinary.run_deferred_certificate_cycle(
                incumbent, roster, validation, qualification, observe, qualify=qualify, **settings,
            )

    return cycle.execute_path(routed, *arguments)


def measure_cohort(panels, plan, baseline, guarded, ceilings, native):
    totals, subjects, fingerprints = {}, {}, {}
    strata = {}
    labels = (ONE, ALWAYS, *ROUTES)
    for subject, model, matrix in panels:
        cells = {str(i): tuple(map(int, row)) for i, row in enumerate(matrix)}
        paths = {label: [] for label in labels}
        scores = subjects.setdefault(subject, {})
        for seed in plan['seeds']:
            start, roster, roles = frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            args = cells, start, roster, roles, seed, plan['fullRosterCap'], 1
            one, one_paid = cycle.execute_path(ordinary.run_deferred_certificate_cycle, *args)
            fixed, fixed_paid = cycle.execute_path(protected.optimized, *args)
            grades = {(prompt, row): passed for (role, prompt, row), passed in one_paid.items()
                      if role == 'validation'}
            status = 'no-nominee' if one.search.prompt == start else validation_status(start, one.search.prompt, grades)
            outcomes = {ONE: (one, one_paid), ALWAYS: (fixed, fixed_paid)}
            for label in ROUTES:
                actual = run_routed(args, label)
                expected = outcomes[ALWAYS] if status != 'no-nominee' and guard_needed(label, status) else outcomes[ONE]
                if actual[0] != expected[0] or list(actual[1].items()) != list(expected[1].items()):
                    raise ValueError('A routed proof must reproduce the exact selected fixed-policy path')
                outcomes[label] = actual

            for label, (result, paid) in outcomes.items():
                point, held, path = guard.point(cells, roles[-1], result, paid)
                totals.setdefault(label, Counter()).update(point)
                frontier.transfer.fitted.prior.add_vector(scores.setdefault(label, [0] * len(held)), held)
                paths[label].append(path)
            delta = sum(cells[fixed.prompt][case] - cells[one.prompt][case] for case in roles[-1])
            strata.setdefault(status, Counter()).update(
                paths=1, changedDeployments=int(one.prompt != fixed.prompt), passDifference=delta,
                lookupDifference=len(fixed_paid) - len(one_paid),
            )
        panel = f'{subject}/{model}'
        fingerprints[panel] = {label: digest(traces) for label, traces in paths.items()}
        if (fingerprints[panel][ONE] != baseline['panelPathHashes'][panel][ONE]
                or fingerprints[panel][ALWAYS] != guarded['panelPathHashes'][panel]):
            raise ValueError('The original ordinary and guarded callback fingerprints must match')

    seeded, expected_guard = baseline['totals'][ONE], guarded['totals']
    if (totals[ONE] != seeded
            or totals[ALWAYS] != {'holdoutPasses': expected_guard['holdoutPasses'],
                                  'paidLookups': expected_guard['optimizedLookups']}):
        raise ValueError('The ordinary and guarded budget and scores must reproduce')
    comparisons = {}
    for label in ROUTES:
        point = totals[label]
        effects = {control: cycle.route.published.paired_effect(subjects, label, control, plan)
                   for control in (ONE, ALWAYS)}
        chosen = [delta for status, delta in strata.items() if status != 'no-nominee' and guard_needed(label, status)]
        if (point['holdoutPasses'] != seeded['holdoutPasses'] + sum(row['passDifference'] for row in chosen)
                or point['paidLookups'] != seeded['paidLookups'] + sum(row['lookupDifference'] for row in chosen)
                or any(row['holdoutPassDifference'] != point['holdoutPasses'] - totals[control]['holdoutPasses']
                       for control, row in effects.items())):
            raise ValueError('Changes in cost and score must come from routed trials')
        coverage = point['paidLookups'] <= min(totals[ONE]['paidLookups'], totals[ALWAYS]['paidLookups'])
        comparisons[label] = {
            'pairedAgainstFixed': effects, 'guardedPaths': sum(row['paths'] for row in chosen),
            'passedGate': coverage and all(row['pairedRange95'][0] >= 0 for row in effects.values()),
            'subjectHindsightBounds': guard.hindsight_bounds(native, ceilings['comparisons'], point['paidLookups']),
        }
    return {'totals': totals, 'comparisons': comparisons, 'strata': strata, 'panelPathHashes': fingerprints}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, baseline, guard_receipt, ceilings, native = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh output path')
    results = {name: measure_cohort(panels, plan, baseline[name], guard_receipt[name], ceilings[name], native[name])
               for name, panels in groups.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results}, out,
                  indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
