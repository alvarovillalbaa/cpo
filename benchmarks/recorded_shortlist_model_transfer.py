"""Confirm the frozen two-witness shortlist on different archived model checkpoints."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_shortlist_screen_order as screen
from cpo._contract import digest


shortlist = screen.previous
cost = shortlist.cost
transfer = cost.transfer
REFERENCE = 'docs/recorded-shortlist-screen-order-results-v1.json'
REFERENCE_SHA256 = 'cb1ac83e7af0e3a035d1292c14f885fdb0eb6329f707f13488ed2a84b78145f5'
ARCHIVES = {'shortlist-model-transfer-v1.json': 'de2369fce95132c95fea9d84f5b4d3b80b96b484bcf0f9ae0f0602081c535859'}
CPO = (screen.PAIRED, shortlist.FIXED)
METHODS = (*CPO, *cost.MODES, cost.frontier.RETAIN)
NEW_TASKS = 'disjoint-tasks-and-models'
KNOWN_TASKS = 'previous-tasks-on-disjoint-models'


def partition(discovery, target):
    models = {model for _, _, model in discovery}
    tasks = {(cohort, subject) for cohort, subject, _ in discovery}
    groups = {NEW_TASKS: [], KNOWN_TASKS: []}
    for panel in target:
        cohort, subject, model, _ = panel
        if model in models:
            raise ValueError('Confirmation requires different model checkpoints')
        group = KNOWN_TASKS if (cohort, subject) in tasks else NEW_TASKS
        groups[group].append(panel)
    if not all(groups.values()):
        raise ValueError('Confirmation requires both new tasks and model-only transfer tasks')
    return groups


def prepare():
    frozen, tuning, _, _, _ = screen.prepare()
    reference = cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, frozen)
    source, _, _, _ = cost.prior.prepare()
    identities = [tuple(panel[:3]) for panels in tuning.values() for panel in panels] + source['discoveryPanels']
    with patch.object(transfer, 'ARCHIVES', ARCHIVES):
        groups = partition(identities, transfer.load_panels())
    plan = {**{key: frozen[key] for key in ('gepaVersion', 'bootstrapSeed', 'bootstrapDraws', 'searchCap',
                                            'minimumSearchCap', 'seeds', 'challengers', 'caseCounts')},
            'protocol': 'recorded-shortlist-model-transfer-v1', 'parentPlanSha256': digest(frozen),
            'parentReceiptSha256': REFERENCE_SHA256, 'archivesSha256': ARCHIVES,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'primary': screen.PAIRED, 'methodsAtOriginalCap': METHODS,
            'enrolledPanels': {name: [panel[:3] for panel in panels] for name, panels in groups.items()},
            'scope': 'Freeze the two-witness shortlist and exact pruning. Keep the original fixed halves as '
                     'a CPO reference. Enroll every target panel by identity before scoring. Separate new '
                     'tasks from previously examined tasks on different checkpoints. Retain the original '
                     'layout, training, qualification and 350-setting realized GEPA cost frontier.'}
    return plan, groups, tuning, reference['results']


def full_cap(subject, matrix, plan):
    old_trial = transfer.study.trial

    def choose(*args, cap, keep_ties, audit):
        return screen.search(*args, cap=cap, arm=screen.PAIRED, audit=audit)

    def trial(*args):
        arm = args[-1]
        if arm == shortlist.FIXED:
            return shortlist.trial(*args)
        if arm == screen.PAIRED:
            with patch.object(shortlist, 'shortlist', choose):
                return shortlist.trial(*args)
        return old_trial(*args)

    with patch.object(transfer, 'METHODS', METHODS), patch.object(transfer.study, 'trial', trial):
        return transfer.measure_panel(matrix, subject, plan)


def measure_cohort(plan, panels):
    totals, vectors, details = {}, {}, {}
    retain = cost.frontier.RETAIN
    for _, subject, model, matrix in panels:
        full, full_scores = full_cap(subject, matrix, plan)
        points, scores = cost.measure_panel(subject, matrix, plan,
                                           {'totals': full, 'holdoutCases': len(full_scores[retain])})
        for mode in cost.MODES:
            if scores[f"{mode}/{plan['searchCap']}"] != full_scores[mode]:
                raise ValueError('Compressed GEPA case vectors must match the direct original-cap runs')
        details[f'{subject}/{model}'] = full
        rows = vectors.setdefault(subject, {})
        for label, count in {**points, **{arm: full[arm] for arm in (*CPO, retain)}}.items():
            totals.setdefault(label, Counter()).update({key: count[key] for key in cost.METRICS})
            grades = scores[label] if label in scores else full_scores[label]
            prior = rows.get(label, [0] * len(grades))
            rows[label] = [a + b for a, b in zip(prior, grades, strict=True)]
    if any(sum(sum(rows[label]) for rows in vectors.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('The score for every setting must match its paired case counts')
    settings = tuple(label for label in totals if label not in (*CPO, retain))
    comparison = cost.frontier.compare(totals, vectors, policies=CPO, draws=plan['bootstrapDraws'],
                                       seed=plan['bootstrapSeed'], groups={'either-mode': settings})
    return {'totals': totals, 'comparisons': {arm: row['either-mode'] for arm, row in comparison.items()},
            'panelsAtOriginalCap': details}


def execute(plan, groups, tuning, reference):
    for group, panels in tuning.items():
        for benchmark in reference[group]:
            _, subject, model, matrix = next(panel for panel in panels if panel[0] == benchmark)
            direct, _ = full_cap(subject, matrix, plan)
            archived = reference[group][benchmark]['panels'][f'{subject}/{model}']
            if any(direct[arm] != archived[arm] for arm in CPO):
                raise ValueError('The frozen shortlist path must match the published tuning receipt')
    results = {name: {cohort: measure_cohort(plan, [panel for panel in panels if panel[0] == cohort])
                      for cohort in sorted({label for label, *_ in panels})} for name, panels in groups.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, tuning, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = execute(plan, groups, tuning, reference)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
