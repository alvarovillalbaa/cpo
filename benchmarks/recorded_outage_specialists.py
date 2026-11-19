"""Compare archived outage specialists with whole-prompt replacement and diverse search."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_archive_restart as restart, recorded_outage_witness as witness
from benchmarks import recorded_promotion_strata as strata
from benchmarks.recorded_field_preservation import SOURCE_PLAN_SHA256, parse, verified
from cpo._contract import digest


TASK = 'outage'
TARGETS = {'long-missing': (2, 'MISSING'), 'long-posted': (2, 'POSTED')}
METHODS = witness.METHODS
MODES = ('base', 'routed', 'whole')
ROUTE = 'cpo.routed'
ROOT = Path(__file__).resolve().parents[1]
PRIOR_WITNESS_SHA256 = '769ce6f194025d07e330592daf4ae7bce09530bc5ab8507a7ae7380e949caee2'


def reserve_cases(risks):
    groups = {name: sorted(case for case, risk in risks.items() if risk == target) for name, target in TARGETS.items()}
    if any(len(cases) < 3 for cases in groups.values()):
        raise ValueError('Both target strata need two selection cases and a retained case')
    return {name: cases[:2] for name, cases in groups.items()}


def select_strict_winner(incumbent, observations, cases):
    """A candidate must pass the entire panel, with a strict gain over the incumbent."""
    if not cases or any(type(observations[incumbent].get(case)) is not bool for case in cases):
        raise ValueError('Require complete incumbent evidence on a nonempty reserve')
    if all(observations[incumbent][case] for case in cases):
        return None
    return next((prompt for prompt in sorted(observations) if prompt != incumbent and
                 all(observations[prompt].get(case) is True for case in cases)), None)


def prompt_for_case(primary, specialists, whole, mode, risk):
    if mode == 'whole':
        return whole or primary
    if mode == 'routed':
        return specialists.get(risk) or primary
    return primary


def route_scores(cases, risks, primary, specialists, whole, mode, outcomes):
    return {case: outcomes.get(prompt_for_case(primary, specialists, whole, mode, risks[case]), {}).get(case)
            for case in cases}


def compare_provider(left, right, critical):
    """Compare observed replies and account for missing pairs separately."""
    observed, missing, critical_losses = 0, 0, 0
    delta = 0
    for case, left_score in left.items():
        right_score = right[case]
        if left_score is None or right_score is None:
            missing += 1
            continue
        observed += 1
        delta += left_score - right_score
        critical_losses += critical[case] and right_score and not left_score
    return Counter(pairedCases=observed, missingPairs=missing, passDelta=delta, criticalLosses=critical_losses)


def prepare(replay, source_plan, archive):
    _, base, _, data, run_gepa, cohorts, risk = strata.prepare(replay)
    old = parse(verified(ROOT / 'docs/recorded-promotion-strata-results-v1.json', witness.RESULT_SHA256))
    verified(ROOT / 'docs/recorded-outage-witness-results-v1.json', PRIOR_WITNESS_SHA256)
    (_, _, _, holdouts, _), _, incumbent, _ = data[TASK]
    source = parse(verified(source_plan, SOURCE_PLAN_SHA256))
    path = 'outage-strict-plan.json'
    independent = parse(verified(archive / path, source['taskSources'][TASK][path]))['datasets']['holdout']
    external_risk = {row['id']: strata.risk_stratum(TASK, row) for row in independent}
    reserve = reserve_cases(external_risk)
    reserved = [case for cases in reserve.values() for case in cases]
    external_critical = {row['id']: row['critical'] for row in independent if row['id'] not in reserved}
    if set(external_critical) & set(risk[TASK]) or any(panel.keys() != external_risk.keys() for panel in holdouts.values()):
        raise ValueError('Expected complete archived panels and a disjoint replay cohort')
    plan = {'protocol': 'cpo-recorded-outage-specialists-v1', 'task': TASK, 'gepaVersion': base['gepaVersion'],
            'baselineReportSha256': witness.RESULT_SHA256, 'witnessReportSha256': PRIOR_WITNESS_SHA256,
            'sourcePlanSha256': SOURCE_PLAN_SHA256, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'archivePoolSha256': digest(sorted(holdouts)), 'archiveCandidates': len(holdouts),
            'archivePool': 'All previously evaluated prompts with a complete original provider panel',
            'primary': ROUTE, 'modes': list(MODES), 'reserved': reserve, 'retainedProviderCases': len(external_critical),
            'retainedReplaySplits': len(cohorts[TASK]), 'targetStrata': TARGETS,
            'selection': 'A prompt must beat the incumbent by passing every reserved case in its assigned stratum',
            'accounting': 'Charge the same full shared reserve to every archive arm once per study'}
    return plan, base, old['results'][TASK], data[TASK], run_gepa, cohorts[TASK], risk[TASK], external_risk, external_critical


def run(plan, base, old, data, run_gepa, holdouts, risk, external_risk, external_critical):
    (_, rows, development, provider, _), _, incumbent, _ = data
    reserved = [case for cases in plan['reserved'].values() for case in cases]
    qualification = {prompt: {case: panel[case][0] for case in reserved} for prompt, panel in provider.items()}
    specialists = {TARGETS[name]: select_strict_winner(incumbent, qualification, cases)
                   for name, cases in plan['reserved'].items()}
    whole = select_strict_winner(incumbent, qualification, reserved)
    reserve_calls = len(qualification) * len(reserved)
    trials = []
    external_profiles = {mode: {} for mode in MODES}
    development_scores = {prompt: {case: score[0] for case, score in panel.items()} for prompt, panel in development.items()}
    provider_scores = {prompt: {case: panel[case][0] for case in external_critical} for prompt, panel in provider.items()}
    for index, held in enumerate(holdouts):
        seed = base['seedStart'] + index * base['seedStride']
        item, _, _ = witness.same_panel(data, held, seed, base, run_gepa, risk)
        records = {}
        for arm in METHODS:
            original = item['arms'][f'{arm}.{witness.BASELINE}']
            primary = original['chosen']
            for mode in MODES:
                scores = route_scores(held, risk, primary, specialists, whole, mode, development_scores)
                if any(passed is None for passed in scores.values()):
                    raise ValueError('A replay decision lacks a recorded case outcome')
                scoring = {**original, 'outcomes': scores, 'originalHoldout': {}}
                if mode != 'base' and index == 0:
                    scoring['calls'] += reserve_calls
                records[f'{arm}.{mode}'] = scoring
                if primary not in external_profiles[mode]:
                    external_profiles[mode][primary] = route_scores(external_critical, external_risk, primary,
                                                                  specialists, whole, mode, provider_scores)
        trials.append({'holdout': held, 'critical': item['critical'], 'arms': records})
    with patch.object(restart, 'PRIMARY', ROUTE):
        aggregate = restart.summarize(trials)
    aggregate.pop('trials')
    for arm in METHODS:
        expected = old['totals'][f'{arm}.{witness.BASELINE}']
        if not all(aggregate['totals'][f'{arm}.base'][key] == expected[key] for key in expected):
            raise ValueError('The source diverse-panel controls do not reproduce')
    pairs = {control: {(trial['arms']['cpo.base']['chosen'], trial['arms'][f'{control}.base']['chosen'])
                       for trial in trials} for control in METHODS[1:]}
    external_paired = {}
    for control, choices in pairs.items():
        external_paired[control] = {}
        for mode, profiles in external_profiles.items():
            counts = Counter(pairedCases=0, missingPairs=0, passDelta=0, criticalLosses=0)
            for left, right in choices:
                if left != right:
                    counts.update(compare_provider(profiles[left], profiles[right], external_critical))
            external_paired[control][mode] = counts
    retained = {}
    for name, target in TARGETS.items():
        selected = specialists[target]
        cases = [case for case in external_critical if external_risk[case] == target]
        retained[name] = {'cases': len(cases), 'incumbentPasses': sum(provider_scores[incumbent][case] for case in cases),
                          'specialistPasses': sum(provider_scores[selected][case] for case in cases) if selected else None}
    archive_only = None
    if whole is not None:
        archive_only = {'selectedPromptSha256': whole, 'reserveCalls': reserve_calls, 'searchCalls': 0,
                        'replayPasses': sum(development_scores[whole][case] for cases in holdouts for case in cases),
                        'retainedProviderPasses': sum(provider_scores[whole].values()),
                        'retainedProviderCases': len(external_critical)}
    return {'plan': plan, 'planSha256': digest(plan), 'promotionReserveCallsPerArchiveArm': reserve_calls,
            'incumbentOnReserve': {name: sum(qualification[incumbent][case] for case in cases)
                                   for name, cases in plan['reserved'].items()},
            'specialistsOnRetainedTargetCases': retained,
            'uniqueSelectedSpecialists': len({prompt for prompt in specialists.values() if prompt is not None}),
            'archiveOnly': archive_only, 'replay': aggregate, 'archivedProviderPairs': external_paired}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('replay', 'source-plan', 'archive'):
        parser.add_argument('--' + argument, type=Path, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    setup = prepare(args.replay, args.source_plan, args.archive)
    plan = setup[0]
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = run(*setup)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
