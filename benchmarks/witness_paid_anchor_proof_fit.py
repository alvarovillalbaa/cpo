"""Fit proof eligibility and the anchor fallback cap without using the held-out subject."""

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import witness_anchor_routing as routing, witness_paid_anchor_bounds as parent
from cpo._contract import digest


ROOT, FULL, RANKING = parent.ROOT, parent.FULL, parent.RANKING
replay = parent.parent
REFERENCE = 'docs/witness-paid-anchor-bounds-results-v1.json'
REFERENCE_SHA256 = '80208c5113b8743d00ae138dcb5e6fe247a43367ec0ea72077a26564b92d8ff3'
CAPS = {f'paid-anchor-proved-gain/{limit}': limit for limit in (8, 12, 16)}
SIGNALS = ('no-proof', 'all', 'two-anchor-wins', 'preserve-paid-passes', 'two-net-paired-wins')
RATES = ('quarter', 'half', 'three-quarters')
PRIMARY, BLIND = 'held-out-paid-proof-fit', 'held-out-blind-proof-fit'
MENUS = {PRIMARY: (FULL, *((arm, rule) for arm in CAPS for rule in SIGNALS)),
         BLIND: (FULL, *((arm, rule) for arm in CAPS for rule in ('no-proof', 'all', *RATES)))}


