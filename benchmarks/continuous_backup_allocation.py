"""Allocate the same independently qualified backup options across tasks."""

import argparse
from collections import Counter, deque
from fractions import Fraction
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import continuous_backup_witness as witness
from cpo._contract import digest
from cpo.two_sided_certificate_cycle import _run


backup, joint, native, transfer = witness.backup, witness.joint, witness.native, witness.transfer
continuous = backup.continuous
GLOBAL, EQUAL, PROPORTIONAL, DISCOUNT = 'global-priority', 'equal-charge', 'charge-per-episode', 'discounted-priority'
POLICIES = (GLOBAL, EQUAL, PROPORTIONAL, DISCOUNT)
MODES = (backup.REPAIR, backup.PROBE)


def offers_for(mode, episodes, priors):
    offers = {}
    for index, episode in enumerate(episodes):
        if episode.finalist is not None and episode.deployed == episode.incumbent:
            choices = backup.nominate(mode, episode.incumbent, episode.roster, episode.finalist,
                                      episode.validation_count, len(episode.qualification),
                                      episode.paid, episode.initial, priors)
            if choices:
                offers[index] = choices
    return offers


def allocation_key(policy, offer_key, spent, eligible, funding, population):
    """Order affordable task heads from paid charges and frozen opportunity counts."""
    if policy == GLOBAL:
        return offer_key
    if policy == EQUAL:
        return spent, *offer_key
    if policy == PROPORTIONAL:
        return Fraction(spent, eligible), *offer_key
    share = Fraction(funding * eligible, population)
    priority, episode, rank = offer_key
    return priority * share / (share + spent), episode, rank


def settle(episode, option, allowance, priors):
    def acquire(role, prompt, row):
        if (role, prompt, row) in episode.paid:
            raise ValueError('The backup cannot charge an already paid grade')
        return bool(episode.cells[prompt][int(row)])

    return backup.attempt(option, episode.incumbent, episode.qualification, episode.initial, acquire,
                          allowance, episode.seed, priors)


def rollout(policy, episodes, offers, funding, priors):
    queues, charges, attempts = {}, Counter(), Counter()
    population = Counter()
    for index, choices in offers.items():
        subject = episodes[index].subject
        population[subject] += 1
        queues.setdefault(subject, []).extend((-option.priority, index, rank, option)
                                             for rank, option in enumerate(choices))
    queues = {subject: deque(sorted(options)) for subject, options in queues.items()}
    remaining, snapshots, paths = funding, {}, []
    counts = Counter(dict.fromkeys(('attempts', 'proofAttempts', 'promotions', 'validationProbes'), 0))
    while True:
        ready = []
        for subject, queue in queues.items():
            while queue and (queue[0][1] in snapshots or queue[0][3].price > remaining):
                queue.popleft()
            if queue:
                key = allocation_key(policy, queue[0][:3], charges[subject], population[subject], funding, len(offers))
                ready.append((key, subject))
        if not ready:
            break
        _, subject = min(ready)
        _, index, _, option = queues[subject].popleft()
        episode = episodes[index]
        prompt, ledger, status = settle(episode, option, remaining, priors)
        if len(ledger) > option.price or status == 'unfunded':
            raise ValueError('A started attempt must fit its original full quote')
        remaining -= len(ledger)
        charges[subject] += len(ledger)
        attempts[subject] += 1
        snapshots[index] = prompt
        counts.update(attempts=1, proofAttempts=int(status != 'no-repair'), promotions=int(status == 'promoted'),
                      validationProbes=int(option.validation_probe is not None))
        if status != 'no-repair':
            other = episode.cells[option.candidate]
            base = episode.cells[episode.incumbent]
            exact = sum(other[int(row.id)] - base[int(row.id)] for row in episode.qualification)
            if status != ('promoted' if exact > 0 else 'rejected'):
                raise ValueError('The pooled scheduler cannot change the independent proof')
        paths.append((index, option.candidate, prompt, ledger))
    if remaining < 0 or sum(charges.values()) != funding - remaining:
        raise ValueError('Task quotes must settle against the same total budget')
    return snapshots, {**counts, 'eligibleEpisodes': len(offers), 'lookups': funding - remaining, 'unspent': remaining,
                       'backupPathSha256': digest(paths), 'lookupsByTask': charges, 'attemptsByTask': attempts}


def positive_menus(episodes, offers, funding, priors):
    """Price helpful terminal actions for hindsight diagnostics only."""
    by_task = {}
    for index, choices in offers.items():
        episode = episodes[index]
        previous = sum(episode.cells[episode.deployed][case] for case in episode.held)
        menu = set()
        for option in choices:
            if option.price <= funding:
                gain = sum(episode.cells[option.candidate][case] for case in episode.held) - previous
                if gain > 0:
                    _, ledger, status = settle(episode, option, option.price, priors)
                    if status == 'promoted':
                        menu.add((gain, len(ledger), option.price))
        if menu:
            by_task.setdefault(episode.subject, []).append(menu)
    return by_task


