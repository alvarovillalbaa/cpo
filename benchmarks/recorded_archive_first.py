"""Qualify archived prompts before search on matched recorded case banks."""

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_archive_restart as restart, recorded_outage_specialists as specialists
from benchmarks import recorded_outage_witness as witness, recorded_promotion_strata as strata
from benchmarks.recorded_field_preservation import SOURCE_PLAN_SHA256, parse, verified
from cpo import Observation, Row
from cpo._contract import digest
from cpo.challenger import certify_challenger


ROOT = Path(__file__).resolve().parents[1]
ORIGINS = ('strict', 'fields', 'hybrid')
METHODS = witness.METHODS
MODES = ('base', 'archive-first', 'full-panel', 'without-fields', 'validation-first')
PRIMARY = 'cpo.archive-first'
SPECIALIST_RESULT_SHA256 = 'aa8283300df9376e0fe378e5bf199ff6297282845ad08fe4289f8b0ae8a6b0f3'


@dataclass(frozen=True)
class ArchiveCheck:
    selected: str | None
    evidence: dict[str, dict[str, bool]]
    retrieved: int

    @property
    def evaluations(self):
        return sum(len(values) for values in self.evidence.values())


def check_archive(incumbent, candidates, rows, evaluate, *, require_full=False):
    """Use only the current promotion rows and stop at the first qualifying archive prompt."""
    if not candidates:
        return ArchiveCheck(None, {}, 0)
    baseline = {row.id: evaluate(incumbent, row) for row in rows}
    evidence = {incumbent: baseline}
    if all(baseline.values()):
        return ArchiveCheck(None, evidence, 0)
    for order, prompt in enumerate(candidates, 1):
        result = certify_challenger(rows, baseline, lambda row: Observation(evaluate(prompt, row), {}),
                                    metric_limit=len(rows))
        evidence[prompt] = result.observations
        if result.status != 'promote':
            continue
        if require_full:
            if not all(result.observations.values()):
                continue
            for row in rows:
                if row.id not in result.observations:
                    result.observations[row.id] = evaluate(prompt, row)
                    if not result.observations[row.id]:
                        break
            if not all(result.observations.values()):
                continue
        return ArchiveCheck(prompt, evidence, order)
    return ArchiveCheck(None, evidence, len(candidates))


def account_fallback(incumbent, rows, check, baseline):
    """Charge the union of observed pairs while preserving the original search and promotion."""
    if not baseline['qualificationEvaluations']:
        return baseline['qualificationEvaluations'] + check.evaluations
    challenger = baseline['challenger']
    reused = len(check.evidence.get(incumbent, {}).keys() & {row.id for row in rows})
    reused += len(check.evidence.get(challenger, {}).keys() & baseline['qualification'].keys())
    return baseline['qualificationEvaluations'] + check.evaluations - reused


def prepare(replay, source_plan, archive):
    _, frozen, _, data, run_gepa, cohorts, risk = strata.prepare(replay)
    old = parse(verified(ROOT / 'docs/recorded-promotion-strata-results-v1.json', witness.RESULT_SHA256))
    verified(ROOT / 'docs/recorded-outage-specialists-results-v1.json', SPECIALIST_RESULT_SHA256)
    source = parse(verified(source_plan, SOURCE_PLAN_SHA256))
    pool_by_origin, external = {}, {}
    for task, dataset in sorted(data.items()):
        (_, rows, matrix, provider, _), graph, incumbent, _ = dataset
        root = dataset[0][0]
        reachable = restart.reachable(graph, root)
        pools = {}
        for origin in ORIGINS:
            file = f'{task}-{origin}/results.json'
            result = parse(verified(archive / file, source['taskSources'][task][file]))
            prompt = result['holdoutCandidate']['promptSha256']
            if prompt not in matrix or prompt not in provider or prompt not in reachable:
                raise ValueError('A historical finalist is outside the verified replay graph or archive')
            pools[origin] = prompt
        pool_by_origin[task] = {name: list(dict.fromkeys(pools[origin] for origin in ORIGINS
                                                        if origin in allowed and pools[origin] != incumbent))
                                for name, allowed in [('all', ORIGINS), ('without-fields', ('strict', 'hybrid'))]}
        file = f'{task}-strict-plan.json'
        cases = parse(verified(archive / file, source['taskSources'][task][file]))['datasets']['holdout']
        critical = {row['id']: row['critical'] for row in cases}
        if set(critical) & set(rows) or any(panel.keys() != critical.keys() for panel in provider.values()):
            raise ValueError('Original provider cases are incomplete or overlap the replay cohort')
        external[task] = critical
    plan = {'protocol': 'cpo-recorded-archive-first-v1', 'modes': list(MODES), 'primary': PRIMARY,
            'sourcePlanSha256': SOURCE_PLAN_SHA256, 'baseReportSha256': witness.RESULT_SHA256,
            'specialistReportSha256': SPECIALIST_RESULT_SHA256, 'archivePoolSha256': digest(pool_by_origin),
            'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'gepaVersion': frozen['gepaVersion'],
            'proposalOrder': list(ORIGINS), 'pool': 'Verified historical finalists in source order',
            'gate': 'Strict matched gain and preserve incumbent critical passes. Full-panel also requires all cases to pass.',
            'validationFirst': 'Skip archive retrieval after a perfect incumbent validation; otherwise apply the archive-first gate.',
            'accounting': 'Deduct all archive lookups from fallback budgets before search. Charge repeated paired outcomes once.'}
    return plan, frozen, old['results'], data, run_gepa, cohorts, risk, pool_by_origin, external


