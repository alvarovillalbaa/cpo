"""Learn downstream holdout gain for one exact first proof on another family."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from math import fsum
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_first_proof_fit as parent
from cpo._contract import digest


ROOT, RANKING, retry, FULL, CAP = parent.ROOT, parent.RANKING, parent.retry, parent.FULL, parent.CAP
REFERENCE = 'docs/witness-first-proof-fit-results-v1.json'
REFERENCE_SHA256 = '4fdb0fd587e38aba5104588a228e92e6a6a6f74efbcf97917f19fd0b5be309b2'
GAIN, GUARDED = 'fitted-deployed-gain', 'fitted-deployed-gain-cost-guard'
METHODS = (*parent.METHODS, GAIN, GUARDED)


def prepare():
    source, controls, data = parent.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(source):
        raise ValueError('Use the published qualification-trained rankers')
    plan = {key: source[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed', 'proofCap',
                                          'ridge', 'features')}
    plan.update(protocol='witness-first-proof-gain-v1', parentPlanSha256=digest(source),
                parentReceiptSha256=REFERENCE_SHA256, sourceSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                methods=METHODS, primary=GUARDED,
                rule='Preserve paid search and the original nomination trigger. Rerank the same already-paid '
                'candidates using the same validation features. Dispatch at most one exact proof on its original panel.',
                fit='Fit realized post-proof holdout gain relative to the original deployment, and separately fit '
                'paid proof cost. Center labels and features within an episode and weight episodes equally. '
                'Training sees only the other benchmark family and may use its recorded holdout grades.',
                guard='Select the strongest predicted gain among candidates whose predicted proof cost is no '
                'higher than the original nominee estimate. Break ties in original nomination order.',
                gate='Require a positive paired lower endpoint against the original first proof for the primary '
                'ranker on every cohort, with realized cost no higher than the original seeded control.')
    return plan, reference, controls, data


def train(development, held_subjects):
    development_subjects = {episode.subject for episode in development}
    if development_subjects.intersection(held_subjects):
        raise ValueError('Development and evaluation subjects must be disjoint before accessing labels')
    original, _ = parent.train(development)
    gain_batches, cost_batches, labels = [], [], Counter()
    for episode in development:
        if len(episode.inputs) < 2:
            continue
        old = episode.prove(episode.nominee)
        reference = episode.score(old.prompt)
        base_passes = sum(reference)
        gain, cost = [], []
        for prompt, inputs in episode.inputs.items():
            result = episode.prove(prompt)
            delta = sum(episode.score(result.prompt)) - base_passes
            gain.append((inputs, delta / len(reference)))
            cost.append((inputs, (result.lookups - old.lookups) / CAP))
            labels.update(aboveOriginal=int(delta > 0), belowOriginal=int(delta < 0), candidates=1)
        gain_batches.append(gain)
        cost_batches.append(cost)
    gain, cost = parent.fit(gain_batches), parent.fit(cost_batches)
    weights = {'gain': dict(zip(parent.FEATURES, gain, strict=True)), 'cost': dict(zip(parent.FEATURES, cost, strict=True))}
    return (original, gain, cost), {'subjects': sorted(development_subjects), 'episodes': len(gain_batches),
                                    'labels': labels, 'weights': weights}


def guarded_choice(episode, gain, cost):
    def predicted_cost(inputs):
        return fsum(value * weight for value, weight in zip(inputs, cost, strict=True))

    maximum = predicted_cost(episode.inputs[episode.nominee])
    eligible = {prompt: inputs for prompt, inputs in episode.inputs.items() if predicted_cost(inputs) <= maximum}
    return parent.choose(eligible, gain)


def compare(plan, entry, weights, reference):
    groups, episodes, totals, traces = entry
    proof_fit, gain, cost = weights
    votes = {subject: {'cases': {arm: unit['cases'][FULL].copy() for arm in METHODS},
                       'decisionsPerCase': unit['decisionsPerCase']} for subject, unit in groups.items()}
    changes = {arm: Counter() for arm in METHODS[1:]}
    for episode in episodes:
        original = episode.prove(episode.nominee)
        routes = {parent.RATE: episode.rate_choice,
                  **{arm: parent.choose(episode.inputs, weights) for arm, weights in proof_fit.items()},
                  GAIN: parent.choose(episode.inputs, gain), GUARDED: guarded_choice(episode, gain, cost)}
        old = episode.score(original.prompt)
        for arm, nominee in routes.items():
            result = episode.prove(nominee)
            vector = votes[episode.subject]['cases'][arm]
            vector[:] = [value + new - before for value, new, before in zip(
                vector, episode.score(result.prompt), old, strict=True)]
            changes[arm].update(changedNominees=int(nominee != episode.nominee),
                                changedDeployments=int(result.prompt != original.prompt),
                                promotionDelta=int(result.status == 'promoted') - int(original.status == 'promoted'),
                                lookupDelta=result.lookups - original.lookups)
    for arm, counts in changes.items():
        totals[arm] = {'holdoutPasses': sum(sum(unit['cases'][arm]) for unit in votes.values()),
                       'paidLookups': totals[FULL]['paidLookups'] + counts['lookupDelta'],
                       'promotions': totals[FULL]['promotions'] + counts['promotionDelta'], **counts}
    paired = {}
    for baseline, challengers in ((FULL, METHODS[1:]), (parent.EFFICIENCY, (GAIN, GUARDED))):
        with patch.object(RANKING.paired_bands, 'BASELINE', baseline):
            paired[baseline] = {arm: RANKING.paired_bands.paired_ranges(votes, arm, plan)['subjectsAndCases']
                                for arm in challengers}
    if any(totals[arm] != reference['totals'][arm] for arm in (*parent.METHODS, retry.BASE)) or any(
            paired[FULL][arm] != reference['pairedVsOriginal'][arm] for arm in parent.METHODS[1:]):
        raise ValueError('The published qualification-trained controls changed')
    return {'totals': totals, 'paired': paired, 'panelTraceSha256': traces,
            'qualifies': totals[GUARDED]['paidLookups'] <= totals[retry.BASE]['paidLookups']
            and paired[FULL][GUARDED]['interval95PercentagePoints'][0] > 0}


def execute(plan, reference, controls, data):
    gathered = {phase: parent.collect(plan, data[phase], controls['cohorts'][phase]) for phase in RANKING.PHASES}
    bbh, mmlu_phases = RANKING.gap.paired.BBH, RANKING.gap.paired.replay.PHASES
    mmlu_episodes = [episode for phase in mmlu_phases for episode in gathered[phase][1]]
    mmlu_subjects = {subject for phase in mmlu_phases for subject in gathered[phase][0]}
    bb_weights, bb_summary = train(gathered[bbh][1], mmlu_subjects)
    mmlu_weights, mmlu_summary = train(mmlu_episodes, set(gathered[bbh][0]))
    cohorts = {phase: compare(plan, entry, mmlu_weights if phase == bbh else bb_weights, reference['cohorts'][phase])
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
