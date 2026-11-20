"""Veto a one-pass promotion only when the reserved panel favors the incumbent."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import expected_cost_proposal_replay as source
from benchmarks import independent_mmlu_transfer as transfer
from benchmarks import proposal_qualification_corroboration as gate
from benchmarks.case_difficulty_allocation import checked_file
from benchmarks.prompteval_transfer import holdout
from cpo._contract import digest


HISTORICAL = '3d571c92716727e4b1175dbb29ac5697bd4b656192ef4d4b0a2d8234452e0a6e'
CORPUS = '4f759dfcf44b4e591d3dd3aa15c3394b43fd131ee50816820df4a4bfc510beb4'
CAPTURE_DESIGN = 'de00800047ff8f8c382f99d789151d5a61d6be0ba98ea8b3a4b518a13fc8f25f'
POLICIES = (*gate.POLICIES, 'veto')
CAPS = (gate.CAP, *POLICIES, 171)
INDEPENDENT = 'independent-archive'


def veto_with_evidence(check):
    def decide(matrix, incumbent, result, rows, layout, *, enforce, counters):
        candidate, paid = check(matrix, incumbent, result, rows, layout, enforce=False, counters=counters)
        reserved = {str(case) for case in layout['corroborate']}
        repeated = [(prompt, passed) for prompt, case, passed in paid if case in reserved]
        if not repeated:
            return candidate, paid
        if len(repeated) != 2 * len(reserved):
            raise ValueError('The veto needs the entire fresh paired panel')
        gain = sum(passed if prompt == candidate else -passed for prompt, passed in repeated)
        counters.update(reserveLosses=int(gain < 0), reserveTies=int(gain == 0),
                        reserveGains=int(gain > 0), vetoed=int(gain < 0))
        return (incumbent if gain < 0 else candidate), paid

    return decide


def measure(plan, panels, references):
    original = source.proposal_episode
    schedule = source.continuous.schedule

    def episode(matrix, start, layouts, settings):
        policy = settings['evaluationLookupLimit']
        if policy not in POLICIES:
            return original(matrix, start, layouts, settings)
        settings = {**settings, 'evaluationLookupLimit': gate.CAP}
        if policy != 'veto':
            return gate.archive_episode(matrix, start, layouts, settings, policy=policy)
        with patch.object(gate, 'corroborate', veto_with_evidence(gate.corroborate)):
            return gate.archive_episode(matrix, start, layouts, settings, policy=policy)

    def with_reserve(case_count, template_count, held, seed, settings):
        start, layouts = schedule(case_count, template_count, held, seed, settings)
        return start, gate.reserve_cases(case_count, held, seed, layouts)

    with (patch.multiple(source, CAPS=CAPS, proposal_episode=episode),
          patch.object(source.continuous, 'schedule', with_reserve)):
        return source.measure_phase(plan, panels, references)


def prepare():
    parent, phases, _ = gate.prepare()
    original = checked_file('docs/proposal-qualification-corroboration-results-v1.json', HISTORICAL)
    if digest(parent) != original['designSha256']:
        raise ValueError('The earlier qualification replay changed')
    archived = checked_file('benchmarks/data/independent-mmlu-transfer-v1.json', CORPUS)
    capture = checked_file('docs/independent-mmlu-transfer-design-v1.json', CAPTURE_DESIGN)['design']
    transfer.check_corpus(archived, capture)
    plan, _, _ = phases['retrospective-transfer']
    sizes = {p['subject']: len(p['correctness'][0]) for p in archived['panels']}
    subjects = {p['subject'] for _, group, _ in phases.values() for p in group}
    models = {p['model'] for _, group, _ in phases.values() for p in group}
    if subjects.intersection(sizes) or models.intersection(p['model'] for p in archived['panels']):
        raise ValueError('The additional archive must use different subjects and models')
    independent_plan = {**plan, 'phase': INDEPENDENT, 'subjects': list(sizes), 'corpusSha256': CORPUS,
                        'models': list(capture['models']),
                        'holdoutCaseIDs': {subject: holdout(subject, size) for subject, size in sizes.items()}}
    design = {'protocol': 'cpo-proposal-qualification-veto-v1', 'historicalReportSha256': HISTORICAL,
              'independentCorpusSha256': CORPUS, 'captureDesignSha256': CAPTURE_DESIGN,
              'independentPlanSha256': digest(independent_plan), 'primary': 'cpo-veto',
              'primaryCohort': INDEPENDENT, 'policies': POLICIES, 'searchCap': gate.CAP,
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'gate': ('The joint paired 95 percent lower endpoint exceeds zero and paid lookups '
                       'do not exceed either official GEPA mode on the additional archive.')}
    return design, phases, original['results'], independent_plan, archived


def independent(plan, archive):
    continuous = source.continuous
    controls = (continuous.CPO[0], *continuous.GEPA)
    with patch.multiple(continuous, CPO=controls[:1], ARMS=controls):
        references = continuous.execute(plan, archive)['panels']
    report = measure(plan, archive['panels'], references)
    for name, panel in report['panels'].items():
        if panel['cpo-audit']['traceSha256'] != panel['cpo-72']['traceSha256']:
            raise ValueError(f'The audit changed the proposal path on {name}')
        for method in continuous.GEPA:
            trace = [episode['arms'][method]['steps'] for episode in references[name]['episodes']]
            if panel[method]['traceSha256'] != digest(trace):
                raise ValueError(f'The independently measured GEPA trace differs on {name}/{method}')
    comparison = report['pairedComparisons']['cpo-veto']
    report['primaryPassed'] = (comparison['jointPairedRange95'][0] > 0
                               and max(comparison['lookupDelta'].values()) <= 0)
    return report


def replay(phases, historical, plan, archive):
    reports = {}
    for phase, inputs in phases.items():
        report = measure(*inputs)
        for name, panel in report['panels'].items():
            for label, point in historical[phase]['panels'][name].items():
                if panel[label] != point:
                    raise ValueError(f'Published control {phase}/{name}/{label} changed')
        reports[phase] = report
    reports[INDEPENDENT] = independent(plan, archive)
    return reports


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, phases, historical, plan, archive = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        cli.error('Use pinned GEPA 0.1.4')
    report = {'design': design, 'designSha256': seal, 'results': replay(phases, historical, plan, archive)}
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