def prepare():
    upstream, _, controls, native, data = parent.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(upstream):
        raise ValueError('Use the published initialized race and proved-gain fallback')
    plan = {key: upstream[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed', 'anchors')}
    plan.update(protocol='witness-paid-anchor-proof-fit-v1', parentPlanSha256=digest(upstream),
                parentReceiptSha256=REFERENCE_SHA256, sourceSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                primary=PRIMARY, caps=CAPS, menus=MENUS,
                scope='Preserve every witness nomination and settled exact race. Use only paid validation '
                'grades to decide whether a proved-gain challenger at the cap earns one independent proof.',
                fit='Hold out each subject including both model panels and all seeds. On the other subjects '
                'within the benchmark family, choose the cap and authorization rule with best macro score '
                'within their seeded total. Break ties by lower cost and then menu order.',
                gate='Require a positive paired lower endpoint against original Halving and the independently '
                'fitted blind gate, with realized lookup cost within the seeded total on every cohort.')
    return plan, reference, controls, native, data


def eligible_rules(start, nominee, layout, grades, bucket):
    anchors = list(layout['validation'])
    Random(layout['seed']).shuffle(anchors)
    anchors = anchors[:replay.ANCHORS]
    lead = sum(grades.get((nominee, case), False) - grades.get((start, case), True) for case in anchors)
    if lead <= 0:
        raise ValueError('Proof eligibility requires a strict anchor gain at the lookup cap')
    paired = [new - grades[start, case] for (prompt, case), new in grades.items()
              if prompt == nominee and (start, case) in grades]
    allowed = {'all'}
    if lead >= 2:
        allowed.add('two-anchor-wins')
    if all(delta >= 0 for delta in paired):
        allowed.add('preserve-paid-passes')
    if sum(paired) >= 2:
        allowed.add('two-net-paired-wins')
    allowed.update(rate for index, rate in enumerate(RATES, 1) if bucket < index)
    return frozenset(allowed)


def collect(plan, data, controls, native, reference):
    _, panels, *_ = data
    panel_identity = {id(panel['correctness']): (panel['subject'], panel['model']) for panel in panels}
    search, qualify = replay.original_search, replay.reference_runner.qualify
    paired_ranges = RANKING.paired_bands.paired_ranges
    episodes, events = Counter(), defaultdict(list)
    current = pending = groups = None

    def record_search(matrix, held, start, layouts, active, policy, cap):
        nonlocal current
        if pending is not None:
            raise ValueError('An extra proof went unrecorded')
        key = id(matrix)
        subject, model = panel_identity[key]
        seed = active['seeds'][episodes[key]]
        episodes[key] += 1
        current = subject, model, seed
        return search(matrix, held, start, layouts, active, policy, cap)

    def record_fallback(start, layouts, paid, evaluate, limit, activity):
        nonlocal pending
        before = activity['provedGainAtCap']
        nomination = parent.fallback(start, layouts, paid, evaluate, limit, activity, allow_proved_gain=True)
        if activity['provedGainAtCap'] > before:
            layout = next(layout for layout in layouts if nomination.original in layout['alternatives'])
            allowed = eligible_rules(start, nomination.original, layout, nomination.grades,
                                     int(digest(current), 16) % 4)
            pending = nomination, limit, allowed
        return nomination

    def record_proof(matrix, held, start, layouts, active, nomination):
        nonlocal pending
        result = qualify(matrix, held, start, layouts, active, nomination)
        if pending is not None:
            expected, limit, allowed = pending
            if nomination is not expected or panel_identity[id(matrix)] != current[:2]:
                raise ValueError('An extra proof must match the captured nomination and panel')
            gain = tuple(int(matrix[int(result.prompt)][case] == '1') - int(matrix[int(start)][case] == '1')
                         for case in held)
            events[current[0], limit].append((current, allowed, result.lookups, gain))
            pending = None
        return result

    def record_groups(observed, method, active):
        nonlocal groups
        groups = observed
        return paired_ranges(observed, method, active)

    with (patch.multiple(replay, CAPS=CAPS, METHODS=(replay.retry.BASE, FULL, *CAPS), PRIMARY=parent.PROVED,
                         cached_race=record_fallback, original_search=record_search),
          patch.object(replay.reference_runner, 'qualify', record_proof),
          patch.object(RANKING.paired_bands, 'paired_ranges', record_groups)):
        fixed = replay.measure(plan, data, controls, native)
    if pending is not None or groups is None or fixed['panelTraceSha256'] != reference['panelTraceSha256']:
        raise ValueError('The archived proof or original panel trace changed')
    if fixed['totals'][parent.PROVED] != reference['totals'][parent.PROVED] or (
            fixed['fallbackActivity'][parent.PROVED] != reference['fallbackActivity'][parent.PROVED]):
        raise ValueError('The published 16-lookup proved-gain arm changed')
    for arm, limit in CAPS.items():
        seen = [event[0] for (subject, cap), rows in events.items() if cap == limit for event in rows]
        if len(seen) != fixed['fallbackActivity'][arm].get('provedGainAtCap', 0) or len(seen) != len(set(seen)):
            raise ValueError('Each extra proof must have one unique event')
    return groups, fixed, events


def materialize(groups, events):
    for subject, group in groups.items():
        proofs = {FULL: 0}
        for arm, limit in CAPS.items():
            rows = events.get((subject, limit), ())
            for rule in (*SIGNALS, *RATES):
                method = arm, rule
                scores, paid = group['cases'][arm].copy(), group['costs'][arm]
                count = 0
                for _, allowed, charge, gains in rows:
                    if rule in allowed:
                        count += 1
                    else:
                        scores = [score - gain for score, gain in zip(scores, gains, strict=True)]
                        paid -= charge
                group['cases'][method], group['costs'][method], proofs[method] = scores, paid, count
        group['extraProofs'] = proofs


def fit_subject(family, subject, method):
    training = [group for name, group in family.items() if name != subject]
    return routing.fit(training, MENUS[method])


def totals(groups, method):
    row = routing.totals(list(groups.values()), method)
    del row['wideEpisodes']
    return {**row, 'extraProofs': sum(group['extraProofs'][method] for group in groups.values())}


def compare(plan, groups, fixed, family, native, reference):
    exact = totals(groups, (parent.PROVED, 'no-proof'))
    if {key: exact[key] for key in reference['totals'][parent.EXACT]} != reference['totals'][parent.EXACT]:
        raise ValueError('Removing the optional proofs must reproduce the earlier exact arm')
    selected = {}
    for subject, group in groups.items():
        selected[subject] = {}
        for method in (PRIMARY, BLIND):
            rule = fit_subject(family, subject, method)
            selected[subject][method] = rule
            group['cases'][method] = group['cases'][rule]
            group['costs'][method] = group['costs'][rule]
            group['extraProofs'][method] = group['extraProofs'][rule]
    learned = {method: totals(groups, method) for method in (PRIMARY, BLIND)}
    pairs = {}
    for control in (FULL, BLIND):
        with patch.object(RANKING.paired_bands, 'BASELINE', control):
            pairs[control] = RANKING.paired_bands.paired_ranges(groups, PRIMARY, plan)['subjectsAndCases']
    available = [(key, row) for key, row in native['totals'].items()
                 if key.startswith('gepa-') and row['paidLookups'] <= learned[PRIMARY]['paidLookups']]
    setting, best = min(available, key=lambda item: (-Fraction(item[1]['macroAccuracy']), item[1]['paidLookups'], item[0]))
    return {'controls': fixed['totals'], 'fallbackActivity': fixed['fallbackActivity'], 'learned': learned,
            'selectedBySubject': selected, 'pairedPrimary': pairs, 'panelTraceSha256': fixed['panelTraceSha256'],
            'fixedSignalMenu': [{'cap': CAPS[arm], 'rule': rule, **totals(groups, (arm, rule))}
                                for arm in CAPS for rule in SIGNALS],
            'bestAffordableNativeGEPA': {'setting': setting, **best},
            'qualifies': learned[PRIMARY]['paidLookups'] <= fixed['totals'][replay.retry.BASE]['paidLookups']
            and all(pair['interval95PercentagePoints'][0] > 0 for pair in pairs.values())}


def run(plan, reference, controls, native, data):
    phases = RANKING.PHASES
    refs = reference['cohorts']
    gathered = {phase: collect(plan, data[phase], controls['cohorts'][phase], native['cohorts'][phase],
                               refs[phase]) for phase in phases}
    bbh = RANKING.gap.paired.BBH
    families = {bbh: {}, 'mmlu': {}}
    for phase, (groups, _, events) in gathered.items():
        materialize(groups, events)
        family = families[bbh if phase == bbh else 'mmlu']
        if groups.keys() & family.keys():
            raise ValueError('Cohort subjects must be disjoint within each benchmark family')
        family.update(groups)
    return {phase: compare(plan, groups, fixed, families[bbh if phase == bbh else 'mmlu'],
                           native['cohorts'][phase], refs[phase]) for phase, (groups, fixed, _) in gathered.items()}


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
    cohorts = run(plan, *inputs)
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'cohorts': cohorts, 'newProviderRequests': 0,
                   'qualifies': all(group['qualifies'] for group in cohorts.values())}, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
