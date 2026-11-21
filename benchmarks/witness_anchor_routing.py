"""Choose a bounded four-case race from the two paid opening anchor replies."""

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import witness_anchor_bounds as parent
from cpo._contract import digest


ROOT, RANKING, retry, FULL, BOUNDS = parent.ROOT, parent.RANKING, parent.retry, parent.FULL, parent.BOUNDS
REPLAY = RANKING.gap.REPLAY
REFERENCE = 'docs/witness-anchor-bounds-results-v1.json'
REFERENCE_SHA256 = 'b730d777e9dd4f7e35869155948b473c2e78f0c3688d4a6bfdbb4f16741fb97e'
MASKS = {f'opening-mask-{mask}': mask for mask in range(1, 7)}
BLIND = {f'hash-rate-{rate}-of-8': rate for rate in range(1, 8)}
PARTIAL = {f'{method}-rate-{rate}-of-8': (mask, rate) for method, mask in MASKS.items() for rate in range(1, 8)}
WHOLE_MENU, BLIND_MENU = (FULL, *MASKS, BOUNDS), (FULL, *BLIND, BOUNDS)
PROBE_MENU = (*WHOLE_MENU, *PARTIAL)
STATIC = (retry.BASE, *PROBE_MENU, *BLIND)
SUBJECT, FAMILY, HASH = 'held-out-subject-opening', 'held-out-family-opening', 'held-out-subject-hash'
WHOLE = 'held-out-subject-whole-opening'


