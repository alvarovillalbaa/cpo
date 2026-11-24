"""Spend verified lookup savings on independently qualified terminal backups."""

import argparse
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from functools import cache, partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import joint_archive_proof as joint
from cpo._contract import digest
from cpo.joint_order_qualification import _order, finish_joint_order, validation_context
from cpo.optimizer import Row
from cpo.paired_qualification import QualificationObservation
from cpo.two_sided_certificate_cycle import _run


continuous, native, transfer = joint.continuous, joint.native, joint.transfer
simple_controls = joint.adaptive.controls
PAID, REPAIR, PROBE = 'paid-certificate', 'paid-repair', 'one-probe'
MODES = (PAID, REPAIR, PROBE)
FIT = 'docs/joint-archive-proof-fit-v1.json'
FIT_SHA = '4f9004b8b10323b9571523e3cd2de324767731a6c399d6a0e4ceaeaf6c2d769d'
PARENT = dict(zip(continuous.COHORTS, (
    'eff95c9c70a251b3fe665387e2b21cf6221607f690fda16229dbca57a5a39d79',
    '4852e0a6fe11573245872df60aaf6599b9b16a2074f5c72f85f430f43c552aa1',
    '8c0dd7e0c3c625d3cb6689caa45451d96baa9ee264344559663575eb99d2d76a',
    '67a37c10ed904925e0d5e4a6280b6211c95fb7a6a60de3ec2b11bfb2d3e3948f',
    '94c0decb4f0858fcc5fea3c63454e1954855c67ceb81835b4eb5a9a03e795d76',
    'f09d6752924f66982134f65cb6e5fd7dc356777db287828f95834e3977ae2b3a',
    'c3005adb6006ec61af239f52186aea7479d4a5299e68c143bba3bb1c843bf56f',
), strict=True))


@dataclass(frozen=True)
class Opportunity:
    candidate: str
    validation_probe: str | None
    counts: tuple
    price: int
    priority: Fraction


@dataclass(frozen=True)
class Episode:
    subject: str
    seed: int
    incumbent: str
    deployed: str
    finalist: str | None
    roster: tuple
    qualification: tuple
    held: tuple
    cells: dict
    paid: dict
    initial: tuple
    validation_count: int


@cache
def qualification_value(weights, untouched, base_passes, base_misses):
    """Return modeled probability of a strict gain and expected new reads."""
    a, b, c, d = weights
    # A pair contributes zero, one or two favorable bits.
    untouched_mass = (a, b + c, d)
    options = [untouched_mass] * untouched + [(a, b)] * base_passes + [(c, d)] * base_misses
    mass = [1]
    for pair in options:
        updated = [0] * (len(mass) + len(pair) - 1)
        for left, weight in enumerate(mass):
            for right, likelihood in enumerate(pair):
                updated[left + right] += weight * likelihood
        mass = updated
    size = untouched + base_passes + base_misses
    threshold = size + 1 - base_misses
    chance = Fraction(sum(mass[threshold:]), sum(mass))
    spend, _ = _order(size, 1, weights, (untouched, base_passes, base_misses, 0, 0), base_misses)
    return chance, spend


