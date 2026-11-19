"""Compare global edits with training-witnessed conditional component edits."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import component_dependencies as prior, component_merge as fixture, component_risk_coverage as risk
from benchmarks.component_dependencies import next_edit as global_edit, score as score_global
from cpo._contract import digest
from cpo.evidence import can_reuse_component_feedback


SEEDS = tuple(range(67201, 67809, 19))
PANELS = ('original', 'six-critical')
POLICIES = ('global', 'conditional')
METHODS = ('cpo-dependencies', 'gepa-dependencies', 'gepa-dependencies-merge')
ARMS = tuple(f'{method}.{policy}' for policy in POLICIES for method in METHODS)
PRIMARY = 'cpo-dependencies.conditional'
REFERENCE = 'gepa-dependencies.global'


def branches(value):
    if value.startswith('scope:'):
        fallback, interaction = value.removeprefix('scope:').split(':')
        return fallback, interaction
    return value, value


def edit_branch(old, interaction, replacement):
    values = list(branches(old))
    values[int(interaction)] = replacement
    fallback, scoped = values
    return fallback if fallback == scoped else f'scope:{fallback}:{scoped}'


def score(program, row, profile):
    effective = {component: branches(value)[int(row['interaction'])] for component, value in program.items()}
    return score_global(effective, row, profile)


def panels(profile, seed):
    source = risk.make_panels(profile, seed)
    return {panel: {split: [{**row, 'interaction': len(row['needs']) > 1} for row in rows]
                    for split, rows in source[panel].items()} for panel in PANELS}


def shifted_labels(rows, seed):
    changed = set(Random(seed ^ 0xC090).sample(sorted(row['id'] for row in rows), len(rows) // 5))
    return [{**row, 'interaction': not row['interaction']} if row['id'] in changed else row for row in rows]


def conditional_edit(parent, journal, training, seen, mode, audit):
    candidate = global_edit(parent, journal, training, seen, mode, audit)
    if candidate == parent:
        return candidate
    component, = (name for name in parent if candidate[name] != parent[name])
    replacement = candidate[component]
    contexts = set()
    for (encoded_source, case), observation in journal.items():
        if case not in training:
            continue
        source = json.loads(encoded_source)
        if any(diagnosis.component == component and diagnosis.replacement == replacement
               and can_reuse_component_feedback(source, parent, component, dependencies=diagnosis.declared)
               for diagnosis in observation.feedback['diagnostics']):
            contexts.add(training[case]['interaction'])

    fallback, active = branches(parent[component])
    local_broadening = replacement == 'broad' and contexts == {True}
    preserve_interaction = replacement == 'guarded' and contexts == {False} and active == 'broad'
    if local_broadening or preserve_interaction:
        scoped = edit_branch(parent[component], local_broadening, replacement)
        if branches(scoped) != (fallback, active):
            conditional = {**parent, component: scoped}
            edge = fixture.encode(parent), fixture.encode(conditional)
            if edge not in seen:
                seen.add(edge)
                return conditional
    return candidate


def expressivity_ceiling(profile, holdout, reference):
    """After selection, bound exact gains at the reference's critical coverage."""
    protected = {row['id'] for row in holdout if row['critical'] and reference[row['id']]}
    interactive = {row['id'] for row in holdout if row['interaction']}
    ordinary = {row['id'] for row in holdout} - interactive
    ceiling = outside = inside = 0
    for program in risk.PROGRAMS:
        passed = {row['id'] for row in holdout if score_global(program, row, profile).passed}
        if protected <= passed:
            ceiling = max(ceiling, len(passed))
        if (protected & ordinary) <= passed:
            outside = max(outside, len(passed & ordinary))
        if (protected & interactive) <= passed:
            inside = max(inside, len(passed & interactive))
    baseline = sum(reference.values())
    return {'global': ceiling - baseline, 'conditional': outside + inside - baseline}


def compare(groups, profile, seed, cap):
    arms = {}
    shifted = shifted_labels(groups['holdout'], seed)
    for policy, proposer in (('global', global_edit), ('conditional', conditional_edit)):
        with patch.object(prior, 'ARMS', METHODS), patch.object(prior, 'cases', return_value=groups), \
                patch.object(prior, 'score', score), patch.object(prior, 'next_edit', proposer):
            trial = prior.compare(profile, seed, cap)
        for arm, record in trial['arms'].items():
            selected = json.loads(record['chosen']) if record['chosen'] is not None else None
            result = ({row['id']: score(selected, row, profile).passed for row in shifted}
                      if selected is not None else None)
            arms[f'{arm}.{policy}'] = {**record, 'shiftedOutcomes': result,
                                       'usesConditional': selected is not None and any(
                                           value.startswith('scope:') for value in selected.values())}
    reference = arms[REFERENCE]['outcomes']
    ceiling = {label: expressivity_ceiling(profile, cohort, reference)
               for label, cohort in (('clean', groups['holdout']), ('shifted', shifted))}
    return {**trial, 'arms': arms, 'expressivityCeiling': ceiling}


def summarize(trials):
    shifted = [{**trial, 'arms': {arm: {**record, 'outcomes': record['shiftedOutcomes']}
                                for arm, record in trial['arms'].items()}} for trial in trials]
    with patch.object(prior, 'ARMS', ARMS), patch.object(prior, 'PRIMARY', PRIMARY):
        clean = prior.summarize(trials)
        transfer = prior.summarize(shifted)
    representation = {}
    for name in ('clean', 'shifted'):
        bounds = [trial['expressivityCeiling'][name] for trial in trials]
        representation[name] = {'additionalOpportunity': sum(b['conditional'] - b['global'] for b in bounds),
                                'tiesUnlocked': sum(b['global'] == 0 < b['conditional'] for b in bounds)}
    return {'clean': clean, 'shifted': transfer, 'expressivityCeiling': representation,
            'selectedConditional': {arm: sum(trial['arms'][arm]['usesConditional'] for trial in trials) for arm in ARMS},
            'trials': trials}


def prepare():
    plan = risk.prepare()
    path = Path(__file__)
    plan['sourceSha256']['benchmarks/component_conditional_edits.py'] = sha256(path.read_bytes()).hexdigest()
    return {**plan, 'protocol': 'cpo-component-conditional-edits-v1', 'seeds': list(SEEDS), 'arms': list(ARMS),
            'primary': PRIMARY, 'panels': list(PANELS), 'heldOutLabelShift': 'flip one fifth, rounded down, after selection',
            'cohortDigests': {profile: digest([panels(profile, seed) for seed in SEEDS]) for profile in prior.PROFILES}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    results = {}
    for cap in plan['caps']:
        results[str(cap)] = {}
        for profile in plan['profiles']:
            cohorts = [(seed, panels(profile, seed)) for seed in plan['seeds']]
            results[str(cap)][profile] = {
                panel: summarize([compare(groups[panel], profile, seed, cap) for seed, groups in cohorts])
                for panel in plan['panels']}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
