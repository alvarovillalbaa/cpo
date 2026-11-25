"""Verify that the packaged first-gain episode reproduces the sealed replays."""

import argparse
from collections import Counter
from dataclasses import asdict
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import certified_strict_gain as math_study
from benchmarks import certified_strict_gain_transfer as prompt_study
from cpo._contract import digest
from cpo.full_roster_precheck import first_gain


sweep = math_study.sweep
archive, transfer = sweep.archive, sweep.transfer
MATH_SHA = prompt_study.STRICT_SHA
PROMPT_SHA = '880b8d10670ddfb6e558d03fdf09075d27f5265bd0eb8933eb290ecf2971e335'
API_PATH = 'cpo/full_roster_precheck/first_gain.py'


def prepare():
    math_plan, math_corpus, _ = math_study.prepare()
    prompt_plan, _, prior_holdouts = prompt_study.prepare()
    math_receipt = transfer.locked('docs/certified-strict-gain-v1.json', MATH_SHA)
    prompt_receipt = transfer.locked('docs/certified-strict-gain-transfer-v1.json', PROMPT_SHA)
    for plan, receipt in ((math_plan, math_receipt), (prompt_plan, prompt_receipt)):
        if digest(plan) != receipt['planSha256'] or digest(receipt['plan']) != receipt['planSha256']:
            raise ValueError('The original strict-gain benchmarks must reproduce their seals')
    root = transfer.donor.ROOT
    path = Path(__file__)
    api = (root / API_PATH).read_bytes()
    if api != Path(first_gain.__file__).read_bytes():
        raise ValueError('The imported first-gain API differs from the fingerprinted source')
    plan = {
        'protocol': 'cpo-certified-first-gain-api-parity-v1', 'gepaVersion': math_plan['gepaVersion'],
        'sources': {API_PATH: sha256(api).hexdigest(),
                    str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest()},
        'mathBenchmark': {'planSha256': math_receipt['planSha256'], 'receiptSha256': MATH_SHA},
        'promptolutionBenchmark': {'planSha256': prompt_receipt['planSha256'], 'receiptSha256': PROMPT_SHA,
                                   'corpusSha256': transfer.donor.CORPUS_SHA},
        'scope': ('Compare every ordered callback, returned cycle result and archive grade trace. Check outcomes '
                  'and archived cost by arm, using the original math and Promptolution layouts.'),
    }
    return plan, (math_plan, math_corpus, math_receipt['math']), (prompt_plan, prompt_receipt['tasks'], prior_holdouts)


def packaged(cap, incumbent, _training, cycles, evaluate, *, probe, qualify):
    return first_gain.run_first_gain_episode(incumbent, cycles, evaluate, qualify=qualify, uniform_read_limit=cap)


def measure(runner, config, matrix, windows, seed, arm):
    results = []

    def record(*args, **kwargs):
        result = runner(*args, **kwargs)
        results.append(asdict(result))
        return result

    with patch.dict(archive.RUNNERS, {arm: record}):
        paid = archive.play(config, matrix, windows, seed, arm)
    result, = results
    return paid, result


def verify(config, matrix, layouts, expected, *, math=False, prices=None):
    caps = config['strictGainCaps']
    totals = {arm: Counter() for arm in caps}
    traces = {arm: sha256() for arm in caps}
    for start, windows, held, seed in layouts:
        with patch.object(transfer.donor, 'START', start):
            for arm, cap in caps.items():
                args = config, matrix, windows, seed, arm
                original = measure(partial(math_study.run, cap), *args)
                actual = measure(partial(packaged, cap), *args)
                if actual != original:
                    raise ValueError(f'The packaged callback sequence or returned result changed for {arm}/{seed}')
                (deploy, cost, (_, _, ledger)), _ = actual
                totals[arm].update(cost, holdoutPasses=sum(int(matrix[deploy][index]) for index in held))
                if math:
                    totals[arm]['promotions'] += deploy != start
                if prices is not None:
                    totals[arm][sweep.math.PRICE] += sum(prices[prompt][case] for (_, prompt, case), _ in ledger)
                traces[arm].update(bytes.fromhex(digest(actual)))
    if len(layouts) != expected['episodes'] or any(stats != expected['totals'][arm] for arm, stats in totals.items()):
        raise ValueError('The packaged outcomes and costs must reproduce the sealed aggregate points')
    return {'episodes': len(layouts), 'arms': {arm: {'totals': totals[arm], 'traceSha256': trace.hexdigest()}
                                               for arm, trace in traces.items()}}


def math_replay(config, corpus, expected):
    original = sweep.math.math
    outcomes = {}
    for subject, settings in config['datasets'].items():
        cells = original.math.load_cells(subject, corpus[subject]['record'])
        matrix = {prompt: ''.join(str(int(cell[0])) for cell in values) for prompt, values in cells.items()}
        prices = ({prompt: tuple(cell[1] for cell in values) for prompt, values in cells.items()}
                  if subject == 'arc' else None)
        groups = {}
        for group in config['incumbentGroups']:
            layouts = [(start, [(tuple(roster), tuple(train), tuple(val[:config['validationPerCycle']]),
                                 tuple(proof[:config['admissionPerCycle']]))], held, seed)
                       for start, roster, (train, val, proof, held), seed in original.trials(
                           cells, settings, group, config['rosterWidth'])]
            prior = expected[subject][group]
            if digest(layouts) != prior['layoutSha256']:
                raise ValueError('The original math episode layouts must reproduce')
            groups[group] = verify(config, matrix, layouts, prior, math=True, prices=prices)
        outcomes[subject] = groups
    return outcomes


def prompt_replay(config, expected, old_holdouts, corpus):
    results = {}
    for name in config['tasks']:
        panel = corpus[name]
        held = sorted(Random(f"{config['holdoutSeed']}/{name}").sample(
            range(len(panel['caseIDs'])), transfer.donor.HOLDOUT))
        prior = expected[name]
        if digest([panel['caseIDs'][index] for index in held]) != old_holdouts[name]['heldCaseSha256']:
            raise ValueError('The original Promptolution holdout must reproduce')
        layouts = [(transfer.donor.START, transfer.layout(config, name, seed, held), held, seed)
                   for seed in config['seeds']]
        if digest([(seed, windows) for _, windows, _, seed in layouts]) != prior['layoutSha256']:
            raise ValueError('The original Promptolution episode layouts must reproduce')
        results[name] = verify(config, panel['correctness'], layouts, prior)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, math, prompt = prepare()
    seal = digest(plan)
    if not (args.corpus or args.execute or args.out):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if (args.execute != seal or args.out is None or args.out.exists() or args.corpus is None
            or version('gepa') != plan['gepaVersion']):
        parser.error('Replay requires the pinned corpus, current seal, pinned GEPA and a fresh output path')
    corpus = transfer.donor.load_corpus(args.corpus.read_bytes())
    result = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
              'math': math_replay(*math), 'promptolution': prompt_replay(*prompt, corpus)}
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
