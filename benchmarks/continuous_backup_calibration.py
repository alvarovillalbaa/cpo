"""Calibrate a terminal backup's promotion probability and paid cost on discovery."""

import argparse
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import continuous_backup_allocation as allocation
from cpo._contract import digest
from cpo.joint_order_qualification import validation_context
from cpo.two_sided_certificate_cycle import _run


witness, backup, joint, native, transfer = (
    allocation.witness, allocation.backup, allocation.joint, allocation.native, allocation.transfer,
)
previous = witness.previous
continuous = allocation.continuous
ORIGINAL, EMPIRICAL, CORRECTED = 'original', 'empirical', 'corrected'
RANKERS = (ORIGINAL, EMPIRICAL, CORRECTED)
MODES = allocation.MODES
SHRINKAGE, SCALE = 24, 1_000_000
LABELS = 'docs/continuous-backup-value-fit-v1.json'
LABELS_SHA = 'f62251e80a4dad71232c9e7f6e4ef99fb17ac1c2f7a388155cb02aaa97148fc4'
RECEIPTS = dict(zip(continuous.COHORTS, (
    '4e4ef3f3436949d89fcc44472f5b9c2732274087fba2a5d4cf21c22cb2c7abc3',
    'be6e37f3cb06b52d17c2560a04f84dc8df445a8a8d11aabb4f51070e4c98febb',
    '8fe3218f60cd9fc098c1245aa231d3b1a02fd5c482c52d1308893ada0b533686',
    '27a1eb349dc41470bca1434ae787b76d6003176fdf2afb981f46f167ba0826db',
    '06ed87eb64c404a61e15368a1e52607117fef43185b7d0dfad9979fc62aa7269',
    '24c2503ae4c5bc627d079768e2f0f607255e0883cbf7aa03d750f6b95c53b19c',
    '6c2ffc83119ba7894c433f4bd2cc4954f8c42a7ce0d906c2d9d0d21b46e7edcb',
), strict=True))


def keys(option, initial):
    parent = previous.keys(option, initial)
    return (*parent, f'{parent[-1]}/{len(initial)}')


def forecast(option, width, initial, priors):
    """Recover the two factors of the original priority before calibration."""
    misses = sum(not event.passed for event in initial)
    weights = priors.get(validation_context(option.counts), priors[None])
    promotion, cost = backup.qualification_value(weights, width - len(initial),
                                                len(initial) - misses, misses)
    if option.validation_probe is not None:
        base, (passed, seen) = option.counts
        prior = priors.get(validation_context((base, (passed - 1, seen - 1))), priors[None])
        probe = Fraction(prior[3], prior[2] + prior[3])
        promotion, cost = probe * promotion, 1 + probe * cost
    if promotion / cost != option.priority:
        raise ValueError('The original score must equal the factored forecast')
    return promotion, cost


def predict(ranker, samples, context, baseline, quote, shrinkage):
    if ranker == ORIGINAL:
        return baseline
    count, successes, reads, probability_mass, cost_mass = samples['all']
    totals = successes, reads
    exposure = probability_mass, cost_mass
    if ranker == EMPIRICAL:
        average = tuple(Fraction(value, count) for value in totals)
        for group in context[1:]:
            seen, wins, paid, _, _ = samples.get(group, (0, 0, 0, 0, 0))
            average = tuple((total + shrinkage * parent) / (seen + shrinkage)
                            for total, parent in zip((wins, paid), average, strict=True))
        probability, cost = average
    else:
        prior = tuple(Fraction(mass * shrinkage, SCALE * count) for mass in exposure)
        factor = (Fraction(1), Fraction(1))
        for group in context:
            _, wins, paid, expected_wins, expected_paid = samples.get(group, (0, 0, 0, 0, 0))
            factor = tuple((observed + parent * regularizer) / (Fraction(predicted, SCALE) + regularizer)
                           for observed, predicted, parent, regularizer
                           in zip((wins, paid), (expected_wins, expected_paid), factor, prior, strict=True))
        probability, cost = (value * scale for value, scale in zip(baseline, factor, strict=True))
    return min(probability, 1), min(quote, max(1, cost))


def hashes():
    paths = (__file__, allocation.__file__, previous.__file__, backup.__file__,
             transfer.ROOT / 'cpo/joint_order_qualification.py')
    return {str(Path(path).relative_to(transfer.ROOT)): sha256(Path(path).read_bytes()).hexdigest() for path in paths}


