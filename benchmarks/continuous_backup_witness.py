"""Choose which paid incumbent miss receives the single terminal backup probe."""

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

from benchmarks import continuous_backup_value as previous
from cpo._contract import digest
from cpo.joint_order_qualification import validation_context
from cpo.two_sided_certificate_cycle import _run


backup, joint, native, transfer = previous.backup, previous.joint, previous.native, previous.transfer
continuous = backup.continuous
CONTROL = backup.PROBE
LAST, PEERS, COMPLEMENT, ADJUSTED = 'last-miss', 'paid-peers', 'finalist-miss', 'adjusted-peers'
POLICIES = (CONTROL, LAST, PEERS, COMPLEMENT, ADJUSTED)
ORIGINAL_NOMINATE = backup.nominate
ORIGINAL_ATTEMPT = backup.attempt
PEER_PRIOR_WEIGHT = 4


def unread_misses(incumbent, candidate, paid):
    return [row for (role, prompt, row), grade in paid.items()
            if role == 'validation' and prompt == incumbent and not grade
            and ('validation', candidate, row) not in paid]


def peer_counts(row, paid, incumbent, candidate):
    grades = [grade for (role, who, case), grade in paid.items() if role == 'validation' and case == row
              and who not in (incumbent, candidate)]
    return sum(grades), len(grades)


def choose_witness(mode, incumbent, candidate, rejected, paid):
    """Order viable misses by same-episode paid validation evidence."""
    rows = unread_misses(incumbent, candidate, paid)
    if mode == LAST:
        return rows[-1]

    def priority(row):
        wins, seen = peer_counts(row, paid, incumbent, candidate)
        complementary = mode == COMPLEMENT and paid.get(('validation', rejected, row)) is False
        return complementary, Fraction(wins + 1, seen + 2)

    return max(rows, key=priority)


def adjust_priority(option, row, incumbent, qualification_count, paid, initial, priors):
    """Update the old probe probability with a row-specific paid peer count."""
    base, (passes, seen) = option.counts
    original = priors.get(validation_context((base, (passes - 1, seen - 1))), priors[None])
    estimate = Fraction(original[3], original[2] + original[3])
    wins, peers = peer_counts(row, paid, incumbent, option.candidate)
    updated = (PEER_PRIOR_WEIGHT * estimate + wins) / (PEER_PRIOR_WEIGHT + peers)
    misses = sum(not event.passed for event in initial)
    posterior = priors.get(validation_context(option.counts), priors[None])
    probability, reads = backup.qualification_value(posterior, qualification_count - len(initial),
                                                    len(initial) - misses, misses)
    return updated * probability / (1 + updated * reads)


def revised_nomination(policy, mode, incumbent, roster, rejected, validation_count, qualification_count,
                       paid, initial, priors):
    options = ORIGINAL_NOMINATE(mode, incumbent, roster, rejected, validation_count, qualification_count,
                               paid, initial, priors)
    transformed = []
    for option in options:
        if option.validation_probe is None:
            transformed.append(option)
            continue
        row = choose_witness(policy, incumbent, option.candidate, rejected, paid)
        priority = (adjust_priority(option, row, incumbent, qualification_count, paid, initial, priors)
                    if policy == ADJUSTED else option.priority)
        transformed.append(replace(option, validation_probe=row, priority=priority))
    return sorted(transformed, key=lambda option: -option.priority)


def priced_bounds(groups, funding):
    """Bound hindsight allocation using settled charges and full start quotes."""
    extend = native.gepa.frontier.transfer.fitted.prior.ceiling.extend

    def choose(cap, slack):
        frontier = {0: 0}
        for options in groups:
            menu = {(0, 0), *((gain, used) for gain, used, quote in options if quote - used <= slack)}
            if len(menu) > 1:
                frontier = {gain: price for gain, price in extend(frontier, menu).items() if price <= cap}
        return max(frontier)

    maximum_slack = max((quote - used for options in groups for _, used, quote in options), default=0)
    # Padding the pooled budget by the largest eligible refund makes any
    # selected schedule affordable regardless of its dispatch order.
    return {'settledChargeUpperBound': choose(funding, maximum_slack),
            'fullyReservedLowerBound': max(choose(funding - slack, slack)
                                          for slack in range(min(funding, maximum_slack) + 1))}


