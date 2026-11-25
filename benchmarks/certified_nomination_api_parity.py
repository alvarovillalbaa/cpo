"""Verify the packaged nominee certificate against the published archive replay."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import validation_routed_nominee_certificate as benchmark
from cpo._contract import digest
from cpo.full_roster_precheck.certified_nomination import run_certified_nomination_episode


transfer = benchmark.transfer
REFERENCE = '2da53d9a75c0a23ff92678e51241b99fc613a248218ae155afa64da2bbf21941'


def packaged(use_validation_rates, incumbent, _training, cycles, evaluate, *, probe, qualify):
    return run_certified_nomination_episode(incumbent, cycles, evaluate, qualify=qualify,
                                            use_validation_rates=use_validation_rates)


def prepare():
    base, *inputs = benchmark.prepare()
    prior = transfer.locked('docs/validation-routed-nominee-certificate-v1.json', REFERENCE)
    seal = digest(base)
    if seal != prior['planSha256'] or digest(prior['plan']) != seal:
        raise ValueError('The benchmark implementation must reproduce its sealed plan')
    root = transfer.donor.ROOT
    paths = ('benchmarks/certified_nomination_api_parity.py', 'cpo/full_roster_precheck/certified_nomination.py')
    plan = {'protocol': 'cpo-certified-nomination-api-parity-v1', 'benchmarkPlanSha256': seal,
            'benchmarkReceiptSha256': REFERENCE, 'gepaVersion': base['gepaVersion'],
            'sourceSha256': {name: sha256((root / name).read_bytes()).hexdigest() for name in paths},
            'scope': ('Compare the two packaged policies with their benchmark implementations on every '
                      'archived episode. Require identical paid replies, cycle transitions, outcomes, costs, '
                      'and matched controls under the published benchmark.')}
    return plan, base, inputs, prior['results']


def replay(base, inputs, expected, corpus):
    play = benchmark.archive.play
    runners = {key: partial(packaged, index == 0) for index, key in enumerate(benchmark.MODES)}
    counts = Counter()
    traces = {name: sha256() for name in runners}

    def verify(*args):
        original = play(*args)
        method = args[-1]
        if method not in runners:
            return original
        with patch.dict(benchmark.archive.RUNNERS, {method: runners[method]}):
            public = play(*args)
        if public != original:
            raise ValueError('The package must reproduce the complete benchmark episode receipt')
        counts[method] += 1
        traces[method].update(bytes.fromhex(digest(public)))
        return public

    with patch.object(benchmark.archive, 'play', verify):
        reproduced = benchmark.replay(base, *inputs, corpus)
    episodes = sum(row['episodes'] for groups in expected['math'].values() for row in groups.values())
    episodes += sum(row['episodes'] for row in expected['promptolution']['tasks'].values())
    if counts != dict.fromkeys(runners, episodes) or digest(reproduced) != digest(expected):
        raise ValueError('The packaged policies must reproduce the entire benchmark')
    return {method: {'episodes': counts[method], 'traceSha256': trace.hexdigest()}
            for method, trace in traces.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if not (args.execute or args.out or args.corpus):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if (args.execute != seal or args.out is None or args.out.exists() or args.corpus is None
            or version('gepa') != plan['gepaVersion']):
        parser.error('Replay requires the pinned corpus, current seal, pinned GEPA and a fresh output path')
    corpus = transfer.donor.load_corpus(args.corpus.read_bytes())
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'verified': replay(*inputs, corpus)}
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
