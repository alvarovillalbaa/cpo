"""Stress-test routing budgets and price the best possible episode-wise route mix."""

import argparse
from fractions import Fraction
from hashlib import sha256
import json
from math import lcm
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_anchor_routing as parent, witness_no_nominee_admission as allocation
from cpo._contract import digest


ROOT, RANKING, retry, FULL, BOUNDS = parent.ROOT, parent.RANKING, parent.retry, parent.FULL, parent.BOUNDS
REFERENCE = 'docs/witness-anchor-routing-results-v1.json'
REFERENCE_SHA256 = 'b88bd033ea829964e240bf28e42c114c97c7a7361f14e3f7473eedc1dfff969e'
DROP_ONE, EACH = 'drop-one-budget-fit', 'each-subject-budget-fit'
METHODS = (DROP_ONE, EACH)


def prepare():
    source, controls, native, data = parent.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(source):
        raise ValueError('Use the published held-out opening routing comparison')
    plan = {key: source[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed')}
    plan.update(protocol='witness-anchor-routing-budget-v1', parentPlanSha256=digest(source),
                parentReceiptSha256=REFERENCE_SHA256, sourceSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                allocatorSha256=sha256(Path(allocation.__file__).read_bytes()).hexdigest(), methods=METHODS,
                primary=DROP_ONE,
                fit='Keep the same paid prefix and mask menu. Train on other subjects in the same family. '
                'Require the chosen rule to fit either every leave-one-training-subject-out budget or every '
                'individual training subject budget. Choose by macro score and lower cost as before.',
                ceiling='Using future charges and holdout grades, find the exact optimal episode-wise mixture '
                'of the two fixed routes within original expected-read or seeded cohort cost. Report separate '
                'maxima for total passes and macro accuracy, with ties broken by fewer lookups.',
                gate='Require a positive paired lower endpoint against original CPO and the original blind fit, '
                'with no more than seeded realized cost on every cohort.')
    return plan, reference, controls, native, data


def collect(plan, data, reference):
    _, panels, _, _, _ = data
    subjects = {id(panel['correctness']): panel['subject'] for panel in panels}
    original, qualify = retry.outcomes, parent.parent.reference_runner.qualify
    pending = None
    episodes = []

    def tally(matrix, held, nomination, final):
        return (nomination.paid_search + final.lookups, sum(matrix[int(final.prompt)][case] == '1' for case in held))

    def capture_original(matrix, held, start, layouts, active, policy, nomination):
        nonlocal pending
        if pending is not None:
            raise ValueError('Unmatched original episode')
        decisions = original(matrix, held, start, layouts, active, policy, nomination)
        pending = (id(matrix), id(layouts), tally(matrix, held, nomination, decisions[FULL]))
        return decisions

    def capture_wide(matrix, held, start, layouts, active, nomination):
        nonlocal pending
        if pending is None or pending[:2] != (id(matrix), id(layouts)):
            raise ValueError('Unmatched score-bound episode')
        result = qualify(matrix, held, start, layouts, active, nomination)
        episodes.append((subjects[id(matrix)], pending[2], tally(matrix, held, nomination, result)))
        pending = None
        return result

    with (patch.object(retry, 'outcomes', capture_original),
          patch.object(parent.parent.reference_runner, 'qualify', capture_wide)):
        groups, traces, _ = parent.measure(plan, data, reference)
    if pending is not None or len(episodes) != sum(group['decisionsPerCase'] for group in groups.values()):
        raise ValueError('Every enrolled episode needs one pair of outcomes')
    return groups, traces, episodes


def fit(groups, method):
    options = []
    for rule in parent.PROBE_MENU:
        excess = [group['costs'][rule] - group['costs'][retry.BASE] for group in groups]
        total = sum(excess)
        fits = max(excess) <= 0 if method == EACH else total <= 0 and total - min(excess) <= 0
        if fits:
            options.append((rule, parent.totals(groups, rule)))
    rule, _ = min(options, key=lambda row: (-Fraction(row[1]['macroAccuracy']), row[1]['paidLookups'],
                                            parent.PROBE_MENU.index(row[0])))
    return rule


def best_mixture(episodes, ceiling, weights):
    """Rebase signed route differences on the cheaper choice in each episode."""
    cheapest_cost = cheapest_score = 0
    menus = []
    for subject, original, wide in episodes:
        cheap, costly = sorted((original, wide), key=lambda row: row[0])
        cheapest_cost += cheap[0]
        cheapest_score += cheap[1] * weights[subject]
        gain = (costly[1] - cheap[1]) * weights[subject]
        if gain > 0:
            menus.append({costly[0] - cheap[0]: gain})
    if cheapest_cost > ceiling:
        raise ValueError('The cheapest route mix exceeds the supplied budget')
    best = allocation.hindsight(menus, ceiling - cheapest_cost)
    return {'score': cheapest_score + best['addedHoldoutPasses'], 'paidLookups': cheapest_cost + best['paidLookups']}


def headroom(episodes, groups, original):
    for index, method in ((1, FULL), (2, BOUNDS)):
        cost = sum(row[index][0] for row in episodes)
        passes = sum(row[index][1] for row in episodes)
        if (cost, passes) != (original[method]['paidLookups'], original[method]['holdoutPasses']):
            raise ValueError('The episode totals must reproduce both fixed routes')
    anchors = {subject: len(group['cases'][FULL]) * group['decisionsPerCase'] for subject, group in groups.items()}
    normalizer = lcm(*anchors.values())
    weights = {subject: normalizer // count for subject, count in anchors.items()}
    unweighted = dict.fromkeys(groups, 1)
    cheaper = equal_cost_gain = 0
    for _, base, wide in episodes:
        cheaper += wide[0] < base[0]
        equal_cost_gain += wide[0] <= base[0] and wide[1] > base[1]
    result = {}
    for name, key in (('originalCost', FULL), ('seededCost', retry.BASE)):
        cap = original[key]['paidLookups']
        actual = best_mixture(episodes, cap, unweighted)
        macro = best_mixture(episodes, cap, weights)
        if actual['score'] < original[FULL]['holdoutPasses']:
            raise ValueError('The exact routing ceiling must include the original route')
        result[name] = {'lookupCeiling': cap, 'rawPassMaximum': {'holdoutPasses': actual['score'],
                        'paidLookups': actual['paidLookups']},
                        'macroAccuracyMaximum': {'macroAccuracy': str(Fraction(macro['score'], normalizer * len(groups))),
                                                 'paidLookups': macro['paidLookups']}}
    return {'episodes': len(episodes), 'cheaperWideRoute': cheaper, 'wideImprovesAtNoExtraCost': equal_cost_gain,
            'episodeCostScoreTraceSha256': digest(episodes), **result}


def compare(plan, groups, traces, episodes, own, reference, native):
    fixed = {method: parent.totals(list(groups.values()), method) for method in parent.STATIC}
    if fixed != reference['fixed'] or traces != reference['panelTraceSha256']:
        raise ValueError('The old fixed routing outcomes changed')
    selected = {}
    for subject, group in groups.items():
        training = [data for name, data in own.items() if name != subject]
        old = reference['selectedBySubject'][subject]
        choices = {parent.SUBJECT: parent.held_out(own, subject, parent.PROBE_MENU),
                   parent.HASH: parent.held_out(own, subject, parent.BLIND_MENU),
                   **{method: fit(training, method) for method in METHODS}}
        if any(choices[method] != old[method] for method in (parent.SUBJECT, parent.HASH)):
            raise ValueError('The original learned opening or blind rule changed')
        selected[subject] = choices
        for method, rule in choices.items():
            group['cases'][method] = group['cases'][rule]
            group['costs'][method] = group['costs'][rule]
            group['wideEpisodes'][method] = group['wideEpisodes'][rule]
    fitted = {method: parent.totals(list(groups.values()), method) for method in (*METHODS, parent.HASH, parent.SUBJECT)}
    if any(fitted[method] != reference['fitted'][method] for method in (parent.HASH, parent.SUBJECT)):
        raise ValueError('The published learned and blind route totals changed')
    pairs, native_points = {}, {}
    for method in METHODS:
        for baseline in (FULL, parent.HASH):
            with patch.object(RANKING.paired_bands, 'BASELINE', baseline):
                pairs[f'{method} vs {baseline}'] = RANKING.paired_bands.paired_ranges(groups, method, plan)['subjectsAndCases']
        available = [(key, row) for key, row in native['totals'].items()
                     if key.startswith('gepa-') and row['paidLookups'] <= fitted[method]['paidLookups']]
        setting, best = min(available, key=lambda item: (-Fraction(item[1]['macroAccuracy']), item[1]['paidLookups'], item[0]))
        native_points[method] = {'setting': setting, **best}
    return {'controls': {key: fixed[key] for key in (retry.BASE, FULL, BOUNDS)}, 'fitted': fitted,
            'selectedBySubject': selected, 'hindsight': headroom(episodes, groups, fixed), 'paired': pairs,
            'bestAffordableNativeGEPA': native_points, 'panelTraceSha256': traces,
            'qualifies': fitted[DROP_ONE]['paidLookups'] <= fixed[retry.BASE]['paidLookups'] and all(
                pairs[f'{DROP_ONE} vs {baseline}']['interval95PercentagePoints'][0] > 0 for baseline in (FULL, parent.HASH))}


def execute(plan, reference, controls, native, data):
    gathered = {phase: collect(plan, data[phase], controls['cohorts'][phase]) for phase in RANKING.PHASES}
    bbh = RANKING.gap.paired.BBH
    mmlu_phases = RANKING.gap.paired.replay.PHASES
    mmlu = {subject: group for phase in mmlu_phases for subject, group in gathered[phase][0].items()}
    bbh_groups = gathered[bbh][0]
    if mmlu.keys() & bbh_groups.keys() or len(mmlu) != sum(len(gathered[phase][0]) for phase in mmlu_phases):
        raise ValueError('Use disjoint evaluation subjects')
    cohorts = {phase: compare(plan, *entry, bbh_groups if phase == bbh else mmlu,
                              reference['cohorts'][phase], native['cohorts'][phase])
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
