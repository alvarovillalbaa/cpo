"""Measure the sealed witness panels' sensitivity to a single incorrect policy branch."""

from collections import Counter
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from random import Random

from benchmarks import grounded, grounded_fixture, grounded_staged as staged, grounded_witness_episode as episode
from benchmarks import typed_policy as policy, witness_halving_physical_limits as bound
from cpo._contract import digest


TOPICS = (*policy.QUEUES, 'general-inquiry', 'unlisted-topic')
REGIMES = {'ticket': tuple((topic,) for topic in TOPICS), 'warehouse': policy.WAREHOUSE, 'outage': policy.OUTAGE}
STRESS_SEED = 955127


def regime(task, row):
    fields = grounded_fixture.facts(row['input'])
    if task == 'ticket':
        return (fields['Topic'],)
    if task == 'warehouse':
        available = int(fields['On hand']) - int(fields['Reserved']) - int(fields['Damaged'])
        stock = 'positive' if available > 0 else 'depleted' if available < 0 else 'zero'
        return stock, fields['Inspection'], fields['Tier'], fields['Site']
    duration, plan = int(fields['Duration minutes']), fields['Plan']
    unbounded = duration // (3 if plan == 'PLUS' else 5) if duration >= 30 else 0
    capped = int(fields['Monthly fee whole USD']) // 10 < unbounded
    return duration, plan, capped, fields['Evidence']


def panels(groups):
    width = episode.SPLITS['admission'] // episode.CYCLES
    return {
        **{name: rows for name, rows in groups.items() if name not in ('train', 'admission')},
        'nativeValidationAnchors': groups['validation'][:episode.GEPA_ANCHORS],
        **{f'train{i + 1}': groups['train'][i * episode.TRAIN_ROWS:(i + 1) * episode.TRAIN_ROWS]
           for i in range(episode.CYCLES)},
        **{f'admission{i + 1}': groups['admission'][i * width:(i + 1) * width] for i in range(episode.CYCLES)},
    }


def stress_cases(groups, prior):
    """Add exactly one fresh synthetic case per regime absent from confirmation."""
    rng = Random(STRESS_SEED)
    generated = {}
    for task, regions in groups.items():
        observed = {regime(task, row) for row in regions['confirmation']}
        seen = {row['input'] for archive in (groups, *prior) for rows in archive[task].values() for row in rows}
        rows = []
        index = 20_000
        for branch in REGIMES[task]:
            if branch in observed:
                continue
            for _ in range(256):
                if task == 'ticket':
                    index += (TOPICS.index(branch[0]) - index) % len(TOPICS)
                    inputs, expected, critical = policy.ticket(index, rng)
                else:
                    make = policy.warehouse if task == 'warehouse' else policy.outage
                    inputs, expected, critical = make(index, rng, branch)
                index += 1
                if inputs not in seen:
                    break
            else:
                raise ValueError('Could not create fresh facts for a missing regime')
            row = {'id': f'witness-regime-stress-{task}-{len(rows) + 1:02}', 'input': inputs,
                   'expected': expected, 'critical': critical}
            if regime(task, row) != branch:
                raise ValueError('The generated case differs from the missing regime')
            seen.add(inputs)
            rows.append(row)
        generated[task] = rows
    return generated


def balanced_confirmation(groups, added):
    """Cover every warehouse regime across scoring without increasing the panel size."""
    original = groups['warehouse']['confirmation']
    development = {regime('warehouse', row) for row in groups['warehouse']['holdout']}
    missing = set(REGIMES['warehouse']) - development
    replacements = [row for row in added['warehouse'] if regime('warehouse', row) in missing]

    def balance(rows):
        return Counter((aspect, value) for row in rows for aspect, value in
                       zip(('critical', 'tier', 'site'), (row['critical'], *regime('warehouse', row)[2:]), strict=True))

    target = balance(original)
    for kept in combinations(original, len(original) - len(replacements)):
        panel = [*kept, *replacements]
        if balance(panel) == target and {regime('warehouse', row) for row in panel} >= missing:
            return panel
    raise ValueError('No same-size completion preserves the confirmation balance')


def mutation(task, expected):
    if task == 'ticket':
        return {**expected, 'queue': 'GENERAL' if expected['queue'] != 'GENERAL' else policy.QUEUES['refund-question']}
    if task == 'warehouse':
        return {**expected, 'action': 'REVIEW' if expected['action'] == 'HOLD' else 'HOLD'}
    return {**expected, 'credit': expected['credit'] + 1}


