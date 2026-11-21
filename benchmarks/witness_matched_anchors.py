"""Replace a rotating repair witness with a four-case exact validation race."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import prompteval_first_proof_budget as discovery, witness_split_finalists as previous
from cpo import Observation, Row
from cpo._contract import digest
from cpo.pool import select_pool


ROOT, RANKING, retry = previous.ROOT, previous.RANKING, previous.retry
REFERENCE = 'docs/witness-split-finalists-results-v1.json'
REFERENCE_SHA256 = 'c75e3c15ff23f39e9330ef44224be01a359d5e9f81c51447e7e8e49da11204a4'
FIRST, BEST = 'four-anchor-first', 'four-anchor-best'
METHODS = (retry.BASE, previous.FULL, FIRST, BEST)
WIDTH = 4


def prepare():
    upstream, controls, native, data = previous.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(upstream):
        raise ValueError('Use the published rotating-screen comparison')
    sources = (Path(__file__).resolve(), Path(discovery.__file__).resolve(), ROOT / 'cpo/pool.py', ROOT / 'cpo/challenger.py')
    plan = {key: upstream[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed', 'proofCap', 'gate')}
    plan.update(protocol='witness-matched-anchors-v1', parentPlanSha256=digest(upstream),
                parentReceiptSha256=REFERENCE_SHA256,
                sourceSha256={path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest() for path in sources},
                methods=METHODS, anchors=WIDTH, primary=BEST,
                rule='Replace the rotating witness stage with an exact race on the first four seeded validation '
                'anchors. Use the original ordered pool and search cap. Nominate the first provable strict gain '
                'or the highest completed strict gain. Keep the fallback, one-admission limit, independent proof, '
                'and paired holdout fixed.')
    return plan, reference, controls, native, data


def select(incumbent, layout, observe, limits, method, activity):
    order = list(layout['validation'])
    Random(layout['seed']).shuffle(order)
    anchors = order[:WIDTH]
    if len(set(anchors)) != WIDTH:
        raise ValueError('The matched race needs four distinct scheduled anchors')
    cap = limits['evaluationLookupLimit']
    if cap < WIDTH:
        return incumbent

    def read(prompt, case):
        activity['anchorLookups'] += 1
        return observe(prompt, case)

    if method == FIRST:
        selected = discovery.first_challenger(incumbent, {**layout, 'validation': anchors}, read, limits,
                                               rank_opening=False)
    else:
        rows = [Row(str(case), 'task') for case in anchors]
        receipt = select_pool((incumbent, *layout['alternatives']), rows,
                              lambda prompt, row: Observation(read(prompt, int(row.id)), {}), metric_limit=cap)
        selected = receipt.prompt
    activity.update(anchorCycles=1, anchorNominees=int(selected != incumbent))
    return selected


def nominate(matrix, held, start, layouts, active, policy, cap, method, activity):
    def race(incumbent, layout, observe, limits):
        return select(incumbent, layout, observe, limits, method, activity)

    with patch.object(previous.WITNESS, 'witness', race):
        return RANKING.search_to_nomination(matrix, held, start, layouts, active, policy, cap)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, reference, controls, native, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    with patch.multiple(previous, PREFIX=FIRST, CACHE=BEST, METHODS=METHODS, nominate=nominate):
        cohorts = {phase: previous.measure(plan, data[phase], controls['cohorts'][phase], native['cohorts'][phase])
                   for phase in RANKING.PHASES}
    for phase, cohort in cohorts.items():
        if cohort['panelTraceSha256'] != reference['cohorts'][phase]['panelTraceSha256'] or any(
                cohort['totals'][method] != reference['cohorts'][phase]['totals'][method] for method in METHODS[:2]):
            raise ValueError('The original screen traces, outcomes, or paid lookup counts changed')
    report = {'plan': plan, 'planSha256': seal, 'newProviderRequests': 0, 'cohorts': cohorts,
              'qualifies': all(row['qualifies'] for row in cohorts.values())}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
