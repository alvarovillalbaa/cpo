"""Order a second proof using only earlier paid validation from the peer model."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_rival_order as prior
from cpo._contract import digest


ROOT, REPLAY, RANKING, retry, split = prior.ROOT, prior.REPLAY, prior.RANKING, prior.retry, prior.audit.split
PARENT = 'docs/witness-rival-order-results-v1.json'
PARENT_SHA256 = '1934837ead931011dba02956ab1470a4074f142d90282fae6c3c26c156fb1656'
CONTROL, PEER, ROTATED = split.FUTILITY, 'peer-order', 'rotated-peer-order'


def prepare():
    parent, baseline, _, data = prior.prepare()
    raw = (ROOT / PARENT).read_bytes()
    receipt = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_SHA256 or receipt['planSha256'] != digest(parent):
        raise ValueError('Use the published rival proof ordering comparison')
    plan = {'protocol': 'witness-peer-case-order-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': PARENT_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'jointProofCap': parent['jointProofCap'], 'fallbackValidationCap': parent['fallbackValidationCap'],
            'pairedCaseDraws': parent['pairedCaseDraws'], 'resamplingSeed': parent['resamplingSeed'],
            'rule': 'Advance both models through the frozen seeds together. After a seed, record only distinct '
                    'paid search grades from each model. On a second proof, use earlier grades from the other '
                    'model of the same subject. Read lower-pass-rate items first for the incumbent and '
                    'higher-pass-rate items first for the rival. Keep both proof panels and the cap fixed.',
            'control': 'Rotate the same peer scores by one position within each panel before ranking. This '
                       'preserves the prior values while removing their match to the original item.',
            'gate': 'Require positive paired lower endpoints against both controls and no greater cost than '
                    'the seeded single proof on every cohort.'}
    return plan, receipt, baseline, data


def record(history, seen, grades, held):
    if any(case in held for _, case in grades):
        raise ValueError('Peer ordering cannot learn from holdout items')
    for entry, passed in grades.items():
        if entry not in seen:
            seen.add(entry)
            history.setdefault(entry[1], Counter()).update(passes=passed, reads=1)


def orders(panel, history, rotate):
    counts = [history.get(case, Counter()) for case in panel]
    estimates = [Fraction(count['passes'] + 1, count['reads'] + 2) for count in counts]
    if rotate:
        estimates = estimates[-1:] + estimates[:-1]
    scored = tuple(zip(panel, estimates, strict=True))
    return tuple(tuple(case for case, _ in sorted(scored, key=lambda item: sign * item[1])) for sign in (1, -1))


def reordered_proof(start, rival, base, reserve, evaluate, evidence, minimum, cap, history, rotate):
    first, second = orders(base, history, rotate), orders(reserve, history, rotate)
    rows = {start: (*first[0], *second[0]), rival: (*first[1], *second[1])}
    return retry.scalar_proof(start, rival, list(range(len(base))), list(range(len(base), len(base) + len(reserve))),
                              lambda prompt, position: evaluate(prompt, rows[prompt][position]), evidence, minimum, cap)


def alternatives(matrix, start, layouts, active, nomination, observed, history):
    if not observed.retry:
        return {PEER: observed, ROTATED: observed}, False
    rival = retry.ranked_rival(layouts, nomination.original, nomination.grades)
    roster = {prompt: index for index, layout in enumerate(layouts) for prompt in layout['alternatives']}
    cycle = roster[nomination.original]
    size = active['maximumExtensionRows']
    retired = set(layouts[cycle]['qualify']) | set([case for layout in layouts[:cycle] for case in layout['qualify']][:size])
    index = retry.retry_panel(layouts, roster[rival], retired)
    base = layouts[index]['qualify']
    reserve = [case for layout in layouts[:index] for case in layout['qualify'] if case not in retired][:size]
    first = observed.lookups - observed.retry_lookups
    cap = split.CAP - first
    results = {}

    def grade(prompt, case):
        return matrix[int(prompt)][case] == '1'

    for name, rotate in ((PEER, False), (ROTATED, True)):
        proof = reordered_proof(start, rival, base, reserve, grade, nomination.grades,
                                active['minimumQualificationGain'], cap, history, rotate)
        paid = len(proof.observations)
        if paid > cap:
            raise ValueError('Case ordering exceeded the remaining physical allowance')
        results[name] = retry.Decision(proof.prompt, first + paid, proof.status, True, paid)
    changed = orders(base, history, False) != (tuple(base), tuple(base)) or (
        orders(reserve, history, False) != (tuple(reserve), tuple(reserve)))
    return results, changed


def measure(plan, data, reference, baseline):
    inputs, panels, _, _, cap = data
    schedule, policy = inputs['schedule'], inputs['qualificationBank']
    active = {**schedule, 'evaluationLookupLimit': cap}
    subjects, groups = {}, {}
    controls = {method: Counter() for method in split.METHODS}
    totals = {method: Counter() for method in (PEER, ROTATED)}
    for panel in panels:
        subjects.setdefault(panel['subject'], []).append(panel)

    for subject, pair in subjects.items():
        if len(pair) != 2 or pair[0]['model'] == pair[1]['model']:
            raise ValueError('Each subject requires two distinct paired models')
        held = REPLAY.transfer.holdout(subject, len(pair[0]['correctness'][0]))
        identities = [tuple(panel['caseIDs']) if 'caseIDs' in panel else panel['caseOrderSha256'] for panel in pair]
        if identities[0] != identities[1]:
            raise ValueError('Paired models must share the same ordered items')
        held_set = set(held)
        group = {'cases': {arm: [0] * len(held) for arm in (CONTROL, PEER, ROTATED)},
                 'decisionsPerCase': len(pair) * len(schedule['seeds'])}
        groups[subject] = group
        histories, seen, traces = ({}, {}), (set(), set()), ([], [])
        for seed in schedule['seeds']:
            nominations = []
            for i, panel in enumerate(pair):
                matrix = panel['correctness']
                start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
                nominee = RANKING.search_to_nomination(matrix, held, start, layouts, active, policy,
                                                       plan['fallbackValidationCap'])
                nominations.append(nominee)
                previous = split.outcomes(matrix, held, start, layouts, active, policy, nominee)
                traces[i].append((seed, tuple((x.prompt, x.lookups, x.status, x.retry) for x in previous.values())))
                for method, decision in previous.items():
                    controls[method].update(holdoutPasses=sum(matrix[int(decision.prompt)][j] == '1' for j in held),
                                            paidLookups=nominee.paid_search + decision.lookups)
                observed = previous[CONTROL]
                arms, changed = alternatives(matrix, start, layouts, active, nominee, observed, histories[1 - i])
                for method, decision in {CONTROL: observed, **arms}.items():
                    votes = [matrix[int(decision.prompt)][j] == '1' for j in held]
                    group['cases'][method] = [x + y for x, y in zip(group['cases'][method], votes, strict=True)]
                    if method != CONTROL:
                        totals[method].update(holdoutPasses=sum(votes), paidLookups=nominee.paid_search + decision.lookups,
                                              secondAttempts=int(observed.retry), supportedReorders=int(changed),
                                              changedDeployments=int(decision.prompt != observed.prompt),
                                              rivalPromotions=int(decision.retry and decision.prompt != start))
            for i, nomination in enumerate(nominations):
                record(histories[i], seen[i], nomination.grades, held_set)
        for panel, trace in zip(pair, traces, strict=True):
            key = f"{subject}/{panel['model']}"
            if digest(trace) != baseline['panelTraceSha256'][key]:
                raise ValueError(f'The original proof trace changed on {key}')
    if any(dict(sums) != {key: baseline['totals'][method][key] for key in sums} for method, sums in controls.items()):
        raise ValueError('The original score or cost changed')
    if any(reference['expectedReadControl'][key] != count for key, count in controls[CONTROL].items()):
        raise ValueError('The expected-read control no longer matches the scheduling replay')

    pairs = {}
    for comparator in (CONTROL, ROTATED):
        with patch.object(RANKING.paired_bands, 'BASELINE', comparator):
            pairs[comparator] = RANKING.paired_bands.paired_ranges(groups, PEER, plan)['subjectsAndCases']
    return {'totals': {**controls, **totals}, 'pairedPeerOrderAgainst': pairs,
            'qualifies': totals[PEER]['paidLookups'] <= controls[retry.BASE]['paidLookups'] and all(
                band['interval95PercentagePoints'][0] > 0 for band in pairs.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, published, baseline, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    cohorts = {phase: measure(plan, data[phase], published['cohorts'][phase], baseline['cohorts'][phase])
               for phase in RANKING.PHASES}
    report = {'plan': plan, 'planSha256': seal, 'cohorts': cohorts, 'newProviderRequests': 0,
              'qualifies': all(cohort['qualifies'] for cohort in cohorts.values())}
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