def nominate(mode, incumbent, roster, rejected, validation_count, qualification_count, paid, initial, priors):
    """Rank terminal possibilities using the cycle's already charged ledger."""
    base = {row: grade for (role, prompt, row), grade in paid.items()
            if role == 'validation' and prompt == incumbent}
    base_misses = sum(not event.passed for event in initial)
    base_passes = len(initial) - base_misses
    remaining = qualification_count - len(initial)
    price = 2 * qualification_count - len(initial)
    choices = []
    for prompt in roster:
        if prompt == rejected:
            continue
        observed = {row: grade for (role, who, row), grade in paid.items()
                    if role == 'validation' and who == prompt}
        lower = len(base) - sum(base.values()) + sum(observed.values()) - validation_count
        upper = validation_count - sum(base.values()) - (len(observed) - sum(observed.values()))
        if upper < 1:
            continue
        has_repair = any(not grade and observed.get(row) is True for row, grade in base.items())
        has_loss = any(grade and observed.get(row) is False for row, grade in base.items())
        if (mode == PAID and lower < 1) or (mode != PAID and has_loss):
            continue
        probe = None
        if not has_repair:
            if mode != PROBE:
                continue
            probe = next((row for row, grade in base.items() if not grade and row not in observed), None)
            if probe is None:
                continue
        counts = ((sum(base.values()), len(base)), (sum(observed.values()), len(observed)))
        posterior_counts = counts if probe is None else (counts[0], (counts[1][0] + 1, counts[1][1] + 1))
        weights = priors.get(validation_context(posterior_counts), priors[None])
        chance, spend = qualification_value(weights, remaining, base_passes, base_misses)
        if probe is not None:
            context = priors.get(validation_context(counts), priors[None])
            probe_chance = Fraction(context[3], context[2] + context[3])
            chance *= probe_chance
            spend = 1 + probe_chance * spend
        if chance and spend:
            choices.append(Opportunity(prompt, probe, posterior_counts, price + int(probe is not None), chance / spend))
    return sorted(choices, key=lambda option: -option.priority)


def attempt(option, incumbent, qualification, initial, acquire, allowance, seed, priors):
    """Reserve every possibly uncached reply before opening either proof."""
    if option.price > allowance:
        return incumbent, (), 'unfunded'
    fresh = []

    def buy(role, prompt, row):
        if len(fresh) == option.price:
            raise ValueError('The backup must fit inside its full reservation')
        grade = acquire(role, prompt, row)
        if type(grade) is not bool:
            raise ValueError('Backup qualification requires an exact binary grade')
        fresh.append((role, prompt, row, grade))
        return grade

    if option.validation_probe is not None and not buy('validation', option.candidate, option.validation_probe):
        return incumbent, tuple(fresh), 'no-repair'
    history = list(initial)

    def read(prompt, row, repeat):
        grade = buy('qualification', prompt, row.id)
        history.append(QualificationObservation(prompt, row.id, repeat, grade))
        return grade

    outcome = finish_joint_order(incumbent, option.candidate, qualification, read, history, option.counts,
                                 1, seed, priors=priors)
    return outcome.prompt, tuple(fresh), outcome.status


def prepare(cohort):
    fit = transfer.read_locked(FIT, FIT_SHA)
    parent, panels, models, static, trained, reference, simple = joint.prepare(cohort, fit)
    receipt = json.loads(transfer.read_locked(f'docs/joint-archive-proof-{cohort.lower()}-v1.json', PARENT[cohort]))
    if receipt['planSha256'] != digest(parent):
        raise ValueError('The paired proof replay and backup layout must match')
    plan = {**parent, 'protocol': 'continuous-archive-backup-v1', 'parentProofSha256': PARENT[cohort],
            'sourceSha256': {**parent['sourceSha256'], Path(__file__).name: sha256(Path(__file__).read_bytes()).hexdigest()},
            'backupPolicies': MODES, 'controls': list(simple_controls.settings(parent['caseCounts'][1])),
            'scope': 'Reproduce all three measured cycles and run backups only after proved rejection in the last '
                     'cycle. Give each policy the same savings between original and joint proof ordering. '
                     'Reuse paid incumbent grades, reserve every possible unseen reply and attempt at most one '
                     'backup per episode. Rank using conditional qualification chance per expected additional read. '
                     'For a strict validation certificate require an exact gain. For the repair policies require a '
                     'paid paired repair with no observed loss. One-probe may buy one missing challenger grade at '
                     'an observed incumbent miss for any remaining challenger. Promotion needs exact '
                     'independent qualification. Replay the best common and subject-tuned simple controls at '
                     'actual spend. Bound the missed upside using hindsight grades and the minimum proof price.'}
    return plan, panels, models, static, trained, reference, simple, receipt['results']


