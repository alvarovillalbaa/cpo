"""Give a second finalist a different already-paid repair witness."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import witness_first_proof_gain as parent
from cpo._contract import digest


ROOT, RANKING, retry, FULL, CAP = parent.ROOT, parent.RANKING, parent.retry, parent.FULL, parent.CAP
REPLAY = RANKING.gap.REPLAY
WITNESS = RANKING.gap.paired.replay.original
REFERENCE = 'docs/witness-first-proof-gain-results-v1.json'
REFERENCE_SHA256 = 'a9ca3fe6a6a1d52551e10addb569ad5fe1d8372a738de6ee10917bbe75e00289'
PREFIX, CACHE = 'split-finalists-prefix', 'split-finalists-paid-cache'
METHODS = (retry.BASE, FULL, PREFIX, CACHE)


def prepare():
    upstream, _, _, data = parent.prepare()
    _, native, _ = RANKING.gap.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(upstream):
        raise ValueError('Use the published paired witness and first-proof comparison')
    plan = {key: upstream[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed', 'proofCap')}
    plan.update(protocol='witness-split-finalists-v1', parentPlanSha256=digest(upstream),
                parentReceiptSha256=REFERENCE_SHA256, sourceSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                methods=METHODS, primary=CACHE,
                rule='Keep the first eligible finalist, incumbent scan, proposal order, and search cap. '
                'After the first finalist, use a different already-paid incumbent miss for the second slot. '
                'Use only this scan or also prior paid witness cycles. Check the same incumbent pass for both '
                'finalists and compare them on one spare case neither used as a witness when the budget fits.',
                gate='Require the primary arm to have a positive paired lower endpoint against the original '
                'expected-read proof and to fit realized seeded CPO spend on every cohort. Report the strongest '
                'published fixed GEPA point affordable at each arm’s realized lookup cost.')
    return plan, reference, native, data


def select(incumbent, layout, observe, plan, previous, activity):
    remaining = plan['evaluationLookupLimit']
    validation = list(layout['validation'])
    Random(layout['seed']).shuffle(validation)

    def read(prompt, case):
        nonlocal remaining
        remaining -= 1
        return observe(prompt, case)

    scanned, first_pass, first_miss = {}, None, None
    for case in validation:
        if not remaining:
            return incumbent
        passed = read(incumbent, case)
        scanned[case] = passed
        if passed and first_pass is None:
            first_pass = case
        if not passed and first_miss is None:
            first_miss = case
        if first_pass is not None and first_miss is not None:
            break
    if first_miss is None:
        return incumbent
    if any(case in previous and previous[case] != value for case, value in scanned.items()):
        raise ValueError('A shared paid incumbent grade changed between witness cycles')
    known = {**previous, **scanned}
    second_miss = next((case for case in validation if case != first_miss and known.get(case) is False), first_miss)
    activity.update(witnessCycles=1, alternateAvailable=int(second_miss != first_miss),
                    priorOnlyAlternate=int(second_miss != first_miss and second_miss not in scanned))
    required = 1 + int(first_pass is not None)
    finalists = []
    for prompt in layout['alternatives']:
        if remaining < required:
            break
        miss = second_miss if finalists else first_miss
        alternate = miss != first_miss
        activity['alternateProbes'] += int(alternate)
        if read(prompt, miss) and (first_pass is None or read(prompt, first_pass)):
            finalists.append((prompt, miss))
            if len(finalists) == 2:
                break
    if not finalists:
        return incumbent
    spare = next((case for case in validation if case != first_pass and all(case != miss for _, miss in finalists)), None)
    chosen = finalists[0]
    if len(finalists) == 2 and remaining >= 2 and spare is not None:
        chosen = max(finalists, key=lambda item: read(item[0], spare))
    activity.update(splitFinalistPairs=int(len(finalists) == 2 and finalists[1][1] != first_miss),
                    alternateNominees=int(chosen[1] != first_miss))
    return chosen[0]


def nominate(matrix, held, start, layouts, active, policy, cap, method, activity):
    known = {}

    def screen(incumbent, layout, observe, limits):
        initial = known.copy() if method == CACHE else {}

        def remember(prompt, case):
            passed = observe(prompt, case)
            if prompt == incumbent:
                known[case] = passed
            return passed

        return select(incumbent, layout, remember, limits, initial, activity)

    with patch.object(WITNESS, 'witness', screen):
        return RANKING.search_to_nomination(matrix, held, start, layouts, active, policy, cap)


def qualify(matrix, held, start, layouts, active, nomination):
    candidate = nomination.original
    if candidate is None:
        return retry.Decision(start, 0, 'no-nominee')
    slot = next(index for index, layout in enumerate(layouts) if candidate in layout['alternatives'])
    base = layouts[slot]['qualify']
    reserve = [case for layout in layouts[:slot] for case in layout['qualify']][:active['maximumExtensionRows']]
    forbidden = set(held) | {case for layout in layouts for role in ('train', 'validation') for case in layout[role]}
    if forbidden.intersection((*base, *reserve)):
        raise ValueError('The witness overlapped its independent proof or holdout')
    proof = retry.scalar_proof(start, candidate, base, reserve, lambda prompt, case: matrix[int(prompt)][case] == '1',
                               nomination.grades, active['minimumQualificationGain'], CAP)
    return retry.Decision(proof.prompt, len(proof.observations), proof.status)


def measure(plan, data, reference, native):
    inputs, panels, _, _, cap = data
    schedule, policy = inputs['schedule'], inputs['qualificationBank']
    active = {**schedule, 'evaluationLookupLimit': cap}
    fallback = plan['fallbackValidationCap']
    groups, traces = {}, {}
    totals = {method: Counter() for method in METHODS}
    activity = {method: Counter() for method in (PREFIX, CACHE)}
    for panel in panels:
        subject, model, matrix = (panel[name] for name in ('subject', 'model', 'correctness'))
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        identity = tuple(panel['caseIDs'][i] for i in held) if 'caseIDs' in panel else panel['caseOrderSha256']
        group = groups.setdefault(subject, {'identity': identity, 'decisionsPerCase': 0,
                                            'cases': {method: [0] * len(held) for method in METHODS}})
        if group['identity'] != identity:
            raise ValueError('Both models must share the same held-out cases')
        group['decisionsPerCase'] += len(schedule['seeds'])
        trace = []
        for seed in schedule['seeds']:
            start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
            original = RANKING.search_to_nomination(matrix, held, start, layouts, active, policy, fallback)
            control = retry.outcomes(matrix, held, start, layouts, active, policy, original)
            decisions = {method: (original, control[method]) for method in (retry.BASE, FULL)}
            trace.append((seed, tuple((item.prompt, item.lookups, item.status, item.retry)
                                      for _, item in decisions.values())))
            for method in (PREFIX, CACHE):
                nominee = nominate(matrix, held, start, layouts, active, policy, fallback, method, activity[method])
                result = qualify(matrix, held, start, layouts, active, nominee)
                decisions[method] = (nominee, result)
                activity[method].update(changedNominees=int(nominee.original != original.original),
                                        addedNominees=int(original.original is None and nominee.original is not None),
                                        lostNominees=int(original.original is not None and nominee.original is None),
                                        changedDeployments=int(result.prompt != control[FULL].prompt))
            for method, (nominee, decision) in decisions.items():
                scores = [int(matrix[int(decision.prompt)][case] == '1') for case in held]
                group['cases'][method] = [a + b for a, b in zip(group['cases'][method], scores, strict=True)]
                totals[method].update(holdoutPasses=sum(scores), paidLookups=nominee.paid_search + decision.lookups,
                                      proofLookups=decision.lookups, searchLookups=nominee.paid_search,
                                      promotions=int(decision.prompt != start))
        traces[f'{subject}/{model}'] = digest(trace)
    if traces != reference['panelTraceSha256'] or any(
            totals[arm][key] != reference['totals'][arm].get(key, 0)
            for arm in (retry.BASE, FULL) for key in ('holdoutPasses', 'paidLookups', 'proofLookups', 'promotions')):
        raise ValueError('The archived search and single-proof controls changed')
    with patch.object(RANKING.paired_bands, 'BASELINE', FULL):
        paired = {method: RANKING.paired_bands.paired_ranges(groups, method, plan)['subjectsAndCases'] for method in (PREFIX, CACHE)}
    best = {}
    for method, counts in totals.items():
        eligible = [(key, row) for key, row in native['totals'].items()
                    if key.startswith('gepa-') and row['paidLookups'] <= counts['paidLookups']]
        if eligible:
            key, score = min(eligible, key=lambda item: (-Fraction(item[1]['macroAccuracy']), item[1]['paidLookups'], item[0]))
            best[method] = {'setting': key, **score}
    return {'totals': totals, 'activity': activity, 'pairedVsOriginal': paired, 'panelTraceSha256': traces,
            'bestAffordableNativeGEPA': best,
            'qualifies': totals[CACHE]['paidLookups'] <= totals[retry.BASE]['paidLookups']
            and paired[CACHE]['interval95PercentagePoints'][0] > 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, reference, native, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    cohorts = {phase: measure(plan, data[phase], reference['cohorts'][phase], native['cohorts'][phase])
               for phase in RANKING.PHASES}
    report = {'plan': plan, 'planSha256': seal, 'newProviderRequests': 0, 'cohorts': cohorts,
              'qualifies': all(row['qualifies'] for row in cohorts.values())}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