def prepare():
    source, _, native, data = parent.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(source):
        raise ValueError('Use the published score-bound race as the routing control')
    plan = {key: source[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed')}
    plan.update(protocol='witness-anchor-routing-v1', parentPlanSha256=digest(source),
                parentReceiptSha256=REFERENCE_SHA256, sourceSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                primary=SUBJECT, staticMethods=STATIC, openingMasks=MASKS, hashRates=BLIND, partialMasks=PARTIAL,
                rule='Choose one search for the entire episode after the first two seeded incumbent reads. '
                'Both searches must already pay for those same reads. The opening mask specifies how many '
                'incumbent passes permit the full four-anchor race. Candidate rules may activate fixed '
                'eighths inside those strata. A hash-rate control uses the same bins without reading scores.',
                fit='Maximize macro holdout accuracy on training subjects within their seeded lookup total. '
                'Break ties by lower cost and declared order. Hold out both model panels and every seed of '
                'each subject. Also fit one rule on the other full benchmark family.',
                gate='Require a positive paired lower endpoint for the learned opening rule against original '
                'CPO and the trained blind rule, with realized lookup cost within seeded CPO on every cohort.')
    return plan, reference, native, data


def opening(start, layout, original, wide):
    anchors = list(layout['validation'])
    Random(layout['seed']).shuffle(anchors)
    keys = [(start, case) for case in anchors[:2]]
    if len(keys) != 2 or any(key not in original or key not in wide or original[key] != wide[key] for key in keys):
        raise ValueError('Both searches must already pay for the same two opening grades')
    return sum(original[key] for key in keys)


def open_route(mask, rate, passes, bucket):
    return BOUNDS if mask & (1 << passes) and bucket < rate else FULL


def measure(plan, data, reference):
    inputs, panels, _, _, cap = data
    schedule, policy = inputs['schedule'], inputs['qualificationBank']
    active = {**schedule, 'evaluationLookupLimit': cap}
    groups, traces, strata = {}, {}, defaultdict(Counter)
    checks = {arm: Counter() for arm in (retry.BASE, FULL, BOUNDS)}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        identity = tuple(panel['caseIDs'][case] for case in held) if 'caseIDs' in panel else panel['caseOrderSha256']
        group = groups.setdefault(subject, {'identity': identity, 'decisionsPerCase': 0, 'costs': Counter(),
                                            'cases': {method: [0] * len(held) for method in STATIC},
                                            'wideEpisodes': Counter()})
        if group['identity'] != identity:
            raise ValueError('Both model panels must use the same held-out cases')
        group['decisionsPerCase'] += len(schedule['seeds'])
        trace = []
        for seed in schedule['seeds']:
            start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
            first = RANKING.search_to_nomination(matrix, held, start, layouts, active, policy, plan['fallbackValidationCap'])
            result = retry.outcomes(matrix, held, start, layouts, active, policy, first)
            wide = parent.nominate(matrix, held, start, layouts, active, policy, plan['fallbackValidationCap'], BOUNDS, Counter())
            final = parent.reference_runner.qualify(matrix, held, start, layouts, active, wide)
            passes = opening(start, layouts[0], first.grades, wide.grades)
            bucket = int(digest((subject, model, seed)), 16) % 8
            controls = {retry.BASE: (first, result[retry.BASE]), FULL: (first, result[FULL]), BOUNDS: (wide, final)}
            payouts = {arm: (tuple(int(matrix[int(decision.prompt)][case] == '1') for case in held),
                             nominee.paid_search + decision.lookups) for arm, (nominee, decision) in controls.items()}
            for arm, (_, decision) in controls.items():
                scores, paid = payouts[arm]
                checks[arm].update(holdoutPasses=sum(scores), paidLookups=paid, proofLookups=decision.lookups,
                                   promotions=int(decision.prompt != start))
            trace.append((seed, tuple((item.prompt, item.lookups, item.status, item.retry)
                                      for item in (result[retry.BASE], result[FULL]))))
            bits = {method: open_route(mask, 8, passes, bucket) for method, mask in MASKS.items()}
            rates = {method: open_route(7, rate, passes, bucket) for method, rate in BLIND.items()}
            partial = {method: open_route(mask, rate, passes, bucket) for method, (mask, rate) in PARTIAL.items()}
            for method, scored in {**{arm: arm for arm in controls}, **bits, **rates, **partial}.items():
                scores, paid = payouts[scored]
                group['cases'][method] = [value + gain for value, gain in zip(group['cases'][method], scores, strict=True)]
                group['costs'][method] += paid
                group['wideEpisodes'][method] += int(scored == BOUNDS)
            original_votes, original_cost = payouts[FULL]
            wide_votes, wide_cost = payouts[BOUNDS]
            strata[passes].update(episodes=1, extraPasses=sum(wide_votes) - sum(original_votes),
                                  extraLookups=wide_cost - original_cost)
        traces[f'{subject}/{model}'] = digest(trace)
    if traces != reference['panelTraceSha256'] or any(
            checks[arm][key] != reference['totals'][arm].get(key, 0) for arm in checks
            for key in ('holdoutPasses', 'paidLookups', 'proofLookups', 'promotions')):
        raise ValueError('The published search, score bounds, or first-proof control changed')
    return groups, traces, strata


def totals(groups, method):
    passes = [sum(group['cases'][method]) for group in groups]
    rates = [Fraction(value, len(group['cases'][method]) * group['decisionsPerCase'])
             for value, group in zip(passes, groups, strict=True)]
    return {'holdoutPasses': sum(passes), 'paidLookups': sum(group['costs'][method] for group in groups),
            'wideEpisodes': sum(group['wideEpisodes'][method] for group in groups),
            'macroAccuracy': str(sum(rates) / len(groups))}


def fit(groups, menu):
    ceiling = sum(group['costs'][retry.BASE] for group in groups)
    options = [(method, totals(groups, method)) for method in menu]
    method, _ = min((row for row in options if row[1]['paidLookups'] <= ceiling),
                    key=lambda row: (-Fraction(row[1]['macroAccuracy']), row[1]['paidLookups'], menu.index(row[0])))
    return method


def held_out(groups, subject, menu):
    return fit([group for name, group in groups.items() if name != subject], menu)


def compare(plan, groups, traces, strata, own, other, native):
    family_rule = fit(list(other.values()), PROBE_MENU)
    fixed = {method: totals(list(groups.values()), method) for method in STATIC}
    selected = {}
    for subject, group in groups.items():
        routes = {SUBJECT: held_out(own, subject, PROBE_MENU), FAMILY: family_rule,
                  HASH: held_out(own, subject, BLIND_MENU), WHOLE: held_out(own, subject, WHOLE_MENU)}
        selected[subject] = routes
        for method, rule in routes.items():
            group['cases'][method] = group['cases'][rule]
            group['costs'][method] = group['costs'][rule]
            group['wideEpisodes'][method] = group['wideEpisodes'][rule]
    fitted = {arm: totals(list(groups.values()), arm) for arm in (SUBJECT, FAMILY, HASH, WHOLE)}
    pairs = {}
    for arm, control in ((SUBJECT, FULL), (FAMILY, FULL), (HASH, FULL), (WHOLE, FULL), (SUBJECT, HASH)):
        with patch.object(RANKING.paired_bands, 'BASELINE', control):
            pairs[f'{arm} vs {control}'] = RANKING.paired_bands.paired_ranges(groups, arm, plan)['subjectsAndCases']
    native_points = {}
    for arm, point in fitted.items():
        available = [(key, row) for key, row in native['totals'].items()
                     if key.startswith('gepa-') and row['paidLookups'] <= point['paidLookups']]
        setting, best = min(available, key=lambda item: (-Fraction(item[1]['macroAccuracy']), item[1]['paidLookups'], item[0]))
        native_points[arm] = {'setting': setting, **best}
    return {'fixed': fixed, 'fitted': fitted, 'selectedBySubject': selected,
            'withinCohortHindsightMask': fit(list(groups.values()), PROBE_MENU),
            'withinCohortHindsightWholeMask': fit(list(groups.values()), WHOLE_MENU), 'openingStrata': strata,
            'paired': pairs, 'bestAffordableNativeGEPA': native_points, 'panelTraceSha256': traces,
            'qualifies': fitted[SUBJECT]['paidLookups'] <= fixed[retry.BASE]['paidLookups'] and all(
                pairs[f'{SUBJECT} vs {control}']['interval95PercentagePoints'][0] > 0 for control in (FULL, HASH))}


def execute(plan, reference, native, data):
    gathered = {phase: measure(plan, data[phase], reference['cohorts'][phase]) for phase in RANKING.PHASES}
    bbh = RANKING.gap.paired.BBH
    mmlu = {key: group for phase in RANKING.gap.paired.replay.PHASES for key, group in gathered[phase][0].items()}
    other_family = gathered[bbh][0]
    if mmlu.keys() & other_family.keys() or len(mmlu) != sum(len(gathered[phase][0]) for phase in RANKING.gap.paired.replay.PHASES):
        raise ValueError('Evaluation cohorts must have disjoint subjects')
    cohorts = {phase: compare(plan, *entry, other_family if phase == bbh else mmlu,
                              mmlu if phase == bbh else other_family, native['cohorts'][phase])
               for phase, entry in gathered.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'cohorts': cohorts,
            'qualifies': all(row['qualifies'] for row in cohorts.values())}


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