def capture(plan, panels, runner, priors, parent):
    """Reproduce the frozen controller and keep only terminal decision state."""
    run = native.paired.cycle.execute_path
    point = native.paired.reference.point
    episodes, cost = [], 0
    certify = partial(finish_joint_order, priors=priors)
    with patch.object(joint.two_sided_certificate_cycle, '_finish_with_partner_evidence', certify):
        for subject, model, matrix in panels:
            cells, _ = transfer.case_cells(matrix)
            paths = []
            for seed in plan['seeds']:
                incumbent, stages = continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
                trace = []
                for local_seed, roster, roles in stages:
                    result, paid = run(runner, cells, incumbent, roster, roles, local_seed, plan['fullRosterCap'], 1)
                    trace.append((incumbent, result.prompt, point(cells, roles[-1], result, paid)[2]))
                    cost += len(paid)
                    incumbent = result.prompt
                paths.append(trace)
                original = trace[-1][0]
                finalist = result.search.finalist if result.qualification.status == 'rejected' else None
                initial = tuple(event for event in result.qualification.observations if event.prompt == original)
                rows = tuple(Row(str(case), 'qualification') for case in roles[2])
                episodes.append(Episode(subject, local_seed, original, result.prompt, finalist, tuple(roster), rows, tuple(roles[-1]),
                                        cells, paid, initial, len(roles[1])))
            if digest(paths) != parent['jointPanelHashes'][f'{subject}/{model}']:
                raise ValueError('Every joint-proof trace must reproduce before introducing backups')
    if cost != parent['pairedProofCost']['jointLookups']:
        raise ValueError('The original joint proof price must reproduce')
    return episodes


def hindsight(episodes, opportunities, funding):
    """Upper bound after relaxing reply order and reservation timing."""
    extend = native.gepa.frontier.transfer.fitted.prior.ceiling.extend
    frontier = {0: 0}
    for index, options in opportunities.items():
        episode = episodes[index]
        current = sum(episode.cells[episode.deployed][case] for case in episode.held)
        base_misses = sum(not event.passed for event in episode.initial)
        menu = {(0, 0)}
        for option in options:
            if option.price > funding:
                continue
            candidate = episode.cells[option.candidate]
            if option.validation_probe is not None and not candidate[int(option.validation_probe)]:
                continue
            if sum(candidate[int(row.id)] - episode.cells[episode.incumbent][int(row.id)]
                   for row in episode.qualification) <= 0:
                continue
            gain = sum(candidate[case] for case in episode.held) - current
            floor = len(episode.qualification) + 1 - base_misses + int(option.validation_probe is not None)
            if gain > 0:
                menu.add((gain, floor))
        if len(menu) > 1:
            frontier = {gain: cost for gain, cost in extend(frontier, menu).items() if cost <= funding}
    return max(frontier)


def rollout(mode, episodes, funding, priors):
    snapshots, opportunities, choices, paths = {}, {}, [], []
    counts = Counter(dict.fromkeys(('eligibleEpisodes', 'attempts', 'proofAttempts', 'promotions', 'validationProbes'),
                                    0))
    for index, episode in enumerate(episodes):
        if episode.finalist is not None and episode.deployed == episode.incumbent:
            options = nominate(mode, episode.incumbent, episode.roster, episode.finalist, episode.validation_count,
                               len(episode.qualification), episode.paid, episode.initial, priors)
            if options:
                counts['eligibleEpisodes'] += 1
                opportunities[index] = options
                choices.extend((-option.priority, index, rank, option) for rank, option in enumerate(options))
    balance = funding
    for _, index, _, option in sorted(choices):
        if index in snapshots or option.price > balance:
            continue
        episode = episodes[index]

        def acquire(role, prompt, row):
            if (role, prompt, row) in episode.paid:
                raise ValueError('The backup must not rebuy an earlier grade')
            return bool(episode.cells[prompt][int(row)])

        prompt, ledger, status = attempt(option, episode.incumbent, episode.qualification, episode.initial,
                                         acquire, balance, episode.seed, priors)
        balance -= len(ledger)
        snapshots[index] = prompt
        counts.update(attempts=1, proofAttempts=int(status != 'no-repair'), promotions=int(status == 'promoted'),
                      validationProbes=int(option.validation_probe is not None), lookups=len(ledger))
        if status != 'no-repair':
            exact = sum(episode.cells[option.candidate][int(row.id)] - episode.cells[episode.incumbent][int(row.id)]
                        for row in episode.qualification)
            if status != ('promoted' if exact > 0 else 'rejected'):
                raise ValueError('The backup must settle the original exact independent qualification')
        paths.append((index, option.candidate, prompt, ledger))
    if balance < 0 or counts['lookups'] != funding - balance:
        raise ValueError('Every backup read must reconcile with the cohort budget')
    return snapshots, {**counts, 'lookups': funding - balance, 'unspent': balance, 'backupPathSha256': digest(paths),
                       'hindsightPassGainUpperBound': hindsight(episodes, opportunities, funding)}


