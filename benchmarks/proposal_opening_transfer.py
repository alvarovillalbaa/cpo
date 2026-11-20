"""Test the frozen eight-case opening screen on fifteen separate archived subjects."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import expected_cost_proposal_replay as source
from benchmarks import proposal_reflection_cap as reflections
from benchmarks import proposal_short_validation as short
from benchmarks.case_difficulty_allocation import checked_file
from benchmarks.prompteval_transfer import MODELS, holdout
from cpo import expected_cost_proposal_cycle as cycle
from cpo._contract import digest


REFERENCE = '6a4e61353e4101c07cd527f80d28c103b1f7ab592cb1650893428c8470eda701'
REVISION = '1639d5ea14c362f6964f260ae81bd903af760187'
SNAPSHOTS = {
    'prompteval-transfer': '2c79f692d761cb816e0066269b1f330f7d961f885177f166e067221f10263243',
    'prompteval-episode-budget': '91a4f77273dc7ef934f766ea8652a4a16daa1c8c7cc24adeab91e66a890f7297',
    'prompteval-requalification': '5d9944780a816b8a095f31b882844273b62c694a6e81a06c8d3c9bf32c66346b',
    'prompteval-search-coverage': '32f842cfa8b6f16b06efd52475d5a7e24e610fedb76362ef743dbbaf258d3f7d',
}
PRIMARY = 'cpo-short-8-r0'
CAPS = (short.CAP, 'short-8-r0', 171)


def prepare():
    parent, phases, _ = reflections.prepare()
    frozen = checked_file('docs/proposal-reflection-cap-results-v1.json', REFERENCE)
    if digest(parent) != frozen['designSha256']:
        raise ValueError('The earlier reflection-cap comparison changed')
    excluded = {p['subject'] for _, group, _ in phases.values() for p in group}
    template, _, _ = phases['retrospective-transfer']
    minimum = (template['cycles'] * template['qualificationRowsPerCycle']
               + template['trainRows'] + template['validationRows'])
    panels, held, cohorts = [], {}, {}
    for name, fingerprint in SNAPSHOTS.items():
        corpus = checked_file(f'benchmarks/data/{name}-v1.json', fingerprint)
        if (corpus['schema'], corpus['sourceDataset'], corpus['observedRepoRevision']) != (
                'prompteval-transfer-v1', 'PromptEval/PromptEval_MMLU_correctness', REVISION):
            raise ValueError('The snapshot must use the published PromptEval revision')
        models = defaultdict(set)
        for panel in corpus['panels']:
            subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
            if subject in excluded or subject in cohorts or model in models[subject]:
                raise ValueError('Transfer requires subjects outside the tuning cohort and distinct panels')
            if len(matrix) != 100 or not all(isinstance(row, str) for row in matrix):
                raise ValueError('Each panel needs one binary vector per template')
            size = len(matrix[0])
            test = holdout(subject, size)
            if (size - len(test) < minimum or held.setdefault(subject, test) != test
                    or any(len(row) != size or set(row) - {'0', '1'} for row in matrix)):
                raise ValueError('The archived panel must support the frozen disjoint schedule')
            panels.append(panel)
            models[subject].add(model)
        if any(used != set(MODELS) for used in models.values()):
            raise ValueError('Each subject needs both recorded model panels')
        cohorts.update(dict.fromkeys(models, name))
    if len(panels) != 30 or len(cohorts) != 15:
        raise ValueError('The transfer roster must include all 30 panels')
    plan = {**template, 'subjects': list(cohorts), 'holdoutCaseIDs': held, 'phase': 'opening-transfer',
            'corpusSha256': digest(SNAPSHOTS)}
    design = {'protocol': 'cpo-proposal-opening-transfer-v1', 'referenceReportSha256': REFERENCE,
              'snapshots': SNAPSHOTS, 'subjectsBySnapshot': cohorts, 'planSha256': digest(plan),
              'primary': PRIMARY, 'searchCap': short.CAP, 'screenWidth': 8, 'laterReflectionCap': 0,
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'gate': ('The primary arm must gain passes over retaining the start, have a positive joint paired '
                       '95 percent lower endpoint against both GEPA modes, and cost no more than either control.')}
    return design, plan, panels, cohorts


def replay(plan, panels, cohorts):
    continuous = source.continuous
    controls = (continuous.CPO[0], *continuous.GEPA)
    with patch.multiple(continuous, ARMS=controls, CPO=controls[:1]):
        references = continuous.execute(plan, {'panels': panels})['panels']
    original = source.proposal_episode

    def episode(matrix, start, layouts, settings):
        if settings['evaluationLookupLimit'] != 'short-8-r0':
            return original(matrix, start, layouts, settings)
        with patch.object(cycle, 'search', reflections.bounded_search(cycle.search, 0)):
            return short.archive_episode(matrix, start, layouts, {**settings, 'evaluationLookupLimit': short.CAP},
                                         width=8)

    with patch.multiple(source, CAPS=CAPS, proposal_episode=episode):
        report = source.measure_phase(plan, panels, references)
    snapshots = defaultdict(lambda: defaultdict(Counter))
    by_subject = defaultdict(Counter)
    base = 0
    for name, values in report['panels'].items():
        ref = references[name]
        for arm in continuous.GEPA:
            trace = [item['arms'][arm]['steps'] for item in ref['episodes']]
            if values[arm]['traceSha256'] != digest(trace):
                raise ValueError(f'The native GEPA path drifted for {name}/{arm}')
        subject = name.split('/')[0]
        snapshot = snapshots[cohorts[subject]]
        base += ref['initialPasses']
        values['retain-start'] = {'holdoutPasses': ref['initialPasses'], 'paidLookups': 0}
        for arm, point in values.items():
            snapshot[arm].update(holdoutPasses=point['holdoutPasses'], paidLookups=point['paidLookups'])
        for arm in continuous.GEPA:
            by_subject[subject][arm] += values[PRIMARY]['holdoutPasses'] - values[arm]['holdoutPasses']
    report['retainStartPasses'] = base
    report['snapshots'] = dict(snapshots)
    comparison = report['pairedComparisons'][PRIMARY]
    report['leaveOneSubjectOutMinDelta'] = {
        subject: min(comparison['passDelta'][arm] - delta[arm] for arm in continuous.GEPA)
        for subject, delta in by_subject.items()}
    report['primaryPassed'] = (comparison['jointPairedRange95'][0] > 0
                               and max(comparison['lookupDelta'].values()) <= 0
                               and report['totals'][PRIMARY]['holdoutPasses'] > base)
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, plan, panels, cohorts = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        cli.error('Use pinned GEPA 0.1.4')
    report = {'design': design, 'designSha256': seal, 'results': replay(plan, panels, cohorts)}
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
