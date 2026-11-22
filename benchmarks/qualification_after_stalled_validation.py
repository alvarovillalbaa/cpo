"""Test one independent qualification after a bounded validation stall."""

import argparse
from collections import Counter
from fractions import Fraction
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import deferred_two_sided_certificate as previous
from benchmarks import qualification_precheck_extension as native
from cpo import Observation, Row
from cpo._contract import digest
from cpo.single_finalist import FinalistResult


paired, cycle, gepa = previous.paired, previous.cycle, native.gepa
REPORT = 'docs/deferred-two-sided-certificate-results-v1.json'
REPORT_SHA256 = 'b50173bfd6964cceb58ae34f8492fc1df00a70f7c25b1bee6ef46530a26de0c4'
COHORTS = ('BBH', 'earlier-screen-cohort', 'disjoint-transfer-cohort')
TIE, TRAINING = 'witnessed-validation-nonloss', 'disjoint-training-gain'
POLICIES = TIE, TRAINING


def prepare():
    parent, groups, controls, _, native_reference = previous.prepare()
    read = paired.frontier.cost.prior.baseline.read_reference
    earlier = read(REPORT, REPORT_SHA256, parent)['results']
    paths = (Path(__file__), Path(native.__file__), Path(gepa.__file__), Path(cycle.__file__))
    plan = {**parent, 'protocol': 'qualification-after-stalled-validation-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': REPORT_SHA256,
            'sourceSha256': {p.name: sha256(p.read_bytes()).hexdigest() for p in paths},
            'cohorts': COHORTS, 'methods': POLICIES, 'corroborationRows': 2,
            'scope': 'Keep the paid incumbent qualification precheck and entire strict two-sided search. '
                     'When it has no nominee, use the unspent search allowance to prove validation '
                     'nonloss for a challenger with a paid paired repair, or prove a strict gain on '
                     'the first two disjoint training cases for one eligible fallback. Protect critical '
                     'cases by keeping the original path for such panels. Independently qualify at most '
                     'one nominee. Compare with the full native GEPA menu at realized lookup budgets.'}
    return plan, groups, controls, earlier, native_reference


def certify_nonloss(rows, base, candidate, read, allowance):
    """Certify a scalar nonloss on a noncritical panel from partially observed grades."""
    width = len(rows)
    known = base, candidate
    for spent in range(allowance + 1):
        favorable = len(base) - sum(base.values()) + sum(candidate.values())
        unfavorable = len(base) + len(candidate) - favorable
        if favorable >= width:
            return True
        if unfavorable > width or width - favorable > allowance - spent:
            return False
        row, side = cycle._next_expected(rows, known, (), favorable)
        known[side][row.id] = read(side, row)
    raise RuntimeError('The validation evidence must settle or exhaust the allowance')


def rescue_screen(incumbent, candidates, rows, evaluate, cap, *, policy, training, observe_training):
    paid = {prompt: {} for prompt in (incumbent, *candidates)}
    spent = 0

    def validation_read(prompt, row):
        nonlocal spent
        reply = evaluate(prompt, row)
        if row.id in paid[prompt] or type(reply.passed) is not bool:
            raise ValueError('The fallback requires unique exact validation replies')
        paid[prompt][row.id] = reply.passed
        spent += 1
        return reply

    original, counts = cycle._screen(incumbent, candidates, rows, validation_read, cap, expected=True)
    if original.finalist is not None or spent >= cap or any(row.critical for row in rows):
        return original, counts
    base = paid[incumbent]
    roster = candidates[:max(0, cap - 2 * len(rows) + 1)]

    def result(prompt):
        ledger = paid[incumbent], paid[prompt]
        return FinalistResult(prompt, prompt, spent), tuple((sum(seen.values()), len(seen)) for seen in ledger)

    if policy == TIE:
        def count_favorable(prompt):
            return len(base) - sum(base.values()) + sum(paid[prompt].values())

        eligible = [prompt for prompt in roster
                    if any(passed and base.get(case) is False for case, passed in paid[prompt].items())]
        for prompt in sorted(eligible, key=count_favorable, reverse=True):
            pair = incumbent, prompt
            if certify_nonloss(rows, base, paid[prompt], lambda side, row: validation_read(pair[side], row).passed,
                               cap - spent):
                return result(prompt)
    else:
        def quality(prompt):
            observed = paid[prompt]
            paired_gain = sum(observed[case] - base[case] for case in observed.keys() & base.keys())
            return paired_gain, Fraction(sum(observed.values()) + 1, len(observed) + 2), len(observed)

        training_base = {}
        for prompt in sorted(roster, key=quality, reverse=True):
            pair = incumbent, prompt

            def read(side, row):
                nonlocal spent
                grade = observe_training(pair[side], row)
                if type(grade) is not bool:
                    raise ValueError('Training corroboration requires exact boolean replies')
                spent += 1
                return grade

            if cycle._certify(training, training_base, {}, read, cap - spent, expected=True):
                return result(prompt)
    return FinalistResult(incumbent, None, spent), None