def measure(plan, panels, models, static, trained, reference, simple, parent):
    priors = {None if key == 'pooled' else tuple(map(int, key.split('/'))): tuple(weights)
              for key, weights in trained['weights'].items()}
    episodes = capture(plan, panels, joint.adaptive.routed_runner(plan, models, static), priors, parent)
    baseline = parent['pairedProofCost']
    funding = baseline['originalLookups'] - baseline['jointLookups']
    snapshots = {base: {} for base in ('joint-proof', *MODES)}
    details = {}
    for mode in MODES:
        snapshots[mode], details[mode] = rollout(mode, episodes, funding, priors)
    scores = {}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for index, episode in enumerate(episodes):
        vectors = scores.setdefault(episode.subject, {})
        for mode, choices in snapshots.items():
            prompt = choices.get(index, episode.deployed)
            grades = [episode.cells[prompt][case] for case in episode.held]
            add(vectors.setdefault(mode, [0] * len(grades)), grades)
    if sum(sum(rows['joint-proof']) for rows in scores.values()) != baseline['holdoutPasses']:
        raise ValueError('The original joint proof score must reproduce')
    paired = native.frozen.paired_effects.paired_effect
    menu = simple['settingsTotals']
    settings = tuple(name for name in menu if name != joint.RETAIN)
    budgets = {mode: baseline['jointLookups'] + receipt['lookups'] for mode, receipt in details.items()}
    ceilings = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling(
        simple['settingsBySubject'], settings, budgets)
    common = {mode: native.gepa.best_fixed(menu, settings, budget) for mode, budget in budgets.items()}
    subjects = scores.keys()
    selected = {f'{mode}/common': (dict.fromkeys(subjects, common[mode]['setting']), common[mode])
                for mode in MODES}
    selected.update({f'{mode}/subject': (ceilings[mode]['settingsBySubject'], ceilings[mode]) for mode in MODES})
    engines = joint.adaptive.screens(plan)
    comparisons, _ = joint.adaptive.replay(plan, panels, {name: partial(_run, screen=engines[name]) for name in settings},
                                           {name: schedule for name, (schedule, _) in selected.items()}, scores)
    for name, (_, expected) in selected.items():
        if any(comparisons[name][key] != expected[key] for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError('The best simple controls must reproduce their exact scores and costs')
    return {'funding': funding, 'originalLookups': baseline['originalLookups'], 'jointLookups': baseline['jointLookups'],
            'jointPasses': baseline['holdoutPasses'], 'priorSubjectTunedGepa': reference['subjectTunedGepa'][joint.ROUTED],
            'policies': {mode: {**receipt, 'paidLookups': budgets[mode],
                                'holdoutPasses': sum(sum(rows[mode]) for rows in scores.values()),
                                'pairedAgainstJoint': paired(scores, mode, 'joint-proof', plan),
                                'pairedAgainstCommonSimple': paired(scores, mode, f'{mode}/common', plan),
                                'pairedAgainstSubjectTunedSimple': paired(scores, mode, f'{mode}/subject', plan),
                                'bestCommonSimple': common[mode],
                                'subjectTunedSimple': ceilings[mode]} for mode, receipt in details.items()}}


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
