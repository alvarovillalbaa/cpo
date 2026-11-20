"""Attribute the archived holdout gap between cap-72 CPO and batched GEPA."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import expected_cost_proposal_replay as source
from benchmarks.case_difficulty_allocation import checked_file
from cpo import expected_cost_proposal_cycle as cycle
from cpo._contract import digest


REFERENCE = 'a340fc3fc1ea6757a691ad594a54a13f500adf2d22328db65707e48b9c1289e5'
CPO = 'cpo-72'
GEPA = 'gepa-batched'


def record_search(offered):
    search = cycle.search

    def traced(initial, train, validation, evaluate, propose, *, opening_pair, **options):
        offered.update((opening_pair.rewrite, opening_pair.repair))

        def record(*args):
            batch = propose(*args)
            offered.update(batch.prompts)
            return batch

        return search(initial, train, validation, evaluate, record, opening_pair=opening_pair, **options)

    return traced


def classify(matrix, layout, minimum_gain, incumbent, cpo, gepa, offered):
    target = gepa['selected']
    if cpo.prompt == target:
        return 'same-deployment'
    if target == gepa['incumbent']:
        return 'gepa-kept-incumbent'
    if target == incumbent:
        return 'cpo-left-gepa-target'
    if target not in layout['alternatives']:
        raise ValueError('GEPA deployed outside the current proposal block')

    def grade(prompt, rows):
        return sum(matrix[int(prompt)][case] == '1' for case in rows)

    if grade(target, layout['qualify']) - grade(incumbent, layout['qualify']) < minimum_gain:
        return 'fails-cpo-pair-qualification'
    if target == cpo.search.prompt:
        raise ValueError('The same nominee passed the exact qualification without deploying')
    gain = grade(target, layout['validation']) - grade(incumbent, layout['validation'])
    if gain < 0:
        return 'below-cpo-incumbent-validation'
    if gain == 0:
        return 'ties-cpo-incumbent-validation'
    event = next((event['kind'] for event in cpo.search.events if event['prompt'] == target), None)
    if event not in (None, 'validated', 'budget', 'dominated'):
        raise ValueError(f'Unexpected PromptEval search outcome {event}')
    if event is not None:
        return f'strict-gain-{event}'
    return 'strict-gain-offered-unopened' if target in offered else 'strict-gain-unoffered'


def add(bucket, delta, same_incumbent):
    bucket.update(cycles=1, positivePassDelta=max(0, delta), negativePassDelta=min(0, delta),
                  netPassDelta=delta, sharedIncumbentCycles=int(same_incumbent),
                  sharedIncumbentPassDelta=delta if same_incumbent else 0)


def audit_panel(matrix, held, plan, previous, *, search_cap):
    cpo_plan = {**plan, 'evaluationLookupLimit': search_cap}
    cpo_paths, gepa_paths = [], []
    buckets = defaultdict(Counter)
    totals = Counter()

    def held_score(prompt):
        return sum(matrix[int(prompt)][row] == '1' for row in held)

    for seed in plan['seeds']:
        start, layouts = source.continuous.schedule(len(matrix[0]), len(matrix), held, seed, plan)
        cpo_incumbent = gepa_incumbent = start
        cpo_trace, gepa_trace = [], []
        for layout in layouts:
            offered = set()
            with patch.object(cycle, 'search', record_search(offered)):
                result, _, search_hash = source.archive_step(matrix, cpo_incumbent, layout, cpo_plan)
            gepa = source.continuous.step(GEPA, matrix, gepa_incumbent, layout, plan)
            replies = () if result.qualification is None else result.qualification.observations
            cpo_trace.append((cpo_incumbent, result.search.prompt, result.prompt, search_hash,
                              [(item.prompt, item.row_id, item.repeat, item.passed) for item in replies]))
            gepa_trace.append(gepa)

            delta = (held_score(gepa['selected']) - held_score(gepa_incumbent)
                     - held_score(result.prompt) + held_score(cpo_incumbent))
            category = classify(matrix, layout, plan['minimumQualificationGain'], cpo_incumbent, result, gepa, offered)
            add(buckets[category], delta, cpo_incumbent == gepa_incumbent)
            totals.update(cpoSearchLookups=result.search.evaluations, cpoQualificationLookups=len(replies),
                          gepaSearchLookups=gepa['searchLookups'], gepaQualificationLookups=gepa['qualificationLookups'])
            cpo_incumbent, gepa_incumbent = result.prompt, gepa['selected']
        totals.update(cpoHoldoutPasses=held_score(cpo_incumbent), gepaHoldoutPasses=held_score(gepa_incumbent))
        cpo_paths.append(cpo_trace)
        gepa_paths.append(gepa_trace)

    checks = ((CPO, cpo_paths, 'cpo', 'expected'), (GEPA, gepa_paths, 'gepa', 'qualificationLookups'))
    for label, paths, prefix, qualification_key in checks:
        point = previous[label]
        if (digest(paths), totals[f'{prefix}HoldoutPasses'], totals[f'{prefix}SearchLookups'],
                totals[f'{prefix}QualificationLookups']) != (
                point['traceSha256'], point['holdoutPasses'], point['searchLookups'], point[qualification_key]):
            raise ValueError(f'{label} changed a published trace, score or lookup total')
    if (sum(item['netPassDelta'] for item in buckets.values())
            != totals['gepaHoldoutPasses'] - totals['cpoHoldoutPasses']):
        raise ValueError('Cycle changes did not sum to the final holdout gap')
    return {'totals': dict(totals), 'categories': dict(buckets),
            'traceSha256': {label: digest(paths) for label, paths, _, _ in checks}}


def prepare():
    design, phases = source.prepare()
    reference = checked_file('docs/expected-cost-proposal-replay-results-v1.json', REFERENCE)
    if digest(design) != reference['designSha256']:
        raise ValueError('Published proposal replay design changed')
    return {'protocol': 'cpo-proposal-gap-audit-v1', 'referenceReportSha256': REFERENCE,
            'searchCap': 72, 'control': GEPA, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': ('Classify the published batched GEPA deployments against cap-72 CPO on each cycle. '
                      'Grade unused archive cells only for attribution after search and qualification.')}, phases, reference


def replay(phases, reference, search_cap):
    results = {}
    for phase, (plan, panels, _) in phases.items():
        published = reference['results'][phase]['panels']
        categories, totals, rows = defaultdict(Counter), Counter(), {}
        for panel in panels:
            subject = panel['subject']
            key = f"{subject}/{panel['model']}"
            point = audit_panel(panel['correctness'], plan['holdoutCaseIDs'][subject], plan, published[key],
                                search_cap=search_cap)
            rows[key] = point
            totals.update(point['totals'])
            for category, counts in point['categories'].items():
                categories[category].update(counts)
        results[phase] = {'panels': rows, 'totals': dict(totals), 'categories': dict(categories)}
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, phases, reference = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for plan, *_ in phases.values()):
        cli.error('Use pinned GEPA 0.1.4')
    report = {'design': design, 'designSha256': seal, 'results': replay(phases, reference, design['searchCap'])}
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