def execute_trial(cells, start, roster, roles, seed, cap, gain, policy):
    training, validation, qualification = (tuple(Row(str(case), label) for case in cases)
                                           for label, cases in zip(('training', 'validation', 'qualification'),
                                                                   roles[:3], strict=True))
    paid = {}

    def observe(role, prompt, row):
        key = role, prompt, row.id
        if key in paid:
            raise ValueError('Each role-scoped reply may be purchased once')
        paid[key] = bool(cells[prompt][int(row.id)])
        return paid[key]

    search = partial(rescue_screen, policy=policy, training=training[:2],
                     observe_training=partial(observe, 'training'))
    result = cycle._run(start, roster, validation, qualification,
                        lambda prompt, row: Observation(observe('validation', prompt, row), {}),
                        metric_limit=cap, qualify=lambda prompt, row, _: observe('qualification', prompt, row),
                        minimum_gain=gain, seed=seed, screen=search)
    if (result.search.evaluations != sum(role != 'qualification' for role, _, _ in paid)
            or result.search.evaluations > cap or result.qualification_evaluations > 2 * len(qualification)
            or len(paid) != result.search.evaluations + result.qualification_evaluations):
        raise ValueError('Training and validation must fit one search allowance and separate qualification')
    return result, paid


def classify_headroom(cells, start, roster, roles, gain):
    training, validation, qualification, holdout = roles
    promising = [name for name in roster
                 if sum(cells[name][case] - cells[start][case] for case in qualification) >= gain
                 and sum(cells[name][case] - cells[start][case] for case in holdout) > 0]
    tiers = Counter()
    tiers['betterIndependentlyQualified'] = bool(promising)
    for prompt in promising:
        replies = [cells[prompt][case] - cells[start][case] for case in validation]
        if sum(replies) > 0:
            tiers['strictValidationAvailable'] = 1
        if sum(replies) == 0 and 1 in replies:
            tiers['witnessedTieAvailable'] = 1
        if sum(cells[prompt][case] - cells[start][case] for case in training[:2]) > 0:
            tiers['trainingGainAvailable'] = 1
    return tiers


