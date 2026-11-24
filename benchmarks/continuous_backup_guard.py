"""Require a paid incumbent-pass witness when qualifying terminal backups."""

import argparse
from collections import Counter
from dataclasses import dataclass, replace
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
CACHED, ONE, TWO = 'cached-pass', 'guard-one-read', 'guard-two-reads'
POLICIES = (CACHED, ONE, TWO)
CONTROLS = (backup.REPAIR, backup.PROBE)


@dataclass(frozen=True)
class Offer:
    option: backup.Opportunity
    guard_case: str | None

    @property
    def price(self):
        return self.option.price + int(self.guard_case is not None)


def guard_options(policy, options, incumbent, paid):
    passes = [row for (role, prompt, row), grade in paid.items()
              if role == 'validation' and prompt == incumbent and grade]
    offers = []
    for option in options:
        if any(paid.get(('validation', option.candidate, row)) is True for row in passes):
            offers.append(Offer(option, None))
            continue
        if policy == CACHED or (policy == ONE and option.validation_probe is not None):
            continue
        row = next((row for row in passes if ('validation', option.candidate, row) not in paid), None)
        if row is not None:
            offers.append(Offer(option, row))
    return offers


def attempt(offer, incumbent, qualification, initial, acquire, allowance, seed, priors):
    if offer.price > allowance:
        return incumbent, (), 'unfunded'
    option = offer.option
    if offer.guard_case is None:
        return backup.attempt(option, incumbent, qualification, initial, acquire, allowance, seed, priors)

    reads = []

    def validate(row):
        grade = acquire('validation', option.candidate, row)
        if type(grade) is not bool:
            raise ValueError('Validation needs an exact binary grade')
        reads.append(('validation', option.candidate, row, grade))
        return grade

    if option.validation_probe is not None:
        if not validate(option.validation_probe):
            return incumbent, tuple(reads), 'no-repair'
        option = replace(option, validation_probe=None, price=option.price - 1)
    if not validate(offer.guard_case):
        return incumbent, tuple(reads), 'guard-rejected'
    result, proof, status = backup.attempt(option, incumbent, qualification, initial, acquire,
                                          allowance - len(reads), seed, priors)
    return result, (*reads, *proof), status


def options_for(episode, priors):
    if episode.finalist is None or episode.deployed != episode.incumbent:
        return ()
    return backup.nominate(backup.PROBE, episode.incumbent, episode.roster, episode.finalist,
                           episode.validation_count, len(episode.qualification), episode.paid,
                           episode.initial, priors)


def close(offer, episode, allowance, priors):
    def acquire(role, prompt, row):
        if (role, prompt, row) in episode.paid:
            raise ValueError('The backup cannot buy an already paid grade')
        return bool(episode.cells[prompt][int(row)])

    return attempt(offer, episode.incumbent, episode.qualification, episode.initial, acquire,
                   allowance, episode.seed, priors)


def rollout(policy, episodes, choices, funding, priors):
    counts = Counter(dict.fromkeys(('eligibleEpisodes', 'attempts', 'guardReads', 'guardRejections',
                                    'proofAttempts', 'promotions'), 0))
    eligible, ordered = {}, []
    for index, options in enumerate(choices):
        episode = episodes[index]
        offers = guard_options(policy, options, episode.incumbent, episode.paid)
        if offers:
            eligible[index] = offers
            counts['eligibleEpisodes'] += 1
            ordered.extend((-offer.option.priority, index, rank, offer) for rank, offer in enumerate(offers))

    remaining, deploy, paths = funding, {}, []
    for _, index, _, offer in sorted(ordered):
        if index in deploy or offer.price > remaining:
            continue
        episode = episodes[index]
        prompt, ledger, status = close(offer, episode, remaining, priors)
        if len(ledger) > offer.price:
            raise ValueError('Every fresh grade must fit the complete start quote')
        remaining -= len(ledger)
        if status in ('promoted', 'rejected'):
            exact = sum(episode.cells[offer.option.candidate][int(row.id)] - episode.cells[episode.incumbent][int(row.id)]
                        for row in episode.qualification)
            if status != ('promoted' if exact > 0 else 'rejected'):
                raise ValueError('Every backup reaching independent proof must settle its exact gain')
            if offer.guard_case is not None and ('validation', offer.option.candidate, offer.guard_case, True) not in ledger:
                raise ValueError('A successful preservation read is required before any independent proof')
        deploy[index] = prompt
        counts.update(attempts=1, guardReads=sum(role == 'validation' and row == offer.guard_case
                                                 for role, _, row, _ in ledger),
                      guardRejections=int(status == 'guard-rejected'),
                      proofAttempts=int(status in ('promoted', 'rejected')), promotions=int(status == 'promoted'))
        paths.append((index, offer.option.candidate, offer.guard_case, prompt, ledger, status))
    return deploy, {**counts, 'lookups': funding - remaining, 'unspent': remaining, 'backupPathSha256': digest(paths),
                    'hindsightSettledBounds': hindsight(episodes, eligible, funding, priors)}


