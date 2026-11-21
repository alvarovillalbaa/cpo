"""Test cached lookahead with round-order reads on cold four-prompt boards."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_halving_lookahead as previous
from cpo._contract import digest
from cpo.halving.cached_lookahead import CachedLookaheadHalving


ROOT = previous.ROOT
REFERENCE = 'docs/witness-halving-lookahead-results-v1.json'
REFERENCE_SHA256 = 'ce6c02297c5d350a51d988e9fd21ece87c7775c89049db4e4d35744d3d27dea3'


def prepare():
    base, *inputs = previous.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    if sha256(raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError('Use the published lookahead receipt')
    receipt = json.loads(raw)
    if receipt['planSha256'] != digest(base):
        raise ValueError('The earlier replay differs from its published source')
    paths = (Path(__file__).resolve(), ROOT / 'cpo/halving/cached_lookahead.py')
    plan = {**base, 'protocol': 'witness-cached-halving-v1', 'previousPlanSha256': digest(base),
            'previousReceiptSha256': REFERENCE_SHA256,
            'sourceSha256': {**base['sourceSha256'], **{
                path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest() for path in paths}},
            'candidate': 'Use round order on cold four-prompt boards and previous lookahead elsewhere. '
                         'The route sees only the presence of exact cached grades in the surviving roster and prefix.'}
    return plan, receipt, inputs


def cold_boards():
    prompts, cases = tuple(map(str, range(13))), tuple(range(3))
    keys = tuple(product(prompts[:4], cases))
    selectors = {'rounds': previous.HalvingSearch, 'previousLookahead': previous.lookahead.LookaheadHalving,
                 'cachedLookahead': CachedLookaheadHalving}
    counts = Counter()
    for bits in product((False, True), repeat=len(keys)):
        grades = dict(zip(keys, bits, strict=True))
        decisions, observations = {}, {}
        for name, selector in selectors.items():
            search = selector(metric_limit=8)
            decisions[name] = search.select(prompts, cases, lambda prompt, case: grades[prompt, case])
            observations[name] = tuple(search.observations.items())
            counts[name] += search.evaluations
        if (None in decisions.values() or len(set(decisions.values())) != 1
                or observations['rounds'] != observations['cachedLookahead']):
            raise ValueError('Cold routing changed the winner or round-order reads')
    return {'boards': 1 << len(keys), 'reads': counts}


def execute(plan, reference, inputs):
    with patch.dict(previous.SELECTORS, {previous.WHOLE: CachedLookaheadHalving}):
        result = previous.execute(plan, *inputs)
    changes = {}
    for scope, report in result['scopes'].items():
        changes[scope] = {}
        for cap, points in report['points'].items():
            before = reference['scopes'][scope]['points'][str(cap)]
            if points[previous.ROUND] != before[previous.ROUND]:
                raise ValueError('The published round-order control changed at the same cap')
            after, earlier = (pair[previous.WHOLE] for pair in (points, before))
            changes[scope][cap] = {field: after[field] - earlier[field]
                                   for field in ('holdoutPasses', 'paidLookups', 'validationLookups', 'proofLookups')}
    return {**result, 'coldFourPromptBoards': cold_boards(), 'differenceVsPreviousLookahead': changes}


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