def measure(panels, plan, controls, earlier, native_reference):
    totals = {label: {method: Counter() for method in POLICIES} for label in controls.values()}
    headroom = {label: Counter() for label in controls.values()}
    subjects, fingerprints = {}, {}
    low, high, cap = plan['minimumSearchCap'], plan['searchCap'], plan['fullRosterCap']
    for subject, model, matrix in panels:
        cells = {str(i): tuple(map(int, row)) for i, row in enumerate(matrix)}
        native_cells = {name: tuple((grade, None, False) for grade in row) for name, row in cells.items()}
        by_subject = subjects.setdefault(subject, {})
        traces = {label: {method: [] for method in (previous.EXPECTED, *POLICIES)} for label in controls.values()}
        deltas = {}
        for seed in plan['seeds']:
            start, roster, roles = paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            by_subject.setdefault(gepa.RETAIN, Counter()).update(
                holdoutPasses=sum(cells[start][case] for case in roles[-1]), paidLookups=0,
            )
            for gain, label in controls.items():
                args = cells, start, roster, roles, seed, cap, gain
                before, old = previous.run_trial(previous.EXPECTED, args)
                anchor, _, path = paired.reference.point(cells, roles[-1], before, old)
                traces[label][previous.EXPECTED].append(path)
                if before.search.finalist is None and before.search.evaluations:
                    headroom[label]['stalledTrials'] += 1
                    headroom[label].update(classify_headroom(cells, start, roster, roles, gain))
                for method in POLICIES:
                    result, paid = execute_trial(*args, method)
                    search = result.search
                    if before.search.finalist is not None or before.search.evaluations == 0:
                        if before != result or list(old.items()) != list(paid.items()):
                            raise ValueError('The original nominee and closed precheck paths must be exact')
                    if list(paid.items())[:len(old)] != list(old.items()):
                        raise ValueError('The original paid path must remain a prefix')
                    nominee = search.prompt
                    gain_on = lambda cases: sum(cells[nominee][case] - cells[start][case] for case in cases)
                    rescued = before.search.finalist is None and search.finalist is not None
                    if rescued and method == TIE and (gain_on(roles[1]) < 0 or not any(
                        old.get(('validation', nominee, str(case))) is True
                        and old.get(('validation', start, str(case))) is False for case in roles[1]
                    )):
                        raise ValueError('A nonloss fallback must preserve validation and have a paid repair')
                    if rescued and method == TRAINING and gain_on(roles[0][:2]) <= 0:
                        raise ValueError('A training fallback must have a strict gain on the corroboration cases')
                    if result.prompt != (nominee if gain_on(roles[2]) >= gain else start):
                        raise ValueError('Every deployment must pass the original independent gate')
                    point, _, path = paired.reference.point(cells, roles[-1], result, paid)
                    totals[label][method].update(
                        **point, extraLookups=point['paidLookups'] - anchor['paidLookups'],
                        extraPasses=point['holdoutPasses'] - anchor['holdoutPasses'],
                        rescuedNominees=int(rescued), rescuedDeployments=int(rescued and result.promoted),
                    )
                    traces[label][method].append(path)
            arguments = native_cells, start, roster, roles, seed
            for mode in native.native_cost.MODES:
                for rule, paths in gepa.native_paths(arguments, mode, low, high).items():
                    native.record_boundaries(deltas.setdefault((mode, rule), {}), paths, high)
        name = f'{subject}/{model}'
        fingerprints[name] = {label: {policy: digest(path) for policy, path in policies.items()}
                              for label, policies in traces.items()}
        if any(path[previous.EXPECTED] != earlier['panelPathHashes'][name][label][previous.EXPECTED]
               for label, path in fingerprints[name].items()):
            raise ValueError('The original paired expected-cost paths must reproduce')
        for (mode, rule), changes in deltas.items():
            state = Counter()
            for amount in range(low, high + 1):
                state.update(changes.get(amount, {}))
                by_subject.setdefault(f'{mode}/{amount}/{rule}', Counter()).update(state)
    control_menu = tuple(label for label in next(iter(subjects.values())) if label != gepa.RETAIN)
    subject_ceiling = gepa.frontier.transfer.fitted.prior.by_subject_ceiling
    anchors = {label: row['cpo']['paidLookups'] for label, row in native_reference['comparisons'].items()}
    if subject_ceiling(subjects, control_menu, anchors) != {
        label: row['expandedSubjectCeiling'] for label, row in native_reference['comparisons'].items()
    }:
        raise ValueError('Every published subject-tuned native setting must reproduce at its budget')
    budgets = {f'{label}/{method}': point['paidLookups'] for label, methods in totals.items()
               for method, point in methods.items()}
    ceilings = subject_ceiling(subjects, control_menu, budgets)
    for label, methods in totals.items():
        for method, point in methods.items():
            anchor = earlier['totals'][label][previous.EXPECTED]
            if (point['paidLookups'] - point['extraLookups'] != anchor['paidLookups']
                    or point['holdoutPasses'] - point['extraPasses'] != anchor['holdoutPasses']):
                raise ValueError('The new and original CPO costs and scores must reconcile')
            key = f'{label}/{method}'
            best = ceilings[key]
            attaining = {sub: scores[best['settingsBySubject'][sub]] for sub, scores in subjects.items()}
            if any(sum(row[metric] for row in attaining.values()) != best[metric] for metric in native.native_cost.METRICS):
                raise ValueError('The native setting must attain its exact subject-tuned ceiling')
            methods[method] = {'cpo': point, 'gepa': best, 'attainingSubjectPoints': attaining}
    return {'comparisons': totals, 'headroom': headroom, 'nativeSettings': len(control_menu),
            'panelPathHashes': fingerprints, 'nativeSubjectTotalsSha256': digest(subjects)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    parent, panels, controls, earlier, native_reference = prepare()
    name = args.cohort
    plan = {**parent, 'cohort': name}
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    result = measure(panels[name], plan, controls, earlier[name], native_reference[name])
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': result},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
