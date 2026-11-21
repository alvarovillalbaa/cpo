"""Transfer the public two-witness policy to disjoint archived MMLU panels."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_two_witness_pool_parity as parity
from cpo._contract import digest


model_transfer = parity.transfer
cost = model_transfer.cost
transfer = model_transfer.transfer
ARCHIVES = {
    'routed-finalist-model-transfer-v1.json': '69db28a8cb4cbe3e18b17a847e6f5d0eb3dff6554612b6486efe58df79f4a5c7',
    'routed-start-model-confirmation-v1.json': 'c0b444d66986002f84fdeb46d22c3b459eda3d63a5c1d3ebae4130a935e381c8',
}
PARITY_SHA256 = '8edd4b652562619d7db069724a1ee4c595ad4c2b8ef0d1d519e8a92695041c62'
FIRST = transfer.study.FIRST
EARLIER = transfer.study.prior.CANDIDATE
METHODS = (*model_transfer.CPO, FIRST, EARLIER)


def enroll(panels, prior):
    used = {(label, subject) for label, subject, _, _ in prior}
    models = {model for _, _, model, _ in prior}
    if any(model in models or label != 'MMLU' for label, _, model, _ in panels):
        raise ValueError('The MMLU target requires disjoint model checkpoints')
    included = [panel for panel in panels if panel[:2] not in used]
    excluded = [panel[:3] for panel in panels if panel[:2] in used]
    return included, excluded


def prepare():
    verified, references = parity.prepare()
    cost.prior.baseline.read_reference('docs/recorded-two-witness-pool-parity-results-v1.json', PARITY_SHA256,
                                       verified)
    source, original, _, _ = cost.prior.prepare()
    previous = original + [panel for entries in references.values() for panel, _ in entries]
    with patch.object(transfer, 'ARCHIVES', ARCHIVES):
        panels, excluded = enroll(transfer.load_panels(), previous)
    plan = {**{key: source[key] for key in ('gepaVersion', 'searchCap', 'bootstrapSeed',
                                            'bootstrapDraws', 'seeds', 'challengers', 'caseCounts')},
            'protocol': 'recorded-two-witness-mmlu-transfer-v1', 'parentPlanSha256': digest(verified),
            'parentReceiptSha256': PARITY_SHA256, 'archivesSha256': ARCHIVES,
            'selectorSha256': verified['selectorSha256'], 'minimumSearchCap': source['caseCounts'][1],
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'primary': model_transfer.screen.PAIRED, 'cpoMethods': METHODS,
            'enrolledPanels': [panel[:3] for panel in panels], 'excludedPreviouslyExaminedTasks': excluded,
            'scope': 'Apply the frozen public selector to all eligible MMLU panels from the two archives. '
                     'Exclude previously examined tasks by identity and reject overlapping model checkpoints. '
                     'Retain the original single-cycle search, training and qualification schedule and '
                     'compare against the same pooled realized-cost GEPA frontier. After selection, '
                     'measure hindsight headroom with and without the three exact proof gates.'}
    return plan, panels


def ceilings(cells, incumbent, roster, cohorts):
    training, validation, qualification, heldout = cohorts
    proof_panels = (training[:len(training) // 2], validation, qualification)

    def score(prompt, cases):
        return sum(cells[prompt][case][0] for case in cases)

    baseline = tuple(score(incumbent, cases) for cases in proof_panels)
    start = roster_best = eligible_best = score(incumbent, heldout)
    for prompt in roster:
        grade = score(prompt, heldout)
        roster_best = max(roster_best, grade)
        if all(score(prompt, cases) > before for cases, before in zip(proof_panels, baseline, strict=True)):
            eligible_best = max(eligible_best, grade)
    return start, roster_best, eligible_best


def audit_headroom(plan, panels, results):
    counts = Counter()
    with patch.object(model_transfer.shortlist, 'shortlist', parity.use_public):
        for _, subject, _, matrix in panels:
            cells = {str(index): tuple((int(passed), None, False) for passed in vector)
                     for index, vector in enumerate(matrix)}
            for seed in plan['seeds']:
                start, roster, cohorts = transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
                point, trace, _ = model_transfer.shortlist.trial(cells, start, roster, cohorts, seed,
                                                                 plan['searchCap'], plan['primary'])
                initial, roster_best, eligible_best = ceilings(cells, start, roster, cohorts)
                observed = point['holdoutPasses']
                if observed > eligible_best:
                    raise ValueError('The deployed prompt must fit the hindsight proof-constrained ceiling')
                counts.update(trials=1, incumbentHoldoutPasses=initial, observedHoldoutPasses=observed,
                              rosterCeilingPasses=roster_best, proofConstrainedCeilingPasses=eligible_best,
                              trialsPromoted=int(trace[3] != start),
                              trialsWithBetterEligiblePrompt=int(eligible_best > observed),
                              precheckStops=point['precheckStops'], paidLookups=point['paidLookups'])
    observed = results['totals'][plan['primary']]
    if (counts['observedHoldoutPasses'] != observed['holdoutPasses']
            or counts['paidLookups'] != observed['paidLookups']
            or counts['incumbentHoldoutPasses'] != results['totals'][cost.frontier.RETAIN]['holdoutPasses']):
        raise ValueError('The headroom audit must reproduce both public selector and incumbent totals')
    return counts


def replay(plan, panels):
    def public_search(*args, cap, arm, audit):
        return parity.use_public(*args, cap=cap, keep_ties=False, audit=audit)

    with (patch.object(model_transfer.screen, 'search', public_search),
          patch.object(model_transfer, 'CPO', METHODS),
          patch.object(model_transfer, 'METHODS', (*METHODS, *cost.MODES, cost.frontier.RETAIN))):
        results = model_transfer.measure_cohort(plan, panels)
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results,
            'hindsightHeadroom': audit_headroom(plan, panels, results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, panels)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
