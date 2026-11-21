"""Test cheaper GEPA controls after the original transfer found none affordable."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import promptolution_witness_episode as original
from benchmarks.prompteval_transfer import PROBES
from cpo._contract import digest


PARENT = '0687f7b813559d93fa2531e3cf40223bcadb4534a3d2924769c6ec7ff9db5fbe'
SMALL = {}
for width in (2, 4, 6):
    for shape, rounds in (('sequential', 1), ('sequential', 2), ('batched', 2)):
        cap = width + rounds * (width + 2 * PROBES)
        SMALL[f'gepa-{shape}/validation-{width}/cap-{cap}/one-admission'] = {'validationRows': width, 'searchCap': cap}


def prepare():
    parent_file = original.ROOT / 'docs/promptolution-witness-episode-results-v1.json'
    raw = parent_file.read_bytes()
    parent = original.prepare()
    if sha256(raw).hexdigest() != PARENT or json.loads(raw)['planSha256'] != digest(parent):
        raise ValueError('The original recorded transfer must match its published seal')
    name = 'benchmarks/promptolution_witness_small_native.py'
    return {**parent, 'protocol': 'cpo-promptolution-witness-small-native-sensitivity-v1',
            'parentPlanSha256': digest(parent), 'parentReportSha256': PARENT,
            'controlSettings': {**parent['controlSettings'], **SMALL},
            'sourceSha256': {**parent['sourceSha256'], name: sha256((original.ROOT / name).read_bytes()).hexdigest()},
            'scope': 'Post-result sensitivity. Add narrower native full-round settings and preserve the original trials.'}


def execute(plan, corpus):
    knobs = {'CONTROLS': plan['controlSettings'], 'GEPA': (*original.GEPA, *SMALL), 'ARMS': (*original.ARMS, *SMALL)}
    with patch.multiple(original, **knobs):
        report = original.execute(plan, corpus)
    parent = json.loads((original.ROOT / 'docs/promptolution-witness-episode-results-v1.json').read_bytes())
    for task in parent['tasks']:
        for method in original.ARMS:
            if report['tasks'][task]['arms'][method] != parent['tasks'][task]['arms'][method]:
                raise ValueError('A wider native control or the original candidate changed its trace or counts')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan = prepare()
    seal = digest(plan)
    if args.corpus is None and args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.corpus is None or args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the pinned archive, sensitivity seal, and a fresh report path')
    report = execute(plan, original.load_corpus(args.corpus.read_bytes()))
    with args.out.open('x') as file:
        json.dump(report, file, sort_keys=True, indent=2)
        file.write('\n')


if __name__ == '__main__':
    main()
