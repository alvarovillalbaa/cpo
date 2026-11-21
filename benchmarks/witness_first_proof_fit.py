"""Transfer a paid-evidence ranker trained on exact first-proof outcomes."""

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from math import fsum
from pathlib import Path
from typing import Callable
from unittest.mock import patch

from benchmarks import witness_shared_rival_ranking as previous
from benchmarks.witness_admission_retry import outcomes as original_outcomes
from cpo._contract import digest


ROOT, RANKING, retry, FULL, CAP = previous.ROOT, previous.RANKING, previous.retry, previous.FULL, previous.CAP
REFERENCE = 'docs/witness-shared-rival-ranking-results-v1.json'
REFERENCE_SHA256 = 'ee0f6d767cf3cf65dd8de9e67bf829b860a47ea6dfaf0c90c5aa83b189a20b3c'
RATE, PROMOTION, EFFICIENCY = 'smoothed-pass-rate', 'fitted-promotion', 'fitted-promotions-per-lookup'
METHODS = (FULL, RATE, PROMOTION, EFFICIENCY)
FEATURES = ('original-nominee', 'pass-rate', 'validation-coverage', 'paired-wins', 'paired-losses',
            'paired-coverage', 'relative-case-performance', 'paired-gain-over-nominee', 'tie-reserve-size')
RIDGE = 1 / 128


@dataclass(frozen=True)
class Episode:
    subject: str
    nominee: str
    rate_choice: str
    inputs: dict[str, tuple[float, ...]]
    prove: Callable[[str], retry.Decision]
    score: Callable[[str], tuple[int, ...]]


