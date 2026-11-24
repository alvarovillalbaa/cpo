"""Rank independently qualified backups by a task-disjoint estimate of terminal gain."""

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

from benchmarks import continuous_archive_backup as backup
from cpo._contract import digest
from cpo.joint_order_qualification import finish_joint_order, validation_context
from cpo.optimizer import Row
from cpo.two_sided_certificate_cycle import _run


joint, continuous, native, transfer = backup.joint, backup.continuous, backup.native, backup.transfer
MODES = (backup.REPAIR, backup.PROBE)
VALUE = {mode: f'value/{mode}' for mode in MODES}
ORIGINAL_NOMINATE = backup.nominate
SHRINKAGE = 24
RECEIPTS = dict(zip(continuous.COHORTS, (
    'd1aa24718ae398d37a364d129a4e5fda755d817fc4484af5cdf62aff8ebc5d72',
    '63e53b97dd7903e0d1c19b573886d0f99a244e7a80714f1268067cf1936230af',
    '82570b0724f77094a5cfa2c4515ca1db0624046658899420ef4f36868b202982',
    'ed29cb011f6f716f9bf639ac24e23d185e12fcdc10311e68e2ec58cfbcff8fbf',
    'fbdd9e594a6aacf60ced5c6401f8a85e8bfa22fb6adc078364504d5028efb8f4',
    '23d0b1f08dc1d32bd329e92b782b805060188d43078977f66978fb0166f0b340',
    '6770acb206f5cd25442e80322aec14666ce73f16e438d88d459472b2bf9aca78',
), strict=True))


def keys(option, initial):
    kind = 'probe' if option.validation_probe is not None else 'paid'
    misses = min(2, sum(not event.passed for event in initial))
    base, challenger = validation_context(option.counts)
    return 'all', kind, f'{kind}/{misses}', f'{kind}/{misses}/{base}/{challenger}'


def summarize(samples, context, shrinkage):
    """Shrink signed outcome and charged reads through increasingly specific groups."""
    root = samples['all']
    gain, cost = Fraction(root[1]) / root[0], Fraction(root[2]) / root[0]
    for group in context[1:]:
        count, observed_gain, observed_cost = samples.get(group, (0, 0, 0))
        gain = (Fraction(observed_gain) + shrinkage * gain) / (count + shrinkage)
        cost = (observed_cost + shrinkage * cost) / (count + shrinkage)
    return gain / cost


def rank(options, initial, samples, shrinkage):
    """Use predicted net gain, abstaining when its estimate is nonpositive."""
    adjusted = []
    for option in options:
        value = summarize(samples, keys(option, initial), shrinkage)
        if value > 0:
            adjusted.append(replace(option, priority=value))
    return sorted(adjusted, key=lambda option: -option.priority)


def hashes():
    paths = (Path(__file__), Path(backup.__file__), *map(Path, (joint.__file__, joint.adaptive.__file__)))
    return {str(path.relative_to(transfer.ROOT)): sha256(path.read_bytes()).hexdigest() for path in paths}


def priors_of(frozen):
    return {None if key == 'pooled' else tuple(map(int, key.split('/'))): tuple(weights)
            for key, weights in frozen['weights'].items()}


def training():
    frozen = json.loads(transfer.read_locked(backup.FIT, backup.FIT_SHA))
    source = frozen['plan']
    discovery, groups, *_ = native.prepare()
    if digest(source) != frozen['planSha256'] or digest(discovery) != source['discoveryPlanSha256']:
        raise ValueError('The original task-disjoint discovery archive must match')
    _, models, static = joint.adaptive.promotion.training_plan()
    plan = {**source, 'protocol': 'continuous-backup-value-fit-v1', 'jointFitSha256': backup.FIT_SHA,
            'shrinkage': SHRINKAGE, 'sourceSha256': {**source['sourceSha256'], **hashes()},
            'scope': 'Label every terminal one-probe option on the task-disjoint discovery panels with its observed '
                     'net change in holdout pass rate and actual additional lookup cost. Include failed probes '
                     'and rejections at zero gain. Use hierarchical smoothing over the probe indicator, '
                     'one or multiple paid incumbent qualification misses, and the coarse paid validation '
                     'rates. Estimate signed expected gain per new read. Decline nonpositive predictions.'}
    return plan, groups, models, static, frozen