def score_mutation(groups, target, branch):
    outcomes = {}
    for task, rows in groups.items():
        scored = []
        for row in rows:
            expected = row['expected']
            response = mutation(task, expected) if task == target and regime(task, row) == branch else expected
            passed, _ = grounded.score(json.dumps(response), expected)
            scored.append((row, passed))
        outcomes[task] = scored
    return outcomes


def gate_status(scored, gate):
    """Compare a faulty prompt with an exact control and with a control sharing its error."""
    verdicts = {}
    for shared in (False, True):
        outcomes = {task: [{'id': row['id'], 'critical': row['critical'],
                             'passes': {'initial': passed if shared else True, 'cpo': passed,
                                        'control': passed if shared else True}}
                            for row, passed in panel for _ in range(grounded.REPEATS)]
                    for task, panel in scored.items()}
        verdicts['errorSharedByControl' if shared else 'exactControl'] = staged.grade(
            outcomes, {'cpo': 90, 'control': 100}, gate, controls=('control',))['qualified']
    return verdicts


def summarize():
    bound.prepare()
    groups = episode.cohorts()
    added = stress_cases(groups, (policy.cohorts(grounded.SEED), staged.cohorts()))
    repaired = balanced_confirmation(groups, added)
    partitions = {task: {**panels(regions), 'stress': added[task]} for task, regions in groups.items()}
    phases = {'holdout': episode.DEVELOPMENT_GATE, 'confirmation': episode.CONFIRMATION_GATE}
    results = {}
    for task, cases in partitions.items():
        counts = {label: len({regime(task, row) for row in rows}) for label, rows in cases.items()}
        trials = []
        for branch in REGIMES[task]:
            mismatches = {label: sum(regime(task, row) == branch for row in rows) for label, rows in cases.items()}
            gates = {}
            for phase, gate in phases.items():
                scored = score_mutation({name: partitions[name][phase] for name in partitions}, task, branch)
                if sum(not passed for _, passed in scored[task]) != mismatches[phase]:
                    raise ValueError('An incorrect policy branch disagrees with its expected detection count')
                gates[phase] = gate_status(scored, gate)
            stress = score_mutation({name: added[name] for name in partitions}, task, branch)
            trials.append({'regime': branch, 'mismatchedRowsByPanel': mismatches, 'qualified': gates,
                           'stressDetects': any(not passed for _, passed in stress[task])})
        results[task] = {'regimeCount': len(REGIMES[task]), 'regimesByPanel': counts,
                         'invisibleInBothSealedScoringPanels': sum(
                             not trial['mismatchedRowsByPanel']['holdout'] and
                             not trial['mismatchedRowsByPanel']['confirmation'] for trial in trials),
                         'confirmationMissedByExactControl': sum(trial['qualified']['confirmation']['exactControl']
                                                                 for trial in trials),
                         'confirmationQualifiedWithSharedError': sum(
                             trial['qualified']['confirmation']['errorSharedByControl'] for trial in trials),
                         'tests': trials}
    proposed = {task: partitions[task]['confirmation'] for task in partitions}
    proposed['warehouse'] = repaired
    warehouse_trials = results['warehouse']['tests']
    for trial in warehouse_trials:
        scored = score_mutation(proposed, 'warehouse', trial['regime'])
        trial['balancedConfirmationQualified'] = gate_status(scored, episode.CONFIRMATION_GATE)
    blind = sum(trial['qualified']['holdout']['exactControl'] and trial['balancedConfirmationQualified']['exactControl']
                for trial in warehouse_trials)
    return {'protocol': 'grounded-witness-regime-coverage-v1', 'portablePlanSha256': bound.PORTABLE,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'datasetSha256': digest(groups),
            'stressSeed': STRESS_SEED, 'stressDatasetSha256': digest(added), 'stressRows': added,
            'alternativeWarehouseConfirmation': {'datasetSha256': digest(repaired), 'rows': repaired,
                                                 'invisibleInBothScoringPanels': blind},
            'providerRequests': 0, 'results': results}


if __name__ == '__main__':
    print(json.dumps(summarize(), sort_keys=True, indent=2))