def training():
    base, groups, models, static, frozen = previous.training()
    labels = json.loads(transfer.read_locked(LABELS, LABELS_SHA))
    if labels['planSha256'] != digest(base):
        raise ValueError('The earlier discovery labels must match their frozen plan')
    plan = {**base, 'protocol': 'continuous-backup-calibration-fit-v1', 'priorLabelsSha256': LABELS_SHA,
            'sourceSha256': {**base['sourceSha256'], **hashes()}, 'scale': SCALE, 'shrinkage': SHRINKAGE,
            'scope': 'Fit only promotion outcomes and charged proof cost from the task-disjoint discovery labels. '
                     'Share counts hierarchically by probe indicator, incumbent misses, validation rates and '
                     'number of incumbent qualification replies. Compare empirical rates with multiplicative '
                     'corrections of the original probability and cost. Preserve original proof ordering.'}
    return plan, groups, models, static, frozen, labels


def fit(plan, groups, models, static, frozen, expected):
    priors = previous.priors_of(frozen)
    runner = joint.adaptive.routed_runner(plan, models, static)
    samples, discovery = {}, {}
    original_attempt = backup.attempt

    def observe(option, incumbent, qualification, initial, acquire, allowance, seed, weights):
        baseline = forecast(option, len(qualification), initial, weights)
        result, ledger, status = original_attempt(option, incumbent, qualification, initial,
                                                  acquire, allowance, seed, weights)
        label = (1, int(status == 'promoted'), len(ledger), *(round(value * SCALE) for value in baseline))
        for context in keys(option, initial):
            counts = samples.setdefault(context, [0] * len(label))
            for index, number in enumerate(label):
                counts[index] += number
        return result, ledger, status

    with patch.object(backup, 'attempt', observe):
        for cohort, panels in groups.items():
            enrolled = set(map(tuple, plan['fitEnrollment'][cohort]))
            if not enrolled:
                continue
            discovery[cohort] = Counter()
            for subject, model, matrix in panels:
                if (subject, model) in enrolled:
                    first, _ = previous.label_panel(plan, subject, matrix, runner, priors)
                    discovery[cohort].update(first)
    if discovery != expected['discoveryTotals'] or any(
            samples[key][:3] != [count, promotions, cost]
            for key, (count, _, cost, promotions) in expected['labels'].items()):
        raise ValueError('Discovery promotion labels and actual costs must reproduce')
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'discoveryTotals': discovery, 'labels': samples}


def prepare(cohort, fit_bytes):
    fit_receipt = json.loads(fit_bytes)
    fit_plan = fit_receipt['plan']
    sources = hashes()
    if (fit_plan['protocol'] != 'continuous-backup-calibration-fit-v1'
            or fit_plan['priorLabelsSha256'] != LABELS_SHA or fit_receipt['planSha256'] != digest(fit_plan)
            or any(fit_plan['sourceSha256'].get(path) != sha for path, sha in sources.items())):
        raise ValueError('The fit receipt and source checksums must match the running scheduler')
    base, panels, models, static, frozen, gepa, simple, joint_parent, _ = allocation.prepare(cohort)
    if {subject for subject, _, _ in panels} & {subject for rows in fit_plan['fitEnrollment'].values()
                                               for subject, _ in rows}:
        raise ValueError('Transfer tasks must be distinct from calibration tasks')
    lock = RECEIPTS[cohort]
    receipt = json.loads(transfer.read_locked(f'docs/continuous-backup-allocation-{cohort.lower()}-v1.json', lock))
    if receipt['planSha256'] != digest(base):
        raise ValueError('The task-balanced dispatch receipt must match the original plan')
    plan = {**base, 'protocol': 'continuous-backup-calibration-transfer-v1', 'fitSha256': sha256(fit_bytes).hexdigest(),
            'allocationReceiptSha256': lock, 'sourceSha256': {**base['sourceSha256'], **sources},
            'rankers': RANKERS, 'scope': 'Keep the original eligibility, witness, task-balanced allocator, '
                     'full quotes and exact proof. Replace priority only. Run each ranker under the previous '
                     'global allocator’s realized lookup count and verify the task-balanced control. '
                     'Measure promotion probability and cost error over the same complete offer menu. '
                     'Replay the subject-tuned simple controls at actual spend.'}
    return plan, panels, models, static, frozen, gepa, simple, joint_parent, fit_receipt, receipt['results']


def forecasts(episodes, offers, samples, shrinkage, priors):
    modeled, diagnostics = {name: {} for name in RANKERS}, {name: Counter() for name in RANKERS}
    for index, options in offers.items():
        episode = episodes[index]
        for name in RANKERS:
            modeled[name][index] = []
        for option in options:
            baseline = forecast(option, len(episode.qualification), episode.initial, priors)
            estimates = {name: predict(name, samples, keys(option, episode.initial), baseline,
                                       option.price, shrinkage) for name in RANKERS}
            for name, (probability, cost) in estimates.items():
                modeled[name][index].append(replace(option, priority=probability / cost))
            _, ledger, status = allocation.settle(episode, option, option.price, priors)
            outcome, charge = int(status == 'promoted'), len(ledger)
            for name, (probability, cost) in estimates.items():
                diagnostics[name].update(offers=1, promotions=outcome, actualCost=charge,
                                         squaredError=round((probability - outcome)**2 * SCALE),
                                         absoluteCostError=round(abs(cost - charge) * SCALE))
    return modeled, diagnostics