def label_panel(plan, subject, matrix, runner, priors):
    run = native.paired.cycle.execute_path
    cells, _ = transfer.case_cells(matrix)
    revised = partial(finish_joint_order, priors=priors)
    baseline, labels = Counter(), []
    for seed in plan['seeds']:
        current, stages = continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
        for local_seed, roster, roles in stages:
            args = runner, cells, current, roster, roles, local_seed, plan['fullRosterCap'], 1
            original, old_paid = run(*args)
            with patch.object(joint.two_sided_certificate_cycle, '_finish_with_partner_evidence', revised):
                result, paid = run(*args)
            if original.prompt != result.prompt or original.search != result.search:
                raise ValueError('Qualification ordering must preserve the original discovery trajectory')
            baseline['paidLookups'] += len(old_paid)
            incumbent, current = current, result.prompt
        start_score = sum(cells[current][case] for case in roles[-1])
        baseline['holdoutPasses'] += start_score
        if result.search.finalist is None or result.qualification.status != 'rejected':
            continue
        initial = tuple(reply for reply in result.qualification.observations if reply.prompt == incumbent)
        qualification = tuple(Row(str(case), 'qualification') for case in roles[2])
        options = ORIGINAL_NOMINATE(backup.PROBE, incumbent, roster, result.search.finalist, len(roles[1]),
                                   len(qualification), paid, initial, priors)

        def acquire(role, prompt, row):
            if (role, prompt, row) in paid:
                raise ValueError('The simulated backup must only charge new grades')
            return bool(cells[prompt][int(row)])

        for option in options:
            prompt, ledger, status = backup.attempt(option, incumbent, qualification, initial,
                                                    acquire, option.price, local_seed, priors)
            outcome = sum(cells[prompt][case] for case in roles[-1])
            labels.append((keys(option, initial), Fraction(outcome - start_score, len(roles[-1])),
                           len(ledger), status == 'promoted'))
    return baseline, labels


def fit(plan, groups, models, static, frozen):
    runner = joint.adaptive.routed_runner(plan, models, static)
    priors = priors_of(frozen)
    samples, discovery = {}, {}
    for cohort, panels in groups.items():
        enrollment = set(map(tuple, plan['fitEnrollment'][cohort]))
        if not enrollment:
            continue
        baseline = Counter()
        for subject, model, matrix in panels:
            if (subject, model) not in enrollment:
                continue
            point, labels = label_panel(plan, subject, matrix, runner, priors)
            baseline.update(point)
            for context, gain, cost, promoted in labels:
                for key in context:
                    totals = samples.setdefault(key, [0, Fraction(0), 0, 0])
                    totals[0] += 1
                    totals[1] += gain
                    totals[2] += cost
                    totals[3] += promoted
        discovery[cohort] = baseline
    if discovery != frozen['discoveryTotals'] or not samples.get('all'):
        raise ValueError('The study requires the original discovery router and measured backup labels')
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'discoveryTotals': discovery,
            'labels': {key: (count, str(gain), cost, promotions)
                       for key, (count, gain, cost, promotions) in samples.items()}}


def prepare(cohort, fitted):
    trained = json.loads(fitted)
    fit_plan = trained['plan']
    sources = hashes()
    if (fit_plan['protocol'] != 'continuous-backup-value-fit-v1' or fit_plan['jointFitSha256'] != backup.FIT_SHA
            or trained['planSha256'] != digest(fit_plan)
            or any(fit_plan['sourceSha256'].get(path) != sha for path, sha in sources.items())):
        raise ValueError('Transfer requires the frozen discovery fit and its original source')
    base, panels, models, static, frozen, gepa, simple, joint_parent = backup.prepare(cohort)
    if {subject for subject, _, _ in panels} & {subject for panels in fit_plan['fitEnrollment'].values()
                                               for subject, _ in panels}:
        raise ValueError('No transfer task can occur in the discovery labels')
    lock = RECEIPTS[cohort]
    receipt = json.loads(transfer.read_locked(f'docs/continuous-archive-backup-{cohort.lower()}-v1.json', lock))
    if receipt['planSha256'] != digest(base):
        raise ValueError('The previous backup study must match the same archive layouts')
    plan = {**base, 'protocol': 'continuous-backup-value-transfer-v1', 'fitSha256': sha256(fitted).hexdigest(),
            'backupReceiptSha256': lock, 'sourceSha256': {**base['sourceSha256'], **sources},
            'scope': 'Rank the same repair and one-probe options by discovery-estimated net gain and allow '
                     'abstention. Reproduce the previous probability-based rollouts for a paired comparison. '
                     'Hold fixed every paid first-choice grade, proof, hard cohort budget and backup eligibility '
                     'rule. Replay exact common and subject-tuned simple controls at each revised spend.'}
    return plan, panels, models, static, frozen, gepa, simple, joint_parent, trained, receipt['results']