def price_opportunities(episodes, opportunities, funding, priors):
    groups = []
    for index, options in opportunities.items():
        episode = episodes[index]
        start = sum(episode.cells[episode.incumbent][case] for case in episode.held)
        menu = set()

        def acquire(role, prompt, row):
            if (role, prompt, row) in episode.paid:
                raise ValueError('The diagnostic must price only grades absent from the original ledger')
            return bool(episode.cells[prompt][int(row)])

        for option in options:
            if option.price > funding:
                continue
            gain = sum(episode.cells[option.candidate][case] for case in episode.held) - start
            if gain <= 0:
                continue
            _, ledger, status = ORIGINAL_ATTEMPT(option, episode.incumbent, episode.qualification, episode.initial,
                                                  acquire, option.price, episode.seed, priors)
            if status == 'promoted':
                menu.add((gain, len(ledger), option.price))
        if menu:
            groups.append(menu)
    return priced_bounds(groups, funding)


def wider_menu(episodes, priors, funding):
    """Bound upside from offering any paid miss while buying at most one probe."""
    original, expanded = {}, {}
    flexible = 0
    for index, episode in enumerate(episodes):
        if episode.finalist is None or episode.deployed != episode.incumbent:
            continue
        options = ORIGINAL_NOMINATE(CONTROL, episode.incumbent, episode.roster, episode.finalist,
                                    episode.validation_count, len(episode.qualification), episode.paid,
                                    episode.initial, priors)
        more = []
        for option in options:
            if option.validation_probe is None:
                more.append(option)
            else:
                rows = unread_misses(episode.incumbent, option.candidate, episode.paid)
                more.extend(replace(option, validation_probe=row) for row in rows)
        if options:
            original[index], expanded[index] = options, more
            flexible += len(more) > len(options)
    return {'episodesWithChoiceOfWitness': flexible,
            'sealedWitnessGainUpperBound': backup.hindsight(episodes, original, funding),
            'anyWitnessGainUpperBound': backup.hindsight(episodes, expanded, funding),
            'sealedWitnessSettledBounds': price_opportunities(episodes, original, funding, priors),
            'anyWitnessSettledBounds': price_opportunities(episodes, expanded, funding, priors)}


def prepare(cohort):
    base, panels, models, static, trained, gepa, simple, joint_parent = backup.prepare(cohort)
    lock = previous.RECEIPTS[cohort]
    ref = json.loads(transfer.read_locked(f'docs/continuous-archive-backup-{cohort.lower()}-v1.json', lock))
    if ref['planSha256'] != digest(base):
        raise ValueError('Probe ordering needs the original budgeted backup plan')
    sources = {str(path.relative_to(transfer.ROOT)): sha256(path.read_bytes()).hexdigest()
               for path in map(Path, (__file__, backup.__file__, previous.__file__))}
    plan = {**base, 'protocol': 'continuous-backup-witness-v1', 'backupReceiptSha256': lock,
            'sourceSha256': {**base['sourceSha256'], **sources}, 'policies': POLICIES,
            'peerPriorWeight': PEER_PRIOR_WEIGHT,
            'scope': 'Change only the witness for candidates that already need a paid probe. Compare last miss, '
                     'same-episode paid peer pass rate, prioritizing a miss by the rejected finalist, and a '
                     'peer-adjusted probability used in the allocation. Reserve and buy at most one probe '
                     'per attempt. Verify the original control receipts and repriced simple controls. Compare '
                     'hindsight proof-floor and settled-charge bounds with the original witness and with any '
                     'eligible witness. Use full quotes to bound a conservatively funded schedule.'}
    return plan, panels, models, static, trained, gepa, simple, joint_parent, ref['results']


