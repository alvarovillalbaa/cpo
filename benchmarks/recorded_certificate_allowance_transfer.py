"""Replay the frozen four-read allowance on disjoint archived tasks and models."""

import argparse
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_certificate_allowance as allowance
from cpo._contract import digest


baseline = allowance.baseline
transfer = baseline.transfer
ARM = '4-sixths-panel'
DISCOVERY = 'docs/recorded-certificate-allowance-results-v1.json'
DISCOVERY_SHA256 = 'cba2bb2d3c4d062914118d68bb369732d3eb85ef1464eaa829fc18e9d73fbc00'
ARCHIVES = {'qualification-order-transfer-v3.json': 'dae40ce166fabd49e8e3559db5a342a4047455c023d32dfe8c0efe2ea80bd326'}
NEW_TASKS = 'disjoint-tasks-and-models'
KNOWN_TASKS = 'original-tasks-on-disjoint-models'


def partition(discovery, target):
    original_tasks = {(cohort, subject) for cohort, subject, _, _ in discovery}
    original_models = {model for _, _, model, _ in discovery}
    if any(model in original_models for _, _, model, _ in target):
        raise ValueError('The target archive must use disjoint model checkpoints')
    groups = {NEW_TASKS: [], KNOWN_TASKS: []}
    for panel in target:
        group = KNOWN_TASKS if panel[:2] in original_tasks else NEW_TASKS
        groups[group].append(panel)
    if not all(groups.values()):
        raise ValueError('The target must contain both disjoint tasks and cross-model replication tasks')
    return groups


def prepare():
    frozen, schedule, _, (discovery, _), _ = allowance.prepare()
    reference = baseline.read_reference(DISCOVERY, DISCOVERY_SHA256, frozen)
    with patch.object(transfer, 'ARCHIVES', ARCHIVES):
        groups = partition(discovery, transfer.load_panels())
    plan = {**{key: schedule[key] for key in ('gepaVersion', 'searchCap', 'minimumLookupSavingPercent',
                                             'bootstrapSeed', 'bootstrapDraws', 'seeds', 'challengers', 'caseCounts')},
            'protocol': 'recorded-certificate-allowance-transfer-v1', 'parentPlanSha256': digest(frozen),
            'parentReceiptSha256': DISCOVERY_SHA256, 'archiveSha256': ARCHIVES,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'candidate': ARM, 'methods': (*transfer.METHODS, ARM),
            'effectiveExtraReads': schedule['caseCounts'][1] * frozen['fixedAllowancesInSixthsOfPanelWidth'][ARM] // 6,
            'discoveryPanels': [panel[:3] for panel in discovery if panel[0] in ('LMentry', 'BBH')],
            'enrolledPanels': {name: [panel[:3] for panel in panels] for name, panels in groups.items()},
            'scope': 'Freeze the four-read later-first policy and the original search, held-out cases, '
                     'corroboration, and expected-cost qualification. Enroll every target panel by task identity '
                     'before replay. Compare against both unchanged GEPA controls within each cohort of the '
                     'disjoint-task archive. Report the original tasks on two different models as replication.'}
    if plan['effectiveExtraReads'] != 4:
        raise ValueError('The discovery schedule must preserve the original four-read allowance')
    return plan, discovery, groups, reference


def replay(plan, panels):
    default_trial = transfer.study.trial
    first = transfer.study.FIRST

    def trial(*arguments):
        runner = baseline.trial if arguments[-1] == ARM else default_trial
        return runner(*arguments)

    with (patch.object(transfer, 'METHODS', plan['methods']), patch.object(transfer.study, 'trial', trial),
          patch.object(baseline, 'LIMITS', {ARM: 1}),
          patch.object(baseline, 'search_for_stronger', partial(allowance.search, ARM))):
        report = transfer.replay(plan, panels)
    for cohort in report['cohorts'].values():
        totals = cohort['totals']
        vectors = {subject: {**rows, first: rows[ARM]} for subject, rows in cohort['caseVectorsBySubject'].items()}
        cohort['firstCertificateComparison'] = {key: cohort.pop(key) for key in
                                               ('caseSensitivityRanges', 'gate', 'lookupSavingFractions')}
        cohort['fourReadComparison'] = transfer.compare(plan, {**totals, first: totals[ARM]}, vectors)
    return report['cohorts']


def execute(plan, discovery, groups, reference):
    first = transfer.study.FIRST
    known = replay(plan, [panel for panel in discovery if panel[0] in ('BBH', 'LMentry')])
    for name, cohort in known.items():
        expected = reference['transfer'][name]
        comparison = {key: value for key, value in expected['comparisons'][ARM].items() if key != 'withoutSubject'}
        if (cohort['totals'][first] != expected['firstCertificate'] or cohort['totals'][ARM] != expected['totals'][ARM]
                or cohort['fourReadComparison'] != comparison):
            raise ValueError('The discovery control and frozen four-read results must reproduce')
    results = {name: replay(plan, panels) for name, panels in groups.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, discovery, groups, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = execute(plan, discovery, groups, reference)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
