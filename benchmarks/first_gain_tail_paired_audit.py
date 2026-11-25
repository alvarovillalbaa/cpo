"""Resample archived questions when comparing first-gain validation extensions."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from operator import mul
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import first_gain_validation_tail as tail
from cpo._contract import digest


earlier = tail.previous.earlier
sweep, transfer = earlier.sweep, earlier.transfer
FIXED = 'first-gain/validation-3'
TERMINAL = tail.previous.PRECHECK
CANDIDATES = (tail.PRIMARY, 'first-gain/stalled-tail-9')
REFERENCE = '28dee539034a95a4a59f38f6d5d2fed3132c2062983519de55eb4ce0a8db1a19'


def interval(values):
    ordered = sorted(values)
    last = len(ordered) - 1
    return [ordered[last // 40], ordered[last * 39 // 40]]


def paired(vectors, comparisons, *, draws, seed):
    """Draw each question once across all its episode appearances and all methods."""
    width = len(next(iter(vectors.values())))
    points = {name: sum(grades) for name, grades in vectors.items()}
    linked = {key: (arm, tuple(peers)) for key, (arm, peers) in comparisons.items()}
    samples = {key: [] for key in linked}
    rng = Random(seed)
    # Equal question vectors yield equal scores in every draw, including ties.
    distinct = {grades for grades in vectors.values()}
    for _ in range(draws):
        draw = Counter(rng.choices(range(width), k=width))
        weights = tuple(draw[index] for index in range(width))
        scores = {grades: sum(map(mul, grades, weights)) for grades in distinct}
        for key, (arm, peers) in linked.items():
            samples[key].append(scores[vectors[arm]] - max(scores[vectors[peer]] for peer in peers))
    return {key: {'passDelta': points[arm] - max(points[peer] for peer in peers),
                  'caseResampled95': interval(samples[key]), 'comparedSettings': len(peers)}
            for key, (arm, peers) in linked.items()}


def affordable(published, reference, metrics):
    budget = {metric: max(reference['arms'][arm]['totals'][metric] for arm in CANDIDATES)
              for metric in metrics}
    return tuple(arm for arm, stats in published.items()
                 if (arm == transfer.BASE or arm.startswith(('gepa-', 'halving/')))
                 and any(stats[metric] <= ceiling for metric, ceiling in budget.items()))


def comparisons(totals, clusters, reference, metrics, draws, seed):
    recipes = {}
    for candidate in CANDIDATES:
        recipes[candidate, 'fixedThree'] = candidate, (FIXED,)
        recipes[candidate, 'terminal'] = candidate, (TERMINAL,)
        for metric in metrics:
            for name, prefix in (('nativeGepa', 'gepa-'), ('halving', 'halving/')):
                peers = tuple(arm for arm, stats in totals.items()
                              if (arm == transfer.BASE or arm.startswith(prefix))
                              and stats[metric] <= totals[candidate][metric])
                strongest = earlier.best_affordable(totals, totals[candidate][metric], metric, peers)
                expected = reference['arms'][candidate]['matchedPoints'][metric][name]
                if any(strongest[key] != expected[key] for key in ('arm', 'holdoutPasses', metric)):
                    raise ValueError('The previously observed budget match must reproduce')
                recipes[candidate, f'{metric}/{name}'] = candidate, peers
    paired_results = paired(clusters, recipes, draws=draws, seed=seed)
    return {arm: {axis: result for (candidate, axis), result in paired_results.items() if candidate == arm}
            for arm in CANDIDATES}


def measure(plan, references, config, layouts, matrix, prices, expected, controls, *, math):
    reference = references[expected['layoutSha256']]
    metrics = ('paidLookups', sweep.math.PRICE) if prices is not None else ('paidLookups',)
    published = controls['totals']
    controls = affordable(published, reference, metrics)
    runners = {FIXED: partial(tail.previous.run, 3), TERMINAL: partial(tail.previous.prior.run, TERMINAL),
               **{arm: partial(tail.run, arm) for arm in CANDIDATES}}
    arms = (*runners, *controls)
    config = {**config, 'controlSettings': plan['controlSettings']}
    cases = sorted({row for _, _, held, _ in layouts for row in held})
    slots = {row: index for index, row in enumerate(cases)}
    vectors = {arm: [0] * len(cases) for arm in arms}
    totals = {arm: Counter() for arm in arms}

    for start, windows, held, seed in layouts:
        with patch.object(transfer.donor, 'START', start):
            for arm in arms:
                if arm in runners:
                    winner, cost, trace = earlier.parity.measure(runners[arm], config, matrix, windows, seed, arm)[0]
                    earlier.parity.prompt_study.verify_deployment(matrix, windows, trace[1])
                else:
                    winner, cost, trace = sweep.play(config, matrix, windows, seed, arm)
                grades = [int(matrix[winner][row]) for row in held]
                totals[arm].update(cost, holdoutPasses=sum(grades))
                if prices is not None:
                    totals[arm][metrics[1]] += sum(prices[prompt][row] for (_, prompt, row), _ in trace[2])
                for row, grade in zip(held, grades, strict=True):
                    vectors[arm][slots[row]] += grade

    if len(layouts) != reference['episodes']:
        raise ValueError('The episode count must reproduce')
    for arm, stats in totals.items():
        original = reference['arms'][arm]['totals'] if arm in runners else published[arm]
        if any(stats[key] != original[key] for key in ('holdoutPasses', *metrics)):
            raise ValueError(f'The published score and cost must reproduce for {arm}')
    clusters = {arm: tuple(values) for arm, values in vectors.items()}
    return {'episodes': len(layouts), 'questions': len(cases), 'controlSettingsReplayed': len(controls),
            'caseVectorsSha256': digest(clusters), 'caseVectors': clusters,
            'comparisons': comparisons(totals, clusters, reference, metrics, plan['draws'], plan['seed'])}


def prepare():
    parent, math, prompt, controls, *_ = tail.prepare()
    reference = transfer.locked('docs/first-gain-validation-tail-v1.json', REFERENCE)
    if digest(parent) != reference['planSha256'] or digest(reference['plan']) != reference['planSha256']:
        raise ValueError('The published validation-tail study must reproduce')
    native = earlier.transfer.locked('docs/certified-nomination-gepa-sweep-v1.json', earlier.parity.math_study.SWEEP_SHA)
    settings = native['plan']
    fingerprints = {str(path.relative_to(transfer.donor.ROOT)): sha256(path.read_bytes()).hexdigest()
                    for path in (Path(__file__), Path(sweep.__file__))}
    references = {math[2][subject][group]['layoutSha256']: result
                  for subject, groups in reference['math'].items() for group, result in groups.items()}
    references.update({prompt[1][task]['layoutSha256']: result for task, result in reference['promptolution'].items()})
    plan = {
        'protocol': 'cpo-first-gain-tail-paired-audit-v1', 'primary': tail.PRIMARY, 'candidates': CANDIDATES,
        'fixedCpoControls': (FIXED, TERMINAL), 'draws': settings['bootstrapDraws'], 'seed': settings['bootstrapSeed'],
        'controlSettings': settings['controlSettings'], 'gepaVersion': settings['gepaVersion'],
        'parentReceiptSha256': REFERENCE, 'parentPlanSha256': reference['planSha256'],
        'promptolutionCorpusSha256': parent['promptolutionCorpusSha256'],
        'sourceSha256': {**parent['sourceSha256'], **fingerprints},
        'scope': ('Rerun both widening policies, two fixed CPO comparators, and all published GEPA or halving '
                  'settings affordable for either candidate at realized lookup cost or ARC historical price. '
                  'Keep costs fixed. Resample whole paired held-out question vectors within each group and '
                  'reselect the strongest affordable native and halving score in each draw.'),
    }
    return plan, math, prompt, controls, references


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute', metavar='PLAN_SHA256')
    cli.add_argument('--corpus', type=Path)
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, math, prompt, controls, references = prepare()
    seal = digest(plan)
    if not (args.execute or args.out or args.corpus):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if (args.execute != seal or args.out is None or args.out.exists() or args.corpus is None
            or version('gepa') != plan['gepaVersion']):
        cli.error('Use the current seal, pinned corpus and GEPA, and a fresh output path')
    corpus = transfer.donor.load_corpus(args.corpus.read_bytes())
    with patch.object(earlier, 'verify_group', partial(measure, plan, references)):
        result = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
                  'math': earlier.math_replay(math, controls['math']),
                  'promptolution': earlier.prompt_replay(prompt, controls['promptolution']['tasks'], corpus)}
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
