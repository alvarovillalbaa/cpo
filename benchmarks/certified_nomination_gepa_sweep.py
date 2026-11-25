"""Compare packaged certified nomination with a denser native GEPA budget sweep."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import certified_nomination_api_parity as parity
from cpo._contract import digest


benchmark = parity.benchmark
math, depth = benchmark.math, benchmark.depth
archive, transfer = benchmark.archive, benchmark.transfer
gepa = transfer.donor.portable.prompteval_transfer
CANDIDATE = benchmark.MODES[0]
PARITY_SHA = '3f634014c9dd4edb9c4676ad0d3734493a22c5e7bfda7f05faf5fba90c0ddcaf'
_PLAY = archive.play


def sweep_settings(original):
    settings = {}
    for rows in range(1, 7):
        for batch in (1, 2):
            round_size = rows + 2 * batch
            full = rows + 2 * round_size
            for mode, caps in (('sequential', (rows, *range(rows + round_size, full + 1))),
                               ('batched', (rows, full))):
                for cap in caps:
                    suffix = '/minibatch-1' if batch == 1 else ''
                    name = f'gepa-{mode}/validation-{rows}/cap-{cap}{suffix}'
                    settings[name] = {'mode': mode, 'validationRows': rows, 'searchCap': cap, 'batch': batch}
    return {**settings, **{arm: {**spec, 'batch': 2} for arm, spec in original.items()}}


def prepare():
    parity_plan, base, inputs, expected = parity.prepare()
    receipt = transfer.locked('docs/certified-nomination-api-parity-v1.json', PARITY_SHA)
    if digest(parity_plan) != receipt['planSha256'] or digest(receipt['plan']) != receipt['planSha256']:
        raise ValueError('The package parity seal must reproduce')
    original = base['controlSettings']
    expanded = sweep_settings(original)
    paths = (Path(__file__), Path(gepa.__file__))
    fingerprints = {str(path.relative_to(transfer.donor.ROOT)): sha256(path.read_bytes()).hexdigest() for path in paths}
    plan = {
        **base, 'protocol': 'cpo-certified-nomination-gepa-sweep-v1', 'primary': CANDIDATE, 'arms': (CANDIDATE,),
        'promptolutionArms': (CANDIDATE,), 'packageParityReceiptSha256': PARITY_SHA,
        'originalControls': tuple(original), 'originalNativeMethods': base['nativeMethods'],
        'nativeMethods': tuple(name for name in expanded if name.startswith('gepa-')), 'controlSettings': expanded,
        'sourceSha256': {**base['sourceSha256'], **parity_plan['sourceSha256'], **fingerprints},
        'scope': ('Keep narrow rosters and the original case layouts. Sweep one to six validation cases and '
                  'one or two examples per reflection minibatch on both native GEPA schedules. Cover the integer '
                  'caps between the first funded round and the full two-challenger quote. Retain all original '
                  'GEPA and halving controls. Reselect affordable settings within each paired bootstrap draw.'),
    }
    return plan, inputs[0], expected


def play(plan, matrix, windows, seed, arm):
    batch = plan['controlSettings'].get(arm, {}).get('batch', 2)
    with patch.object(gepa, 'PROBES', batch):
        return _PLAY(plan, matrix, windows, seed, arm)


def distinct_controls(methods, panels, *, priced=False):
    by_signature = {}
    for arm in sorted(methods):
        signature = tuple((totals[arm]['paidLookups'], totals[arm].get(math.PRICE) if priced else None,
                           tuple(vectors[arm])) for totals, vectors in panels)
        by_signature.setdefault(signature, arm)
    return tuple(by_signature.values())


def reproduce(totals, reference, plan):
    for arm in (CANDIDATE, transfer.BASE, *plan['originalControls']):
        if totals[arm] != reference['totals'][arm]:
            raise ValueError(f'The original measured total for {arm} must reproduce')


def math_comparison(plan, corpus, reference):
    def compare(config, totals, vectors, peers):
        native = distinct_controls(config['nativeMethods'], [(totals, vectors)], priced=True)
        simple = tuple(arm for arm in peers if arm not in config['nativeMethods'])
        with patch.object(math, 'STALLED', CANDIDATE):
            return original({**config, 'nativeMethods': native}, totals, vectors, (*native, *simple))

    original = math.paired
    runner = partial(parity.packaged, True)
    with (patch.multiple(math, POLICIES=(CANDIDATE,), paired=compare),
          patch.object(archive, 'play', play), patch.dict(math.tail.RUNNERS, {CANDIDATE: runner})):
        measured = math.replay(plan, corpus)
    for subject, groups in measured.items():
        for group, row in groups.items():
            expected = reference[subject][group]
            if row['episodes'] != expected['episodes'] or row['layoutSha256'] != expected['layoutSha256']:
                raise ValueError('The original math episode layout must reproduce')
            reproduce(row['totals'], expected, plan)
            row['originalNativeGepa'] = {metric: values['nativeGepa']
                                         for metric, values in expected['matched'][CANDIDATE].items()}
    return measured


def promptolution_comparison(plan, reference, corpus):
    prompt_plan, *_ = archive.prepare()
    prior = transfer.locked('docs/validation-routed-promptolution-v1.json', depth.width.PROMPTOLUTION_SHA)
    config = {**prompt_plan, 'controlSettings': plan['controlSettings']}
    native = plan['nativeMethods']
    simplest = tuple(arm for arm in config['controlSettings'] if arm not in native)
    arms = (CANDIDATE, transfer.BASE, *config['controlSettings'])

    def compare(panels):
        return {
            'originalNativeGepa': transfer.compare(config, panels, CANDIDATE, plan['originalNativeMethods']),
            'expandedNativeGepa': transfer.compare(config, panels, CANDIDATE, distinct_controls(native, panels)),
            'expandedWithHalving': transfer.compare(config, panels, CANDIDATE,
                                                     distinct_controls((*native, *simplest, transfer.BASE), panels)),
        }

    outputs, combined = {}, []
    with patch.dict(archive.RUNNERS, {CANDIDATE: partial(parity.packaged, True)}):
        for task in config['tasks']:
            panel = corpus[task]
            held = sorted(Random(f"{config['holdoutSeed']}/{task}").sample(
                range(len(panel['caseIDs'])), transfer.donor.HOLDOUT))
            if digest([panel['caseIDs'][row] for row in held]) != prior['tasks'][task]['heldCaseSha256']:
                raise ValueError('Use the original Promptolution held-out questions')
            totals = {arm: Counter() for arm in arms}
            vectors = {arm: [0] * len(held) for arm in arms}
            for seed in config['seeds']:
                windows = transfer.layout(config, task, seed, held)
                matrix = panel['correctness']
                for arm in arms:
                    winner, cost, _ = play(config, matrix, windows, seed, arm)
                    grades = [matrix[winner][case] == '1' for case in held]
                    totals[arm].update(cost, holdoutPasses=sum(grades))
                    vectors[arm] = [a + b for a, b in zip(vectors[arm], grades, strict=True)]
            reproduce(totals, reference[task], plan)
            combined.append((totals, vectors))
            outputs[task] = {'episodes': len(config['seeds']), 'totals': totals,
                             'comparisons': compare([(totals, vectors)])}
    return {'tasks': outputs, 'pooledComparisons': compare(combined)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, math_corpus, expected = prepare()
    seal = digest(plan)
    if not (args.execute or args.out or args.corpus):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if (args.execute != seal or args.out is None or args.out.exists() or args.corpus is None
            or version('gepa') != plan['gepaVersion']):
        parser.error('Replay requires the pinned corpus, current seal, pinned GEPA and a fresh output path')
    corpus = transfer.donor.load_corpus(args.corpus.read_bytes())
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
              'math': math_comparison(plan, math_corpus, expected['math']),
              'promptolution': promptolution_comparison(plan, expected['promptolution']['tasks'], corpus)}
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
