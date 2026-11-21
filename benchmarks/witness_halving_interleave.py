"""Allocate one paid Halving lookup at a time and measure the direct-cycle ceiling."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_halving_cycle_priority as parent, witness_no_nominee_admission as allocation
from cpo._contract import digest


ROOT, RANKING, FULL, replay = parent.ROOT, parent.RANKING, parent.FULL, parent.replay
REFERENCE = 'docs/witness-halving-cycle-priority-results-v1.json'
REFERENCE_SHA256 = '3e1c99cd8d93f6b56cb235dc76ed8659a039001e88739e90d09e262656f53213'
ACTIVE = 'interleave-halving-by-paid-priority'


def prepare():
    upstream, _, controls, native, data = parent.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(upstream):
        raise ValueError('Use the published fixed-order priority comparison')
    paths = (Path(__file__), Path(allocation.__file__))
    plan = {key: upstream[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed')}
    plan.update(protocol='witness-halving-interleave-v1', primary=ACTIVE, parentPlanSha256=digest(upstream),
                parentReceiptSha256=REFERENCE_SHA256,
                sourceSha256={file.resolve().relative_to(ROOT).as_posix(): sha256(file.read_bytes()).hexdigest()
                              for file in paths},
                rule='Recompute the published priority from all paid grades after each new evaluation. Let the '
                'highest-ranked cycle request at most one new grade before reprioritizing. Nominate the first '
                'settled challenger and keep the original independent proof and pooled validation cap.',
                hindsight='Enumerate every single cycle run directly from the witness cache at the original '
                'pooled cap. Include retention and at most one independent proof. Maximize holdout passes '
                'with future costs and outcomes known under the original or seeded cohort lookup budget.',
                gate='Require a positive paired lower endpoint against original Halving within seeded '
                'realized lookup spend on every cohort.')
    return plan, reference, controls, native, data


def select(start, layout, paid, evaluate, limit):
    selector = parent.cached_lookahead.CachedLookaheadHalving(metric_limit=limit, paid=paid)
    nominee = selector.select((start, *layout['alternatives']), layout['validation'], evaluate)
    return nominee, selector.observations


def fallback(start, layouts, paid, evaluate, cap, activity):
    observations = dict(paid)
    previous = None
    for remaining in range(cap, -1, -1):
        ranks = [parent.priority(start, layout, observations) for layout in layouts]
        index = max(range(len(layouts)), key=ranks.__getitem__)
        certain, priority = ranks[index]
        if not priority or (not remaining and not certain):
            break
        activity['cycleSteps'] += 1
        activity['cycleSwitches'] += int(previous is not None and previous != index)
        previous = index
        before = len(observations)
        candidate, observations = select(start, layouts[index], observations, evaluate, int(not certain))
        if candidate not in (None, start):
            activity['nominations'] += 1
            return RANKING.Nomination(candidate, len(observations), observations)
        if len(observations) != before + 1:
            raise ValueError('An unsettled chosen cycle must buy exactly one new grade')
    return RANKING.Nomination(None, len(observations), observations)


def direct_cycle_menu(start, layouts, paid, evaluate, cap, prove, score):
    gains = {}
    for layout in layouts:
        candidate, observations = select(start, layout, paid, evaluate, cap)
        if candidate in (None, start):
            continue
        search_cost = len(observations) - len(paid)
        proof = prove(RANKING.Nomination(candidate, len(observations), observations))
        gain = score(proof.prompt) - score(start)
        cost = search_cost + proof.lookups
        if gain > 0:
            gains[cost] = max(gains.get(cost, 0), gain)
    return gains


def measure(plan, data, controls, native, reference):
    original, qualify = replay.original_search, replay.reference_runner.qualify
    context = pending = None
    menus, activity = [], Counter()

    def record_search(matrix, held, start, layouts, active, policy, cap):
        nonlocal context
        if pending is not None:
            raise ValueError('An interleaved fallback was left unpriced')
        context = matrix, held, start, layouts, active
        return original(matrix, held, start, layouts, active, policy, cap)

    def run_fallback(start, layouts, paid, evaluate, cap, counts):
        nonlocal pending
        nomination = fallback(start, layouts, paid, evaluate, cap, counts)
        pending = nomination
        matrix, held, incumbent, scheduled, active = context
        if (start, id(layouts)) != (incumbent, id(scheduled)):
            raise ValueError('The direct-cycle menu must use the same witness search')
        score = lambda prompt: sum(matrix[int(prompt)][case] == '1' for case in held)
        prove = lambda candidate: qualify(matrix, held, start, layouts, active, candidate)
        menus.append(direct_cycle_menu(start, layouts, paid, evaluate, cap, prove, score))
        return nomination

    def record_proof(matrix, held, start, layouts, active, nomination):
        nonlocal pending
        if nomination is not pending:
            raise ValueError('Only the selected interleaved nomination may contribute to the policy')
        proof = qualify(matrix, held, start, layouts, active, nomination)
        activity['addedPasses'] += sum(int(matrix[int(proof.prompt)][case] == '1') -
                                       int(matrix[int(start)][case] == '1') for case in held)
        pending = None
        return proof

    with (patch.multiple(replay, PRIMARY=ACTIVE, CAPS={ACTIVE: plan['fallbackValidationCap']},
                         METHODS=(replay.retry.BASE, FULL, ACTIVE), cached_race=run_fallback, original_search=record_search),
          patch.object(replay.reference_runner, 'qualify', record_proof)):
        report = replay.measure(plan, data, controls, native)
    totals = report['totals']
    if pending is not None or report['panelTraceSha256'] != reference['panelTraceSha256'] or any(
            totals[arm] != reference['controls'][arm] for arm in (FULL, replay.retry.BASE)):
        raise ValueError('The inherited seeded or original Halving outcomes changed')
    counts = report['fallbackActivity'][ACTIVE]
    if len(menus) != counts['eligibleEpisodes'] or len(menus) != reference['fallbackActivity'][parent.PRIORITY]['eligibleEpisodes']:
        raise ValueError('Every eligible episode needs exactly one direct-cycle menu')
    witness_paid = totals[ACTIVE]['paidLookups'] - counts['validationLookups'] - counts['proofLookups']
    witness_passes = totals[ACTIVE]['holdoutPasses'] - activity['addedPasses']
    hindsight = {}
    for key, control in (('originalCost', FULL), ('seededCost', replay.retry.BASE)):
        budget = totals[control]['paidLookups'] - witness_paid
        best = allocation.hindsight(menus, budget)
        hindsight[key] = {'lookupCeiling': totals[control]['paidLookups'],
                          'holdoutPasses': witness_passes + best['addedHoldoutPasses'],
                          'paidLookups': witness_paid + best['paidLookups']}
    return {**report, 'publishedFixedPriority': reference['totals'][parent.PRIORITY],
            'directCycleHindsight': {'eligibleEpisodes': len(menus), 'episodesWithAnImprovingCertifiedChoice':
                                     sum(bool(menu) for menu in menus), **hindsight}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, reference, controls, native, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    cohorts = {phase: measure(plan, data[phase], controls['cohorts'][phase], native['cohorts'][phase],
                              reference['cohorts'][phase]) for phase in RANKING.PHASES}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'cohorts': cohorts, 'newProviderRequests': 0,
                   'qualifies': all(row['qualifies'] for row in cohorts.values())}, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