def prepare(cohort):
    base, panels, models, static, trained, gepa, simple, joint_parent, reference = witness.prepare(cohort)
    plan = {**base, 'protocol': 'continuous-backup-allocation-v1', 'queuePolicies': POLICIES, 'backupModes': MODES,
            'sourceSha256': {**base['sourceSha256'], Path(__file__).name: sha256(Path(__file__).read_bytes()).hexdigest()},
            'scope': 'Preserve every original offer, witness, priority within task and independent qualification. '
                     'Compare globally ranked funding with equalizing settled reads per task, equalizing settled '
                     'reads per eligible episode, and discounting by cumulative reads relative to a task’s '
                     'opportunity-proportional budget share. The cohort ceiling and full per-attempt quotes are '
                     'unchanged. Use settled-price hindsight to separate pooled allocation headroom from '
                     'headroom within observed task charges, and reprice the simple controls at actual spend. '
                     'Replay each alternative under the original policy’s realized spend as a stricter ceiling.'}
    return plan, panels, models, static, trained, gepa, simple, joint_parent, reference


def measure(plan, panels, models, static, trained, gepa, simple, joint_parent, reference):
    priors = witness.previous.priors_of(trained)
    episodes = backup.capture(plan, panels, joint.adaptive.routed_runner(plan, models, static), priors, joint_parent)
    funding = reference['funding']
    settlements, receipts, matched, frontiers = {'joint-proof': {}}, {}, {}, {}
    for mode in MODES:
        offers = offers_for(mode, episodes, priors)
        menus = positive_menus(episodes, offers, funding, priors)
        frontiers[mode] = witness.priced_bounds([menu for entries in menus.values() for menu in entries], funding)
        for policy in POLICIES:
            name = f'{mode}/{policy}'
            settlements[name], receipt = rollout(policy, episodes, offers, funding, priors)
            if policy == GLOBAL and any(receipt[key] != reference['policies'][mode][key]
                                        for key in receipt if key not in ('lookupsByTask', 'attemptsByTask')):
                raise ValueError('The original global allocation must reproduce its complete dispatch receipt')
            receipts[name] = {**receipt, 'taskChargeCeiling': sum(
                witness.priced_bounds(groups, receipt['lookupsByTask'][subject])['settledChargeUpperBound']
                for subject, groups in menus.items())}
            if policy != GLOBAL:
                cap = receipts[f'{mode}/{GLOBAL}']['lookups']
                settlements[f'{name}/matched'], matched[name] = rollout(policy, episodes, offers, cap, priors)
    vectors = {}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for index, episode in enumerate(episodes):
        subject = vectors.setdefault(episode.subject, {})
        for name, choices in settlements.items():
            prompt = choices.get(index, episode.deployed)
            grades = [episode.cells[prompt][case] for case in episode.held]
            add(subject.setdefault(name, [0] * len(grades)), grades)
    scores = {name: sum(sum(rows[name]) for rows in vectors.values()) for name in settlements}
    if scores['joint-proof'] != reference['jointPasses'] or any(
            scores[f'{mode}/{GLOBAL}'] != reference['policies'][mode]['holdoutPasses'] for mode in MODES):
        raise ValueError('The original final scores must reproduce')
    budgets = {name: reference['jointLookups'] + receipt['lookups'] for name, receipt in receipts.items()}
    menu = simple['settingsTotals']
    settings = tuple(name for name in menu if name != joint.RETAIN)
    ceilings = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling(simple['settingsBySubject'], settings, budgets)
    engines = joint.adaptive.screens(plan)
    schedules = {f'{name}/subject': point['settingsBySubject'] for name, point in ceilings.items()}
    attained, _ = joint.adaptive.replay(plan, panels, {name: partial(_run, screen=engines[name]) for name in settings},
                                       schedules, vectors)
    for name, point in ceilings.items():
        if any(attained[f'{name}/subject'][key] != point[key] for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError('The subject-tuned simple schedule must attain the equivalent budgeted result')

    paired = native.frozen.paired_effects.paired_effect
    policies = {}
    for mode in MODES:
        for policy in POLICIES:
            name = f'{mode}/{policy}'
            gain = scores[name] - scores['joint-proof']
            if not gain <= receipts[name]['taskChargeCeiling'] <= frontiers[mode]['settledChargeUpperBound']:
                raise ValueError('Observed gains and task-specific hindsight must fit the pooled ceiling')
            policies[name] = {**receipts[name], 'holdoutPasses': scores[name], 'paidLookups': budgets[name],
                              'subjectTunedSimple': ceilings[name],
                              'paired': {target: paired(vectors, name, target, plan)
                                         for target in ('joint-proof', f'{mode}/{GLOBAL}', f'{name}/subject')}}
            if name in matched:
                matched_name = f'{name}/matched'
                policies[name]['atPriorRealizedSpend'] = {
                    'holdoutPasses': scores[matched_name], 'backupLookups': matched[name]['lookups'],
                    'backupPathSha256': matched[name]['backupPathSha256'],
                    'pairedAgainstGlobal': paired(vectors, matched_name, f'{mode}/{GLOBAL}', plan),
                }
    return {'funding': funding, 'jointPasses': scores['joint-proof'], 'jointLookups': reference['jointLookups'],
            'originalLookups': reference['originalLookups'],
            'gepaAtOriginalBudget': gepa['subjectTunedGepa'][joint.ROUTED],
            'hindsight': frontiers, 'policies': policies}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=continuous.COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.cohort)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': measure(plan, *inputs)}
    with args.out.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