def rollout(policy, episodes, funding, priors):
    actual = Counter()

    def attempt(option, incumbent, qualification, initial, acquire, allowance, seed, prior):
        prompt, ledger, status = ORIGINAL_ATTEMPT(option, incumbent, qualification, initial, acquire, allowance, seed, prior)
        if option.validation_probe is not None:
            actual.update(passedProbes=int(status != 'no-repair'), probePromotions=int(status == 'promoted'))
        return prompt, ledger, status

    propose = ORIGINAL_NOMINATE if policy == CONTROL else partial(revised_nomination, policy)
    with patch.multiple(backup, nominate=propose, attempt=attempt):
        snapshots, stats = backup.rollout(CONTROL, episodes, funding, priors)
    return snapshots, {**stats, 'passedProbes': actual['passedProbes'], 'probePromotions': actual['probePromotions']}


def measure(plan, panels, models, static, trained, gepa, simple, joint_parent, reference):
    priors = previous.priors_of(trained)
    episodes = backup.capture(plan, panels, joint.adaptive.routed_runner(plan, models, static), priors, joint_parent)
    funding = reference['funding']
    diagnostic = wider_menu(episodes, priors, funding)
    baseline = reference['policies'][CONTROL]
    if diagnostic['sealedWitnessGainUpperBound'] != baseline['hindsightPassGainUpperBound']:
        raise ValueError('The baseline witness ceiling must reproduce')
    snapshots, receipts = {'joint-proof': {}}, {}
    for policy in POLICIES:
        snapshots[policy], receipts[policy] = rollout(policy, episodes, funding, priors)
    if any(receipts[CONTROL][key] != baseline[key] for key in receipts[CONTROL]
           if key not in ('passedProbes', 'probePromotions')):
        raise ValueError('The original one-probe receipt must reproduce')
    if any(receipts[policy]['eligibleEpisodes'] != baseline['eligibleEpisodes'] for policy in POLICIES):
        raise ValueError('The offer set must be preserved')

    vectors = {}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for index, episode in enumerate(episodes):
        subject = vectors.setdefault(episode.subject, {})
        for name, positions in snapshots.items():
            prompt = positions.get(index, episode.deployed)
            grades = [episode.cells[prompt][case] for case in episode.held]
            add(subject.setdefault(name, [0] * len(grades)), grades)
    scores = {name: sum(sum(rows[name]) for rows in vectors.values()) for name in snapshots}
    if scores[CONTROL] != baseline['holdoutPasses'] or scores['joint-proof'] != reference['jointPasses']:
        raise ValueError('The two archived final scores must reproduce')

    budgets = {policy: reference['jointLookups'] + receipts[policy]['lookups'] for policy in POLICIES}
    menu = simple['settingsTotals']
    settings = tuple(name for name in menu if name != joint.RETAIN)
    tuned = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling(simple['settingsBySubject'], settings, budgets)
    engines = joint.adaptive.screens(plan)
    selected = {f'{policy}/subject': tuned[policy]['settingsBySubject'] for policy in POLICIES}
    attained, _ = joint.adaptive.replay(plan, panels, {name: partial(_run, screen=engines[name]) for name in settings},
                                       selected, vectors)
    for policy in POLICIES:
        if any(attained[f'{policy}/subject'][key] != tuned[policy][key] for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError('The chosen simple schedule must attain its measured score and cost')
    paired = native.frozen.paired_effects.paired_effect
    return {'funding': funding, 'jointPasses': scores['joint-proof'], 'jointLookups': reference['jointLookups'],
            'originalLookups': reference['originalLookups'], 'witnessMenu': diagnostic,
            'priorSubjectTunedGepa': gepa['subjectTunedGepa'][joint.ROUTED],
            'policies': {policy: {**receipts[policy], 'holdoutPasses': scores[policy], 'paidLookups': budgets[policy],
                                  'deploymentChanges': sum(snapshots[policy].get(index, episode.deployed)
                                                           != snapshots[CONTROL].get(index, episode.deployed)
                                                           for index, episode in enumerate(episodes)),
                                  'subjectTunedSimple': tuned[policy],
                                  'paired': {name: paired(vectors, policy, name, plan)
                                             for name in (CONTROL, 'joint-proof', f'{policy}/subject')}}
                         for policy in POLICIES}}


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
