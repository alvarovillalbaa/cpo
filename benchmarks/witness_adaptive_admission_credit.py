"""Learn which optional proof route to fund from settled proofs in the same batch."""

import argparse
from collections import Counter, deque
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_shared_admission_credit as shared
from benchmarks.witness_shared_admission_credit import allocate as fixed_allocate
from cpo._contract import digest


ROOT, RANKING, FULL, CAP = shared.ROOT, shared.RANKING, shared.FULL, shared.CAP
REFERENCE = 'docs/witness-shared-admission-credit-results-v1.json'
REFERENCE_SHA256 = '86cf078f89311facad891e5e3ece7516c719baf79b7b4d18951238daf47828f3'
BALANCED, ADAPTIVE = 'alternating-routes', 'adaptive-route'
METHODS = (*shared.METHODS, BALANCED, ADAPTIVE)


def prepare():
    parent, unchanged, direct, funded, data = shared.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('Use the published shared proof queues and fixed budgets')
    plan = {**parent, 'protocol': 'witness-adaptive-admission-credit-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': METHODS, 'rule': 'Keep each route in episode order. Try each route if it is affordable. '
            'Then favor the route with the highest (promotions + 1) / (charged reads + 24), using only already '
            'settled proofs in the current arm. Break ties by fewer attempts and earlier episode. The '
            'alternating control always favors fewer attempts. Both skip unreservable offers and settle the '
            'same existing proof policy under the same credit.',
            'gate': 'Require a positive paired lower endpoint against the full single proof for the policy '
                    'selected by the other family. Also compare the adaptive queue with its alternating control.'}
    return plan, reference, unchanged, direct, funded, data


def allocate(candidates, method, limit, settle):
    if method not in (BALANCED, ADAPTIVE):
        return fixed_allocate(candidates, method, limit, settle)

    queues = {kind: deque() for kind in (shared.DIRECT, shared.RETRY)}
    for offer in candidates:
        if not 1 <= offer.reserve <= CAP:
            raise ValueError('Each proof needs a reservation within the original episode cap')
        queues[offer.kind].append(offer)

    attempts, promotions, spent = Counter(), Counter(), Counter()
    receipts, remaining = {}, limit
    while True:
        for queue in queues.values():
            while queue and queue[0].reserve > remaining:
                queue.popleft()
        available = [kind for kind, queue in queues.items() if queue]
        if not available:
            return receipts, remaining

        def order(kind):
            return attempts[kind], queues[kind][0].key

        if method == ADAPTIVE and all(attempts[kind] for kind in available):
            selected = min(available, key=lambda kind: (-Fraction(promotions[kind] + 1, spent[kind] + CAP), *order(kind)))
        else:
            selected = min(available, key=order)
        offer = queues[selected].popleft()
        remaining -= offer.reserve
        proof = settle(offer)
        if type(proof.paid) is not int or not 0 <= proof.paid <= offer.reserve:
            raise ValueError('The proof exceeded its reserved lookups')
        receipts[offer.key] = proof
        attempts[selected] += 1
        promotions[selected] += proof.promoted
        spent[selected] += proof.paid
        remaining += offer.reserve - proof.paid


def execute(plan, reference, unchanged, direct, funded, data):
    with patch.multiple(shared, METHODS=METHODS, allocate=allocate):
        replayed = {phase: shared.measure(plan, phase, data[phase], unchanged['cohorts'][phase], direct['cohorts'][phase],
                                          funded['cohorts'][phase]) for phase in RANKING.PHASES}
        bbh = RANKING.gap.paired.BBH
        fit = {bbh: shared.select([replayed[bbh][1]]), 'mmlu': shared.select(
            [replayed[phase][1] for phase in RANKING.gap.paired.replay.PHASES])}
    cohorts = {}
    for phase, (votes, report) in replayed.items():
        parent = reference['cohorts'][phase]
        for key in ('availableCredit', 'offers', 'panelTraceSha256'):
            if report[key] != parent[key]:
                raise ValueError(f'The frozen queue changed in {phase}/{key}')
        if any(report['totals'][arm] != row for arm, row in parent['totals'].items()):
            raise ValueError('The established fixed queues changed their costs or outcomes')
        selected = fit['mmlu' if phase == bbh else bbh]
        comparisons = {}
        for method, control in dict.fromkeys(((selected, FULL), (ADAPTIVE, BALANCED), (ADAPTIVE, FULL))):
            with patch.object(RANKING.paired_bands, 'BASELINE', control):
                comparisons[f'{method} vs {control}'] = RANKING.paired_bands.paired_ranges(votes, method, plan)['subjectsAndCases']
        report.update(selectedOutsideFamily=selected, paired=comparisons,
                      qualifies=comparisons[f'{selected} vs {FULL}']['interval95PercentagePoints'][0] > 0)
        cohorts[phase] = report
    return {'plan': plan, 'planSha256': digest(plan), 'training': fit, 'cohorts': cohorts,
            'newProviderRequests': 0, 'qualifies': all(group['qualifies'] for group in cohorts.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    report = execute(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
