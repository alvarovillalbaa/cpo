"""Measure which remaining rival certificates can benefit from read ordering."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import accumulate
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_rival_capacity as audit
from cpo import Row
from cpo._contract import digest
from cpo.halving.qualification_budget import qualify_with_budget_lookahead


ROOT, REPLAY, RANKING, retry = audit.ROOT, audit.REPLAY, audit.RANKING, audit.retry
PARENT = 'docs/witness-rival-capacity-results-v1.json'
PARENT_SHA256 = 'bc6951a6f5cf61b105244ec50f10a86d99574f2bc1136754c02f24f8b2ef4125'
CONTROL, CANDIDATE = 'expected-reads', 'promotion-first'


def prepare():
    parent, prior, data = audit.prepare()
    raw = (ROOT / PARENT).read_bytes()
    receipt = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_SHA256 or receipt['planSha256'] != digest(parent):
        raise ValueError('Use the published audit of paid rivals and remaining proof')
    plan = {'protocol': 'witness-rival-order-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': PARENT_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'fallbackValidationCap': parent['fallbackValidationCap'], 'jointProofCap': parent['jointProofCap'],
            'pairedCaseDraws': prior['plan']['pairedCaseDraws'], 'resamplingSeed': prior['plan']['resamplingSeed'],
            'intervention': 'Preserve the first proof, paid rival, and case order. On each observed second proof, '
                            'prioritize the modeled chance of certifying promotion within the remaining cap.',
            'bound': 'For improving paid rivals with complete certificates, calculate the least number of reads '
                     'with clairvoyant side interleaving and with arbitrary read order. Base ties require '
                     'reading both sides of all base rows before the tie panel can open.'}
    return plan, prior, receipt, data


def certificate_minima(start, candidate, base, reserve, grade, minimum, tie):
    rows = reserve if tie else base
    inc = list(accumulate((not grade(start, case) for case in rows), initial=0))
    new = list(accumulate((grade(candidate, case) for case in rows), initial=0))
    target = len(rows) + minimum
    if inc[-1] + new[-1] < target:
        raise ValueError('A complete promotion requires sufficient favorable grades')
    overhead = 2 * len(base) if tie else 0
    prefix = min(i + j for i, old in enumerate(inc) for j, passed in enumerate(new) if old + passed >= target)
    return overhead + prefix, overhead + target


def measure(plan, data, prior, reference):
    inputs, panels, _, _, _ = data
    seeds = inputs['schedule']['seeds']
    groups, identities, owners = {}, {}, {}
    for panel in panels:
        subject, matrix = panel['subject'], panel['correctness']
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        identity = tuple(panel['caseIDs'][i] for i in held) if 'caseIDs' in panel else panel['caseOrderSha256']
        if identities.setdefault(subject, (identity, held)) != (identity, held):
            raise ValueError('Holdout cases must align across models')
        owners[id(matrix)] = subject
        group = groups.setdefault(subject, {'cases': {arm: [0] * len(held) for arm in (CONTROL, CANDIDATE)},
                                            'decisionsPerCase': 0})
        group['decisionsPerCase'] += len(seeds)

    results, constraints = Counter(), Counter()
    assess, scalar = audit.assess, retry.scalar_proof

    def inspect(matrix, held, start, layouts, active, nomination, observed):
        remaining = plan['jointProofCap'] - (observed.lookups - observed.retry_lookups)
        ranked = retry.ranked_rival(layouts, nomination.original, nomination.grades)
        minima = {}
        second = None

        def price(incumbent, prompt, base, reserve, grade, evidence, minimum, limit):
            nonlocal second
            complete = scalar(incumbent, prompt, base, reserve, grade, evidence, minimum, limit)
            if complete.status == 'promoted':
                minima[prompt] = certificate_minima(incumbent, prompt, base, reserve, grade, minimum,
                                                    complete.used_reserve)
                if minima[prompt][0] > len(complete.observations):
                    raise ValueError('The certificate lower bound exceeds a witnessed proof')
            if prompt == ranked:
                counts = []
                for key in (incumbent, prompt):
                    passes = [passed for (candidate, _), passed in evidence.items() if candidate == key]
                    counts.append((sum(passes), len(passes)))
                second = qualify_with_budget_lookahead(
                    incumbent, prompt, [Row(str(case), 'task') for case in base],
                    lambda key, row, _: grade(key, int(row.id)),
                    reserve=[Row(str(case), 'task') for case in reserve], minimum_gain=minimum,
                    validation_counts=counts, evaluation_limit=remaining)
                reads = len(second.observations)
                if reads > remaining or (second.status == 'promoted' and
                                          (prompt not in minima or reads < minima[prompt][0])):
                    raise ValueError('Promotion-first must honor the same cost and exact certificate')
            return complete

        with patch.object(retry, 'scalar_proof', price):
            measured = assess(matrix, held, start, layouts, active, nomination, observed)
        reason, _, _, _, options = measured
        if reason == 'paid-improvement-exceeds-cap':
            limits = [minima[rival.prompt] for rival in options if rival.gain > 0 and rival.status == 'promoted']
            if any(fixed <= remaining for fixed, _ in limits):
                constraints['side-order-can-fit'] += 1
            elif any(any_order <= remaining for _, any_order in limits):
                constraints['case-order-needed'] += 1
            else:
                constraints['certificate-minimum-exceeds-cap'] += 1

        candidate_delta = groups[owners[id(matrix)]]['cases'][CANDIDATE]
        gain = [int(matrix[int(second.prompt)][case] == '1') - int(matrix[int(observed.prompt)][case] == '1')
                for case in held]
        candidate_delta[:] = [a + b for a, b in zip(candidate_delta, gain, strict=True)]
        results.update(secondAttempts=1, changedDeployments=int(second.prompt != observed.prompt),
                       newPromotions=int(second.prompt != start and observed.prompt == start),
                       lostPromotions=int(second.prompt == start and observed.prompt != start),
                       holdoutPassDelta=sum(gain), paidLookupDelta=len(second.observations) - observed.retry_lookups)
        return measured

    with patch.object(audit, 'assess', inspect):
        observed = audit.measure(plan, data, prior)
    if observed != reference or sum(constraints.values()) != observed['reasons']['paid-improvement-exceeds-cap']:
        raise ValueError('Published controls or the budget attribution failed to reproduce')
    with patch.object(RANKING.paired_bands, 'BASELINE', CONTROL):
        paired = RANKING.paired_bands.paired_ranges(groups, CANDIDATE, plan)['subjectsAndCases']
    return {'candidateComparison': results, 'outsideCapAttribution': constraints, 'paired': paired,
            'expectedReadControl': observed['controls'][audit.split.FUTILITY]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, prior, reference, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    report = {'plan': plan, 'planSha256': seal, 'newProviderRequests': 0, 'cohorts': {
        phase: measure(plan, data[phase], prior['cohorts'][phase], reference['cohorts'][phase])
        for phase in RANKING.PHASES}}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
