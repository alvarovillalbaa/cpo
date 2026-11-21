"""Test whether a paid case reply can improve the order of an exact rival proof."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_peer_case_order as peer
from cpo._contract import digest
from cpo.halving.qualification_budget import AdmissionDecision
from cpo.paired_qualification import QualificationObservation


PARENT = 'docs/witness-peer-case-order-results-v1.json'
PARENT_SHA256 = '913aedde31995b0a959da4211d0a2b1c01d1b53e611687e74442403abc08f47a'
CONDITIONAL, MARGINAL = 'conditional-case', 'marginal-only'
PRIOR_WEIGHT = 4


def prepare():
    parent, expected, baseline, data = peer.prepare()
    raw = (peer.ROOT / PARENT).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('Use the published matched case-order replay')
    plan = {'protocol': 'witness-same-case-order-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': PARENT_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'jointProofCap': parent['jointProofCap'], 'fallbackValidationCap': parent['fallbackValidationCap'],
            'pairedCaseDraws': parent['pairedCaseDraws'], 'resamplingSeed': parent['resamplingSeed'],
            'rule': 'Preserve the reserved first proof, selected rival, independent panels, and remaining cap. '
                    'Choose the next reply by expected progress toward exact promotion or rejection. Predict '
                    'each side from its paid search and proof grades. If the other side is already read, '
                    'shrink the corresponding empirical conditional rate toward its marginal rate.',
            'priorWeight': PRIOR_WEIGHT, 'comparison': 'Run the same scheduler with marginal rates alone and '
                    'the published expected-read order. Historical peer scores play no role.',
            'gate': parent['gate']}
    return plan, expected, baseline, data


def rates(side, counterpart, wins, reads, paired, conditional):
    marginal = Fraction(wins[side] + 1, reads[side] + 2)
    if not conditional or counterpart is None:
        return marginal
    fail, passed = ((False, counterpart), (True, counterpart)) if side == 0 else (
        (counterpart, False), (counterpart, True))
    support = paired[fail] + paired[passed]
    return (PRIOR_WEIGHT * marginal + paired[passed]) / (PRIOR_WEIGHT + support)


def prove(start, rival, base, reserve, evaluate, evidence, minimum, cap, *, conditional):
    """Use the scalar exact gate on two disjoint panels, with an optional base tie."""
    if not base or len(set(base) | set(reserve)) != len(base) + len(reserve):
        raise ValueError('Use distinct cases and a nonempty base panel')
    if type(minimum) is not int or minimum < 1 or type(cap) is not int or cap < 0:
        raise ValueError('Use a positive minimum gain and a nonnegative lookup cap')
    if start == rival:
        return AdmissionDecision('rejected', start, (), 0, 0, False)
    prompts = (start, rival)
    paid = [{case: passed for (key, case), passed in evidence.items() if key == prompt} for prompt in prompts]
    if (set(base) | set(reserve)) & (paid[0].keys() | paid[1].keys()):
        raise ValueError('The exact proof requires independent cases')
    wins, reads = [sum(grades.values()) for grades in paid], [len(grades) for grades in paid]
    paired = Counter((paid[0][case], paid[1][case]) for case in paid[0].keys() & paid[1].keys())
    observations, observed = [], {}
    for panel, extended, tie_allowed in ((base, False, bool(reserve)), (reserve, True, False)):
        low, high = -len(panel), len(panel)
        pending = dict.fromkeys((side, case) for case in panel for side in (0, 1))

        def settle(status, used):
            return AdmissionDecision(status, rival if status == 'promoted' else start,
                                     tuple(observations), low, high, used)

        while True:
            can_tie = tie_allowed and low <= 0 <= high
            if low >= minimum:
                return settle('promoted', extended)
            if high < minimum and not can_tie:
                return settle('rejected', extended)
            if can_tie and low == high == 0:
                break
            remaining = cap - len(observations)
            if not remaining:
                return settle('undecided', None if can_tie else extended)

            favorable = {}
            for side, case in pending:
                chance = rates(side, observed.get((1 - side, case)), wins, reads, paired, conditional)
                favorable[side, case] = chance if side else 1 - chance
            up = max(favorable, key=favorable.__getitem__)
            down = min(favorable, key=favorable.__getitem__)
            up_need = minimum - low
            down_need = high + 1 if can_tie else high - minimum + 1
            favor_rejection = remaining < up_need or down_need * favorable[up] <= up_need * (1 - favorable[down])
            side, case = down if favor_rejection else up
            del pending[side, case]
            passed = evaluate(prompts[side], case)
            if type(passed) is not bool:
                raise ValueError('Each qualification grade must be an exact boolean')
            observed[side, case] = passed
            observations.append(QualificationObservation(prompts[side], str(case), 0, passed))
            wins[side] += passed
            reads[side] += 1
            if (1 - side, case) in observed:
                paired[observed[0, case], observed[1, case]] += 1
            low += int(passed == bool(side))
            high -= int(passed != bool(side))
    raise RuntimeError('A complete scalar proof must settle the decision')


def execute(plan, published, baseline, data):
    def reordered_proof(start, rival, base, reserve, evaluate, evidence, minimum, cap, _history, marginal_only):
        return prove(start, rival, base, reserve, evaluate, evidence, minimum, cap, conditional=not marginal_only)

    with patch.multiple(peer, PEER=CONDITIONAL, ROTATED=MARGINAL, reordered_proof=reordered_proof):
        cohorts = {phase: peer.measure(plan, data[phase], published['cohorts'][phase], baseline['cohorts'][phase])
                   for phase in peer.RANKING.PHASES}
    for cohort in cohorts.values():
        cohort['pairedConditionalAgainst'] = cohort.pop('pairedPeerOrderAgainst')
        for arm in (CONDITIONAL, MARGINAL):
            del cohort['totals'][arm]['supportedReorders']
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'cohorts': cohorts,
            'qualifies': all(cohort['qualifies'] for cohort in cohorts.values())}


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