def recorded_decision(original, selected, check, qualification, matrix, held, paid_validation):
    if check.selected is not None:
        search, slots, status = paid_validation, 0, 'promote'
    else:
        search, slots, status = original['searchEvaluations'], original['proposalSlots'], original['promotion']
    archive = (original['archiveLookups'] if check.selected is None else 0) + check.retrieved
    return {'chosen': selected, 'outcomes': {case: matrix[selected][case][0] for case in held},
            'searchEvaluations': search, 'proposalSlots': slots + check.retrieved, 'archiveLookups': archive,
            'qualificationEvaluations': qualification, 'promotion': status,
            'calls': search + slots + check.retrieved + qualification, 'originalHoldout': {}}


def replay_task(frozen, old, data, run_gepa, holdouts, risk, pools, external):
    (_, metadata, matrix, provider, _), _, incumbent, _ = data
    trials, skips = [], Counter({mode: 0 for mode in MODES[1:]})
    for index, held in enumerate(holdouts):
        seed = frozen['seedStart'] + index * frozen['seedStride']
        trial, validation, promotion = witness.same_panel(data, held, seed, frozen, run_gepa, risk)
        rows = tuple(Row(case, 'task', metadata[case]['critical']) for case in promotion)

        def evaluate(prompt, row):
            return matrix[prompt][row.id][0]

        checks = {'base': ArchiveCheck(None, {}, 0),
                  'archive-first': check_archive(incumbent, pools['all'], rows, evaluate),
                  'full-panel': check_archive(incumbent, pools['all'], rows, evaluate, require_full=True),
                  'without-fields': check_archive(incumbent, pools['without-fields'], rows, evaluate)}
        perfect = all(matrix[incumbent][case][0] for case in validation)
        if perfect and any(trial['arms'][f'{arm}.{witness.BASELINE}']['calls'] != len(validation) or
                           trial['arms'][f'{arm}.{witness.BASELINE}']['chosen'] != incumbent for arm in METHODS):
            raise ValueError('The perfect validation shortcut must match the observed search exits')
        checks['validation-first'] = checks['base'] if perfect else checks['archive-first']
        records, fallback_cache = {}, {(0, 0): trial}
        for mode, check in checks.items():
            if mode != 'base':
                skips[mode] += check.selected is not None
            fallback = trial
            if check.selected is None:
                spent = check.retrieved, check.evaluations
                if spent not in fallback_cache:
                    remaining = {**frozen, 'proposalSlots': frozen['proposalSlots'] - check.retrieved,
                                 'metricLimit': frozen['metricLimit'] - check.evaluations}
                    with patch.dict(run_gepa.__globals__, {'PROPOSAL_LIMIT': remaining['proposalSlots'],
                                                           'METRIC_LIMIT': remaining['metricLimit']}):
                        fallback_cache[spent] = witness.same_panel(data, held, seed, remaining, run_gepa, risk)[0]
                fallback = fallback_cache[spent]
            for arm in METHODS:
                original = fallback['arms'][f'{arm}.{witness.BASELINE}']
                selected = check.selected or original['chosen']
                qualification = (check.evaluations if check.selected is not None else
                                 account_fallback(incumbent, rows, check, original))
                paid_validation = len(validation) if mode == 'validation-first' else 0
                decision = recorded_decision(original, selected, check, qualification, matrix, held, paid_validation)
                if (decision['searchEvaluations'] + decision['qualificationEvaluations'] > frozen['metricLimit'] + 6 or
                        decision['proposalSlots'] > frozen['proposalSlots']):
                    raise ValueError('The recorded archive policy exceeded the original combined allowance')
                records[f'{arm}.{mode}'] = decision
        trials.append({'holdout': held, 'critical': trial['critical'], 'arms': records})
    with patch.object(restart, 'PRIMARY', PRIMARY):
        aggregate = restart.summarize(trials)
    aggregate.pop('trials')
    with patch.object(restart, 'PRIMARY', 'cpo.validation-first'):
        validation_comparisons = restart.summarize(trials)['comparisons']
    aggregate['validationFirstComparisons'] = {arm: validation_comparisons[arm] for arm in
                                               ('cpo.base', 'cpo.archive-first', 'gepa-sequential.validation-first',
                                                'gepa-batched.validation-first')}
    for arm in METHODS:
        if aggregate['totals'][f'{arm}.base'] != old['totals'][f'{arm}.{witness.BASELINE}']:
            raise ValueError('The source diverse-panel totals did not reproduce')
    provider_scores = {prompt: {case: score[0] for case, score in values.items()} for prompt, values in provider.items()}
    aggregate['originalProviderComparisons'] = {}
    for comparator in ('cpo.base', 'cpo.full-panel', 'cpo.without-fields', 'cpo.validation-first', 'gepa-sequential.archive-first',
                       'gepa-batched.archive-first'):
        pairs = {(trial['arms'][PRIMARY]['chosen'], trial['arms'][comparator]['chosen']) for trial in trials}
        counts = Counter(differentPromptPairs=0, pairedCases=0, missingPairs=0, passDelta=0, criticalLosses=0)
        unobserved = dict.fromkeys(external)
        for left, right in pairs:
            if left != right:
                counts['differentPromptPairs'] += 1
                counts.update(specialists.compare_provider(provider_scores.get(left, unobserved),
                                                           provider_scores.get(right, unobserved), external))
        aggregate['originalProviderComparisons'][comparator] = counts
    aggregate['searchesSkipped'] = skips
    aggregate['poolSizes'] = {name: len(values) for name, values in pools.items()}
    return aggregate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('replay', 'source-plan', 'archive'):
        parser.add_argument('--' + arg, required=True, type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, frozen, old, inputs, run_gepa, cohorts, risk, pools, external = prepare(args.replay, args.source_plan, args.archive)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    results = {task: replay_task(frozen, old[task], inputs[task], run_gepa, cohorts[task], risk[task], pools[task],
                                 external[task]) for task in sorted(inputs)}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