def measure(plan, panels, models, static, frozen, gepa, simple, joint_parent, trained, reference):
    priors = priors_of(frozen)
    episodes = backup.capture(plan, panels, joint.adaptive.routed_runner(plan, models, static), priors, joint_parent)
    samples = {key: values[:3] for key, values in trained['labels'].items()}
    shrinkage = trained['plan']['shrinkage']
    funding = reference['funding']
    snapshots, receipts = {'joint-proof': {}}, {}

    def nominate(mode, incumbent, roster, rejected, validation_count, qualification_count, paid, initial, priors):
        options = ORIGINAL_NOMINATE(mode, incumbent, roster, rejected, validation_count, qualification_count,
                                   paid, initial, priors)
        return rank(options, initial, samples, shrinkage)

    for mode in MODES:
        snapshots[mode], receipts[mode] = backup.rollout(mode, episodes, funding, priors)
        old = reference['policies'][mode]
        if any(receipts[mode][key] != old[key] for key in receipts[mode]):
            raise ValueError('The earlier backup trajectory must reproduce every charged read')
        name = VALUE[mode]
        with patch.object(backup, 'nominate', nominate):
            snapshots[name], receipts[name] = backup.rollout(mode, episodes, funding, priors)

    vectors = {}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for index, episode in enumerate(episodes):
        subject = vectors.setdefault(episode.subject, {})
        for name, positions in snapshots.items():
            prompt = positions.get(index, episode.deployed)
            grades = [episode.cells[prompt][case] for case in episode.held]
            add(subject.setdefault(name, [0] * len(grades)), grades)
    scores = {name: sum(sum(rows[name]) for rows in vectors.values()) for name in snapshots}
    if scores['joint-proof'] != reference['jointPasses'] or any(
            scores[mode] != reference['policies'][mode]['holdoutPasses'] for mode in MODES):
        raise ValueError('The matched control must keep its archived final scores')

    budgets = {name: reference['jointLookups'] + receipts[name]['lookups'] for name in VALUE.values()}
    menu = simple['settingsTotals']
    settings = tuple(name for name in menu if name != joint.RETAIN)
    common = {name: native.gepa.best_fixed(menu, settings, cap) for name, cap in budgets.items()}
    tuned = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling(simple['settingsBySubject'], settings, budgets)
    targets = {f'{name}/common': (dict.fromkeys(vectors, common[name]['setting']), common[name]) for name in budgets}
    targets.update({f'{name}/subject': (tuned[name]['settingsBySubject'], tuned[name]) for name in budgets})
    engines = joint.adaptive.screens(plan)
    measured, _ = joint.adaptive.replay(plan, panels, {name: partial(_run, screen=engines[name]) for name in settings},
                                       {name: setting for name, (setting, _) in targets.items()}, vectors)
    for name, (_, expected) in targets.items():
        if any(measured[name][key] != expected[key] for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError('The budget-matched simple controls must attain their score and cost')

    paired = native.frozen.paired_effects.paired_effect
    results = {}
    for mode, name in VALUE.items():
        counter = receipts[name]
        score = {**counter, 'holdoutPasses': scores[name], 'paidLookups': budgets[name]}
        score['priorPolicy'] = {'holdoutPasses': scores[mode],
                                'paidLookups': reference['policies'][mode]['paidLookups']}
        score['bestCommonSimple'] = common[name]
        score['subjectTunedSimple'] = tuned[name]
        score['paired'] = {target: paired(vectors, name, target, plan)
                           for target in ('joint-proof', mode, f'{name}/common', f'{name}/subject')}
        results[name] = score
    return {'funding': funding, 'jointPasses': scores['joint-proof'], 'originalLookups': reference['originalLookups'],
            'jointLookups': reference['jointLookups'], 'policies': results,
            'priorSubjectTunedGepa': gepa['subjectTunedGepa'][joint.ROUTED]}


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
            parser.error('Fit requires only a fresh output path')
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
            parser.error('Transfer requires its current seal, pinned GEPA and a fresh output path')
        report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': measure(plan, *inputs)}
        path = args.out
    with path.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
