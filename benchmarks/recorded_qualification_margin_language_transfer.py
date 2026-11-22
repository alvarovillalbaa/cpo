"""Transfer the frozen two-gain qualification screen to archived BBH and LMentry."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_matched_qualification_margin as matched
from cpo._contract import digest


prior, cost, frontier = matched.prior, matched.cost, matched.frontier
ROOT = prior.transfer.ROOT
ARCHIVE = 'benchmarks/data/qualification-order-transfer-v3.json'
ARCHIVE_SHA256 = 'dae40ce166fabd49e8e3559db5a342a4047455c023d32dfe8c0efe2ea80bd326'
PARENT_REPORT = 'docs/recorded-matched-qualification-margin-results-v1.json'
PARENT_SHA256 = '6841281aef1b1ef533e6c9f424e681aa3fce33dbfcad35943af33ca0292f6cfd'
COHORTS = ('BBH', 'LMentry')
BASELINE, CANDIDATE = prior.BASELINE, prior.CANDIDATE
ARMS = (BASELINE, CANDIDATE)


def load_panels(entries):
    aligned, panels = {}, {cohort: [] for cohort in COHORTS}
    for entry in entries:
        cohort, subject, model, matrix = (entry[key] for key in ('benchmark', 'subject', 'model', 'correctness'))
        cases = tuple(entry['caseIDs'])
        templates = tuple(digest(identity) for identity in entry['templateIDs'])
        if (cohort not in panels or len(cases) < 30 or len(set(cases)) != len(cases)
                or len(templates) != 100 or len(set(templates)) != len(templates) or len(matrix) != len(templates)
                or any(len(row) != len(cases) or set(row) - {'0', '1'} for row in matrix)):
            raise ValueError('Each target panel must preserve the original case and template axes')
        axes, models = aligned.setdefault((cohort, subject), ((cases, templates), set()))
        if axes != (cases, templates) or model in models:
            raise ValueError('Both model panels must align in case and template order')
        models.add(model)
        panels[cohort].append((subject, model, matrix))
    if any(len(models) != 2 for _, models in aligned.values()) or not all(panels.values()):
        raise ValueError('Every task must have both model panels')
    return panels


def prepare():
    source, *_ = matched.prepare()
    cost.prior.baseline.read_reference(PARENT_REPORT, PARENT_SHA256, source)
    data = (ROOT / ARCHIVE).read_bytes()
    if sha256(data).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Use the exact published language correctness snapshot')
    panels = load_panels(json.loads(data)['panels'])
    paths = (Path(__file__), Path(matched.__file__), Path(prior.__file__), Path(cost.__file__))
    plan = {**{key: source[key] for key in ('caseCounts', 'seeds', 'challengers', 'searchCap',
                                          'minimumSearchCap', 'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-qualification-margin-language-transfer-v1',
            'parentPlanSha256': digest(source), 'parentReceiptSha256': PARENT_SHA256,
            'archiveSha256': ARCHIVE_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'enrolledPanels': {cohort: [panel[:2] for panel in group] for cohort, group in panels.items()},
            'screenCap': prior.transfer.CAP, 'candidate': CANDIDATE, 'baseline': BASELINE,
            'gate': 'positive observed margin and nonnegative paired lower endpoint against the strongest '
                    'affordable native GEPA setting with either proof rule or retained starts',
            'scope': 'Transfer the complete-panel-reserve screen with one- and two-gain qualification to both '
                     'archived language families. Freeze the MMLU schedule and qualification settings before '
                     'running the language panels. Match realized search and qualification costs to both '
                     'native GEPA modes for every cap and qualification rule. Resample paired cases and '
                     'report the two archived families separately, along with the paired qualification effect.'}
    return plan, panels


def measure_panel(subject, matrix, plan):
    cells = {str(index): tuple((int(passed), None, False) for passed in row) for index, row in enumerate(matrix)}
    totals, vectors, events = {}, {}, Counter()
    native, traces = {mode: Counter() for mode in cost.MODES}, {mode: [] for mode in cost.MODES}
    for seed in plan['seeds']:
        start, roster, cohorts = prior.transfer.fixed.archive.transfer.schedule(
            subject, len(matrix[0]), len(matrix), seed, plan)
        args = cells, start, roster, cohorts, seed
        old, before, old_scores, _ = prior.early.trial(args, 'complete-panel', plan['screenCap'])
        with patch.object(prior.adapter, 'qualify_with_prefix', prior.minimum_two):
            new, after, new_scores, _ = prior.early.trial(args, 'complete-panel', plan['screenCap'])
        if before[:3] != after[:3] or old['searchLookups'] != new['searchLookups']:
            raise ValueError('The threshold must keep the screen and nominee')
        nominee = after[2]
        gain = sum(cells[nominee][case][0] - cells[start][case][0] for case in cohorts[2])
        if before[3] != (nominee if gain >= 1 else start):
            raise ValueError('The original candidate must qualify with one gain')
        if after[3] != (nominee if gain >= 2 else start):
            raise ValueError('The stricter rule must qualify with exactly the stated minimum')
        retain = tuple(cells[start][case][0] for case in cohorts[-1])
        observed = {BASELINE: (old, old_scores), CANDIDATE: (new, new_scores),
                    frontier.RETAIN: ({'holdoutPasses': sum(retain), 'paidLookups': 0}, retain)}
        for label, (point, grades) in observed.items():
            totals.setdefault(label, Counter()).update({metric: point[metric] for metric in cost.METRICS})
            prior.transfer.fixed.fitted.prior.add_vector(vectors.setdefault(label, [0] * len(grades)), grades)
        diff = new['holdoutPasses'] - old['holdoutPasses']
        events.update(trials=1, oldPromotions=int(before[3] != start), newPromotions=int(after[3] != start),
                      proofLookupsSaved=old['qualificationLookups'] - new['qualificationLookups'],
                      gainsFromVeto=max(0, diff), lossesFromVeto=max(0, -diff))
        for mode in cost.MODES:
            point, trace, _ = cost.run(args, mode, plan['searchCap'])
            native[mode].update(point)
            traces[mode].append(trace)
    anchor = {mode: {**counts, 'traceSha256': digest(traces[mode])} for mode, counts in native.items()}
    gepa, grades, checked = matched.measure_native(subject, matrix, plan, anchor)
    return {**totals, **gepa}, {**vectors, **grades}, events, checked


def paired_effect(subjects, plan):
    changes = [[after - before for before, after in zip(rows[BASELINE], rows[CANDIDATE], strict=True)]
               for _, rows in sorted(subjects.items())]
    rng = Random(plan['bootstrapSeed'])
    draws = [sum(sum(rng.choices(values, k=len(values))) for values in changes)
             for _ in range(plan['bootstrapDraws'])]
    return {'passDifference': sum(map(sum, changes)), 'pairedRange95': frontier.interval(draws)}


def replay_cohort(panels, plan):
    totals, subjects, details = {}, {}, {}
    diagnostics = Counter()
    checked = 0
    for subject, model, matrix in panels:
        points, vectors, events, count = measure_panel(subject, matrix, plan)
        grades = subjects.setdefault(subject, {})
        for label, point in points.items():
            totals.setdefault(label, Counter()).update(point)
            row = vectors[label]
            prior.transfer.fixed.fitted.prior.add_vector(grades.setdefault(label, [0] * len(row)), row)
        diagnostics.update(events)
        checked += count
        details[f'{subject}/{model}'] = {'events': events, 'screenPoints': {label: points[label] for label in ARMS}}
    if any(sum(sum(rows[label]) for rows in subjects.values()) != point['holdoutPasses'] for label, point in totals.items()):
        raise ValueError('Every setting must match its paired case totals')
    native = tuple(label for label in totals if label not in (*ARMS, frontier.RETAIN))
    comparison = frontier.compare(totals, subjects, policies=ARMS, draws=plan['bootstrapDraws'],
                                  seed=plan['bootstrapSeed'], groups={'either-native-proof': native})
    results = {label: row['either-native-proof'] for label, row in comparison.items()}
    gates = {label: row['holdoutPassDifference'] > 0 and row['pairedRange95'][0] >= 0
             for label, row in results.items()}
    return {'totals': totals, 'comparison': results, 'passedArchiveGate': gates,
            'marginEffect': paired_effect(subjects, plan), 'events': diagnostics, 'panels': details,
            'nativeSearchPathsChecked': checked, 'caseVectorsSha256': digest(subjects)}


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
    results = {cohort: replay_cohort(group, plan) for cohort, group in panels.items()}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