def hindsight(episodes, eligible, funding, priors):
    groups = []
    for index, offers in eligible.items():
        episode = episodes[index]
        previous = sum(episode.cells[episode.deployed][case] for case in episode.held)
        menu = set()
        for offer in offers:
            if offer.price > funding:
                continue
            gain = sum(episode.cells[offer.option.candidate][case] for case in episode.held) - previous
            if gain <= 0:
                continue
            _, ledger, status = close(offer, episode, offer.price, priors)
            if status == 'promoted':
                menu.add((gain, len(ledger), offer.price))
        if menu:
            groups.append(menu)
    return witness.priced_bounds(groups, funding)


def prepare(cohort):
    base, panels, models, static, trained, gepa, simple, joint_parent, reference = witness.prepare(cohort)
    sources = {str(path.relative_to(transfer.ROOT)): sha256(path.read_bytes()).hexdigest()
               for path in map(Path, (__file__, witness.__file__))}
    plan = {**base, 'protocol': 'continuous-backup-guard-v1', 'guardPolicies': POLICIES,
            'sourceSha256': {**base['sourceSha256'], **sources},
            'scope': 'Keep the original primary cycles, candidate menu and probability ranking. Qualify a backup '
                     'only if it repairs a known validation miss and preserves a known validation pass. '
                     'Compare cached-only evidence, at most one new validation read and at most two new '
                     'validation reads per attempt. Keep full reservations, the original joint qualification '
                     'order, exact gain, and the original lookup savings per cohort. Measure settled-price '
                     'hindsight bounds for each guard menu and reprice subject-tuned simple controls.'}
    return plan, panels, models, static, trained, gepa, simple, joint_parent, reference


def measure(plan, panels, models, static, trained, gepa, simple, joint_parent, reference):
    priors = witness.previous.priors_of(trained)
    episodes = backup.capture(plan, panels, joint.adaptive.routed_runner(plan, models, static), priors, joint_parent)
    funding = reference['funding']
    options = [options_for(episode, priors) for episode in episodes]
    snapshots, receipts = {'joint-proof': {}}, {}
    for mode in CONTROLS:
        snapshots[mode], receipts[mode] = backup.rollout(mode, episodes, funding, priors)
        if any(reference['policies'][mode][key] != value for key, value in receipts[mode].items()):
            raise ValueError('The original control must reproduce its full dispatch receipt')
    for mode in POLICIES:
        snapshots[mode], receipts[mode] = rollout(mode, episodes, options, funding, priors)
    vectors = {}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for index, episode in enumerate(episodes):
        subject = vectors.setdefault(episode.subject, {})
        for mode, choices in snapshots.items():
            prompt = choices.get(index, episode.deployed)
            grades = [episode.cells[prompt][case] for case in episode.held]
            add(subject.setdefault(mode, [0] * len(grades)), grades)
    scores = {name: sum(sum(rows[name]) for rows in vectors.values()) for name in snapshots}
    if scores['joint-proof'] != reference['jointPasses'] or any(
            scores[mode] != reference['policies'][mode]['holdoutPasses'] for mode in CONTROLS):
        raise ValueError('The original backups must retain their published scores')

    budgets = {mode: reference['jointLookups'] + receipts[mode]['lookups'] for mode in POLICIES}
    menu = simple['settingsTotals']
    settings = tuple(name for name in menu if name != joint.RETAIN)
    tuned = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling(simple['settingsBySubject'], settings, budgets)
    engines = joint.adaptive.screens(plan)
    selected = {f'{mode}/subject': tuned[mode]['settingsBySubject'] for mode in POLICIES}
    attained, _ = joint.adaptive.replay(plan, panels, {name: partial(_run, screen=engines[name]) for name in settings},
                                       selected, vectors)
    for mode in POLICIES:
        if any(attained[f'{mode}/subject'][key] != tuned[mode][key] for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError('The selected schedule must attain the budget-matched simple ceiling')

    paired = native.frozen.paired_effects.paired_effect
    return {'funding': funding, 'jointPasses': scores['joint-proof'], 'jointLookups': reference['jointLookups'],
            'originalLookups': reference['originalLookups'],
            'gepaAtOriginalBudget': gepa['subjectTunedGepa'][joint.ROUTED],
            'control': {mode: {key: reference['policies'][mode][key] for key in ('holdoutPasses', 'paidLookups')}
                        for mode in CONTROLS},
            'policies': {mode: {**receipts[mode], 'holdoutPasses': scores[mode], 'paidLookups': budgets[mode],
                                'subjectTunedSimple': tuned[mode],
                                'paired': {name: paired(vectors, mode, name, plan)
                                           for name in ('joint-proof', *CONTROLS, f'{mode}/subject')}}
                         for mode in POLICIES}}


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
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