def measure(plan, panels, models, static, frozen, gepa, simple, joint_parent, trained, reference):
    priors = previous.priors_of(frozen)
    episodes = backup.capture(plan, panels, joint.adaptive.routed_runner(plan, models, static), priors, joint_parent)
    snapshots, points, diagnostics = {'joint-proof': {}}, {}, {}
    for mode in MODES:
        offers = allocation.offers_for(mode, episodes, priors)
        estimates, diagnostics[mode] = forecasts(episodes, offers, trained['labels'], trained['plan']['shrinkage'], priors)
        cap = reference['policies'][f'{mode}/{allocation.GLOBAL}']['lookups']
        for ranker in RANKERS:
            name = f'{mode}/{ranker}'
            snapshots[name], points[name] = allocation.rollout(allocation.PROPORTIONAL, episodes,
                                                              estimates[ranker], cap, priors)
        original = points[f'{mode}/{ORIGINAL}']
        prior = reference['policies'][f'{mode}/{allocation.PROPORTIONAL}']['atPriorRealizedSpend']
        if (original['lookups'], original['backupPathSha256']) != (prior['backupLookups'], prior['backupPathSha256']):
            raise ValueError('The task-balanced control must reproduce its charged callback trace')
    vectors = {}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for index, episode in enumerate(episodes):
        rows = vectors.setdefault(episode.subject, {})
        for key, choices in snapshots.items():
            prompt = choices.get(index, episode.deployed)
            grades = [episode.cells[prompt][case] for case in episode.held]
            add(rows.setdefault(key, [0] * len(grades)), grades)
    scores = {name: sum(sum(rows[name]) for rows in vectors.values()) for name in snapshots}
    if scores['joint-proof'] != reference['jointPasses'] or any(
            scores[f'{mode}/{ORIGINAL}']
            != reference['policies'][f'{mode}/{allocation.PROPORTIONAL}']['atPriorRealizedSpend']['holdoutPasses']
            for mode in MODES):
        raise ValueError('The final joint-proof and task-balanced scores must reproduce')

    menu = simple['settingsTotals']
    settings = tuple(name for name in menu if name != joint.RETAIN)
    budgets = {name: reference['jointLookups'] + point['lookups'] for name, point in points.items()}
    tuned = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling(simple['settingsBySubject'], settings, budgets)
    engines = joint.adaptive.screens(plan)
    schedules = {f'{name}/subject': point['settingsBySubject'] for name, point in tuned.items()}
    attained, _ = joint.adaptive.replay(plan, panels, {name: partial(_run, screen=engines[name]) for name in settings},
                                       schedules, vectors)
    for name, point in tuned.items():
        if any(attained[f'{name}/subject'][key] != point[key] for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError('The selected subject-tuned controls must attain their budget-matched scores')

    paired = native.frozen.paired_effects.paired_effect
    return {'jointPasses': scores['joint-proof'], 'jointLookups': reference['jointLookups'],
            'originalLookups': reference['originalLookups'], 'forecastErrorsInMillionths': diagnostics,
            'gepaAtOriginalBudget': gepa['subjectTunedGepa'][joint.ROUTED],
            'policies': {name: {**point, 'holdoutPasses': scores[name], 'paidLookups': budgets[name],
                                'subjectTunedSimple': tuned[name],
                                'paired': {control: paired(vectors, name, control, plan) for control in
                                           ('joint-proof', f'{name.split("/")[0]}/{ORIGINAL}', f'{name}/subject')}}
                         for name, point in points.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--fit', type=Path)
    modes.add_argument('--cohort', choices=continuous.COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.fit is not None:
        if args.fit.exists() or any((args.fitted, args.execute, args.out)):
            parser.error('Fit requires a fresh path and no transfer arguments')
        plan, *inputs = training()
        if version('gepa') != plan['gepaVersion']:
            parser.error('Fit requires pinned GEPA')
        report, path = fit(plan, *inputs), args.fit
    else:
        if args.fitted is None:
            parser.error('Transfer requires a fitted receipt')
        plan, *inputs = prepare(args.cohort, args.fitted.read_bytes())
        seal = digest(plan)
        if args.execute is None and args.out is None:
            print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
            return
        if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
            parser.error('Transfer requires its current seal, pinned GEPA and a fresh path')
        report, path = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
                        'results': measure(plan, *inputs)}, args.out
    with path.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