def prepare():
    parent, _, data = previous.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('Use the published first-proof traces and backup audit')
    plan = {key: parent[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed')}
    plan.update(protocol='witness-first-proof-fit-v1', parentPlanSha256=digest(parent),
                parentReceiptSha256=REFERENCE_SHA256, sourceSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                methods=METHODS, features=FEATURES, ridge=RIDGE, proofCap=CAP, primary=EFFICIENCY,
                rule='At the original first nomination, rerank the already-paid enrolled candidates using only '
                'the paid validation grades and the sealed panel layout. Each nominee receives one exact proof '
                'on its assigned base and tie rows. Keep the original trigger and leave no-nominee stops alone.',
                fit='Center features and labels within each multi-candidate episode. Fit episode-weighted ridge '
                'on other-family exact promotion or promotion per realized proof lookup. Holdout grades never '
                'enter feature extraction, training labels, or nominee choice.',
                gate='The primary fixed ranker must have a positive paired lower endpoint against the original '
                'single proof and spend no more than the original seeded control on all cohorts.')
    return plan, reference, data


def features(start, nominee, pool, grades, validation_count, extension):
    rows = {}
    by_case = {}
    for (prompt, case), passed in grades.items():
        rows.setdefault(prompt, {})[case] = passed
        by_case.setdefault(case, Counter()).update(passes=passed, count=1)
    old, original = rows.get(start, {}), rows[nominee]
    result = {}
    for prompt in pool:
        seen = rows[prompt]
        pairs, common = seen.keys() & old.keys(), seen.keys() & original.keys()
        wins = sum(seen[case] and not old[case] for case in pairs)
        losses = sum(old[case] and not seen[case] for case in pairs)
        peer = fsum(passed - (by_case[case]['passes'] - passed + 1) / (by_case[case]['count'] + 1)
                    for case, passed in seen.items())
        result[prompt] = (float(prompt == nominee), (sum(seen.values()) + 1) / (len(seen) + 2),
                          len(seen) / validation_count, wins / (len(pairs) + 2), losses / (len(pairs) + 2),
                          len(pairs) / validation_count, peer / (len(seen) + 2),
                          sum(seen[case] - original[case] for case in common) / (len(common) + 2),
                          extension[prompt] / CAP)
    return result


def collect(plan, data, reference):
    _, panels, _, _, _ = data
    subjects = {id(panel['correctness']): panel['subject'] for panel in panels}
    episodes = []

    def outcomes(matrix, held, start, layouts, active, policy, nomination):
        original = original_outcomes(matrix, held, start, layouts, active, policy, nomination)
        result = {retry.BASE: original[retry.BASE], FULL: original[FULL]}
        nominee = nomination.original
        if nominee is None:
            return result
        roster = {prompt: slot for slot, layout in enumerate(layouts) for prompt in layout['alternatives']}
        paid = {prompt for prompt, _ in nomination.grades}
        if nominee not in roster or nominee not in paid:
            raise ValueError('The original nominee must be enrolled and already paid')
        pool = (nominee, *(prompt for prompt in roster if prompt != nominee and prompt in paid))
        validation = {case for layout in layouts for case in layout['validation']}
        forbidden = set(held) | validation | {case for layout in layouts for case in layout['train']}
        panels = [tuple(layout['qualify']) for layout in layouts]
        if forbidden.intersection(case for rows in panels for case in rows):
            raise ValueError('First-proof cases must be independent of search and holdout')
        reserves = [tuple(case for rows in panels[:slot] for case in rows)[:active['maximumExtensionRows']]
                    for slot in range(len(panels))]
        extension = {prompt: len(reserves[roster[prompt]]) for prompt in pool}
        inputs = features(start, nominee, pool, nomination.grades, len(validation), extension)
        settled = {nominee: original[FULL]}

        def grade(prompt, case):
            if case in forbidden:
                raise ValueError('Qualification left its independent cases')
            return matrix[int(prompt)][case] == '1'

        def prove(prompt):
            if prompt not in settled:
                slot = roster[prompt]
                exact = retry.scalar_proof(start, prompt, panels[slot], reserves[slot], grade, nomination.grades,
                                           active['minimumQualificationGain'], CAP)
                settled[prompt] = retry.Decision(exact.prompt, len(exact.observations), exact.status)
            return settled[prompt]

        def score(prompt):
            return tuple(int(matrix[int(prompt)][case] == '1') for case in held)

        rate_choice = RANKING.rank(nomination, start, roster)[RATE]
        episodes.append(Episode(subjects[id(matrix)], nominee, rate_choice, inputs, prove, score))
        return result

    with patch.multiple(retry, METHODS=(retry.BASE, FULL), outcomes=outcomes):
        groups, traces = retry.measure(*data, plan['fallbackValidationCap'])
    totals = {arm: sum((group['counts'][arm] for group in groups.values()), Counter()) for arm in (retry.BASE, FULL)}
    if traces != reference['panelTraceSha256'] or any(
            totals[arm][key] != reference['totals'][arm].get(key, 0)
            for arm in totals for key in ('holdoutPasses', 'paidLookups', 'proofLookups', 'promotions')):
        raise ValueError('The original search and first-proof controls changed')
    return groups, episodes, totals, traces


def fit(batches):
    """Solve the episode-weighted ridge normal equations with centered data."""
    width = len(FEATURES)
    system = [[0.0] * (width + 1) for _ in range(width)]
    if not batches:
        raise ValueError('A ranker needs development episodes with multiple paid candidates')
    for episode in batches:
        size = len(episode)
        means = [fsum(inputs[index] for inputs, _ in episode) / size for index in range(width)]
        average = fsum(label for _, label in episode) / size
        for inputs, label in episode:
            centered = [value - mean for value, mean in zip(inputs, means, strict=True)]
            for i, value in enumerate(centered):
                for j, other in enumerate(centered):
                    system[i][j] += value * other / size
                system[i][-1] += value * (label - average) / size
    for i in range(width):
        system[i][i] += RIDGE * len(batches)
    for i, pivot in enumerate(system):
        for row in system[i + 1:]:
            scale = row[i] / pivot[i]
            row[i:] = [value - scale * lead for value, lead in zip(row[i:], pivot[i:], strict=True)]
    weights = [0.0] * width
    for i in reversed(range(width)):
        row = system[i]
        weights[i] = (row[-1] - fsum(row[j] * weights[j] for j in range(i + 1, width))) / row[i]
    return weights


def train(episodes):
    rows = {method: [] for method in (PROMOTION, EFFICIENCY)}
    labels, positives = 0, 0
    for episode in episodes:
        if len(episode.inputs) < 2:
            continue
        scores = [(inputs, episode.prove(prompt)) for prompt, inputs in episode.inputs.items()]
        labels += len(scores)
        positives += sum(result.status == 'promoted' for _, result in scores)
        rows[PROMOTION].append([(inputs, float(result.status == 'promoted')) for inputs, result in scores])
        rows[EFFICIENCY].append([(inputs, (result.status == 'promoted') / max(1, result.lookups))
                                 for inputs, result in scores])
    weights = {method: fit(batches) for method, batches in rows.items()}
    return weights, {'episodes': len(rows[PROMOTION]), 'candidateLabels': labels, 'promotedLabels': positives,
                     'weights': {method: dict(zip(FEATURES, vector, strict=True)) for method, vector in weights.items()}}


def choose(inputs, weights):
    return max(inputs, key=lambda prompt: fsum(a * b for a, b in zip(inputs[prompt], weights, strict=True)))


def compare(plan, groups, episodes, totals, traces, weights):
    votes = {subject: {'cases': {arm: unit['cases'][FULL].copy() for arm in METHODS},
                       'decisionsPerCase': unit['decisionsPerCase']} for subject, unit in groups.items()}
    changes = {arm: Counter() for arm in METHODS[1:]}
    for episode in episodes:
        original = episode.prove(episode.nominee)
        old = episode.score(original.prompt)
        routes = {RATE: episode.rate_choice, **{arm: choose(episode.inputs, vector) for arm, vector in weights.items()}}
        for arm, prompt in routes.items():
            result = episode.prove(prompt)
            scores = votes[episode.subject]['cases'][arm]
            scores[:] = [base + new - before for base, new, before in zip(scores, episode.score(result.prompt), old, strict=True)]
            changes[arm].update(changedNominees=int(prompt != episode.nominee),
                                changedDeployments=int(result.prompt != original.prompt),
                                promotionDelta=int(result.status == 'promoted') - int(original.status == 'promoted'),
                                lookupDelta=result.lookups - original.lookups)
    pairs = {}
    for arm, change in changes.items():
        totals[arm] = {'holdoutPasses': sum(sum(unit['cases'][arm]) for unit in votes.values()),
                       'paidLookups': totals[FULL]['paidLookups'] + change['lookupDelta'],
                       'promotions': totals[FULL]['promotions'] + change['promotionDelta'], **change}
        with patch.object(RANKING.paired_bands, 'BASELINE', FULL):
            pairs[arm] = RANKING.paired_bands.paired_ranges(votes, arm, plan)['subjectsAndCases']
    return {'totals': totals, 'pairedVsOriginal': pairs, 'nominations': len(episodes),
            'multiCandidateEpisodes': sum(len(episode.inputs) > 1 for episode in episodes), 'panelTraceSha256': traces,
            'qualifies': totals[EFFICIENCY]['paidLookups'] <= totals[retry.BASE]['paidLookups']
            and pairs[EFFICIENCY]['interval95PercentagePoints'][0] > 0}


def execute(plan, reference, data):
    gathered = {phase: collect(plan, data[phase], reference['cohorts'][phase]) for phase in RANKING.PHASES}
    bbh = RANKING.gap.paired.BBH
    mmlu_phases = RANKING.gap.paired.replay.PHASES
    mmlu = [episode for phase in mmlu_phases for episode in gathered[phase][1]]
    mmlu_subjects = {subject for phase in mmlu_phases for subject in gathered[phase][0]}
    if mmlu_subjects.intersection(gathered[bbh][0]):
        raise ValueError('Training and evaluation subjects must be disjoint')
    bb_weights, bb_summary = train(gathered[bbh][1])
    mmlu_weights, mmlu_summary = train(mmlu)
    cohorts = {phase: compare(plan, *entry, mmlu_weights if phase == bbh else bb_weights)
               for phase, entry in gathered.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0,
            'training': {bbh: bb_summary, 'mmlu': mmlu_summary}, 'cohorts': cohorts,
            'qualifies': all(row['qualifies'] for row in cohorts.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    report = execute(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
