"""Match realized cost on the archived routed-finalist model-transfer cohort."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import finalist_screen_budget as screen
from benchmarks import finalist_witness_rescue as rescue
from benchmarks import independent_mmlu_cost_frontier as frontier
from benchmarks import independent_mmlu_cost_uncertainty as uncertainty
from benchmarks import routed_finalist_model_transfer as transfer
from benchmarks import routed_witness_split as split
from benchmarks import starting_prompt_margin as margins
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
PHASE = 'model-transfer'
REPORTS = {
    'transfer': ('routed-finalist-model-transfer', 'c1eb91255cdfd0d124695f1d9710552bdb49ce54ad86db446e8af8984a3444a7'),
    'screen': ('finalist-screen-budget', '53e59a42802a935e859ae4ce417c28e7972b3364c2c3b5f9a87aa873e94ea8c2'),
    'rescue': ('finalist-witness-rescue', '38c45a8bc77aaa77deec7d53701ef0e5aa5886aa243efaad6a9a3f0d5d5e7413'),
    'split': ('routed-witness-split', '859091e953d3a0f81c8b375564f2c22acd68c87d6571906ef942683fec095e57'),
}
CAPS = frontier.CAPS
GEPA = uncertainty.MODES
AUDITED = ('wide-on-third-pass', 'wide-on-third-miss', 'routed-backup', 'always-wide-backup')
TARGET = 'wide-on-third-pass'
FIELDS = frontier.FIELDS


def prepare():
    parent, panels, _, _ = split.prepare(PHASE)
    sources = {}
    for label, (filename, expected) in REPORTS.items():
        raw = (ROOT / 'docs' / f'{filename}-results-v1.json').read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError(f'The archived {label} report differs from its published receipt')
        report = split.read_json(raw)
        sources[label] = report if label == 'transfer' else report[PHASE]
    if sources['split']['planSha256'] != digest(parent):
        raise ValueError('The split-witness source plan differs from its report')
    if min(CAPS) < parent['validationRows'] + parent['schedule']['qualificationRowsPerCycle']:
        raise ValueError('The GEPA sweep must fund incumbent validation after archive deductions')
    paths = ('benchmarks/routed_model_cost_frontier.py', 'benchmarks/independent_mmlu_cost_frontier.py',
             'benchmarks/independent_mmlu_cost_uncertainty.py', 'benchmarks/paid_budget_frontier.py',
             'benchmarks/gepa_paid_cap_transfer.py', 'benchmarks/starting_prompt_margin.py')
    plan = {**{k: parent[k] for k in ('schedule', 'searchCap', 'gepaVersion', 'validationRows')},
            'protocol': 'cpo-routed-model-cost-frontier-v1', 'parentPlanSha256': digest(parent),
            'reportSha256': {label: expected for label, (_, expected) in REPORTS.items()},
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'gepaCaps': CAPS, 'gepaMethods': GEPA,
            'cpoMethods': (*split.METHODS, 'seeded', 'always-wide-bounds', 'always-wide-backup', 'rescue-after-empty'),
            'bootstrapMethods': AUDITED, 'lossAuditCandidate': TARGET, 'bootstrapDraws': 4096,
            'bootstrapSeed': 20261124,
            'scope': ('Replay every integer GEPA cap under the matched roster, archive and qualification. '
                      'Measure realized search plus qualification cost. Compare with the best affordable fixed '
                      'GEPA point and the task-specific hindsight bound. Reselect the fixed point in each draw.')}
    return plan, panels, sources


def cpo_paths(method, matrix, held, plan):
    traces, finals, total = [], [], Counter()
    for seed in plan['schedule']['seeds']:
        if method == 'seeded':
            count, trace = transfer.race.run(matrix, held, seed, plan, 'seeded')
        elif method.startswith('always-wide-'):
            mode = 'try-backup' if method == 'always-wide-backup' else 'two-lazy-bounds'
            count, trace = screen.run(matrix, held, seed, plan, 'balanced-six', mode)
        elif method == 'rescue-after-empty':
            count, trace = rescue.run(matrix, held, seed, plan, 'late-empty')
        else:
            count, trace = split.run(matrix, held, seed, plan, method)
        total.update(count)
        traces.append(trace)
        finals.append(int(trace[-1]['decision']['selected']))
    point = {'holdoutPasses': total['holdoutPasses'], 'paidLookups': total['searchPaid'] + total['qualificationPaid'],
             'traceSha256': digest(traces)}
    return finals, point, traces


def retained_prompts(matrix, held, schedule):
    return [int(transfer.gepa.continuous.schedule(len(matrix[0]), len(matrix), held, seed, schedule)[0])
            for seed in schedule['seeds']]


def verify_transfer_gepa(points, reference):
    for method, short, additional in zip(GEPA, ('sequential', 'batched'), (31, 44), strict=True):
        for cap in (additional, 52):
            frontier.expect_reference(points[method][str(cap)], reference[f'gepa-{short}-{cap}'])


def measure_panel(plan, panel, references):
    matrix = panel['correctness']
    held = references['transfer']['holdoutCaseIDs']
    if transfer.holdout(panel['subject'], len(matrix[0])) != held:
        raise ValueError('The search and holdout cases differ from the published panel')
    schedule = plan['schedule']
    points, gepa, finals = {}, {}, {}
    for method in GEPA:
        measured = gepa[method] = {}
        for cap in CAPS:
            key = f'{method}/{cap}'
            finals[key], measured[str(cap)] = uncertainty.final_prompts(matrix, held, schedule, plan, method, cap)
    verify_transfer_gepa(gepa, references['transfer']['methods'])

    expected = {
        **references['split'],
        'seeded': references['transfer']['methods']['cpo-seeded'],
        'always-wide-backup': references['screen']['balanced-six']['modes']['try-backup'],
        'always-wide-bounds': references['screen']['balanced-six']['modes']['two-lazy-bounds'],
        'rescue-after-empty': references['rescue']['methods']['late-empty'],
    }
    target_trace = None
    for method in plan['cpoMethods']:
        finals[method], points[method], traces = cpo_paths(method, matrix, held, plan)
        frontier.expect_reference(points[method], expected[method])
        if method == TARGET:
            target_trace = traces
    finals['retain-start'] = retained_prompts(matrix, held, schedule)
    retain = references['transfer']['methods']['retain-start']['holdoutPasses']
    return held, {'gepa': gepa, 'cpo': points, 'retainStart': retain}, (finals, target_trace)


def audit_losses(matrix, held, schedule, validation_rows, traces, winners):
    by_reason = Counter()
    lost_passes = Counter()
    for seed, trace, winner in zip(schedule['seeds'], traces, winners, strict=True):
        selected = trace[-1]['decision']['selected']
        rival = str(winner)
        deficit = sum((matrix[winner][row] == '1') - (matrix[int(selected)][row] == '1') for row in held)
        if deficit <= 0:
            continue
        start, layouts = transfer.gepa.smaller.narrow_schedule(
            *transfer.gepa.continuous.schedule(len(matrix[0]), len(matrix), held, seed, schedule), validation_rows)
        decisions = [step['decision'] for step in trace]
        reason = margins.attribute_loss(matrix, held, (start, layouts, decisions, [None] * len(layouts)), rival)['reason']
        by_reason[reason] += 1
        lost_passes[reason] += deficit
    return {'episodes': by_reason, 'grossPassDeficit': lost_passes}


def paired_summary(plan, panels, measured, summary):
    totals = summary['gepaTotals']
    gepa_cost = {f'{method}/{cap}': row['paidLookups'] for method, caps in totals.items() for cap, row in caps.items()}
    cpo_cost = {m: summary['cpoTotals'][m]['paidLookups'] for m in AUDITED}
    matches = {}
    for method in AUDITED:
        point = summary['matchedCostComparisons'][method]['cheapestFixedGepaMatchingPasses']
        if point is None:
            raise ValueError('No GEPA setting reaches the audited score within the swept range')
        matches[method] = f"{point['method']}/{point['cap']}"
    affordable = {label: cost for label, cost in gepa_cost.items() if cost <= max(cpo_cost.values())}
    audit = {'cpoPaidLookups': cpo_cost, 'gepaPaidLookups': {**affordable, **{m: gepa_cost[m] for m in matches.values()}},
             'publishedScoreMatchedGepa': matches,
             **{k: plan[k] for k in ('bootstrapSeed', 'bootstrapDraws')}}
    labels = (*cpo_cost, *audit['gepaPaidLookups'], 'retain-start')
    best = summary['matchedCostComparisons'][TARGET]['bestFixedGepaWithinCost']
    controls = (f"{best['method']}/{best['cap']}", f'{GEPA[0]}/52')
    losses = {label: {'episodes': Counter(), 'grossPassDeficit': Counter()} for label in controls}
    subjects = {}
    for panel in panels:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held, current, (finals, trace) = measured[name]
        dest = subjects.setdefault(subject, {case: Counter() for case in held})
        if tuple(dest) != tuple(held):
            raise ValueError('Both model panels must share the same ordered holdout cases')
        for label in labels:
            values = uncertainty.case_totals(matrix, held, finals[label])
            if label in cpo_cost:
                expected = current['cpo'][label]['holdoutPasses']
            elif label == 'retain-start':
                expected = current['retainStart']
            else:
                method, cap = label.split('/')
                expected = current['gepa'][method][cap]['holdoutPasses']
            if sum(values.values()) != expected:
                raise ValueError('The paired holdout counts do not reproduce the trajectory totals')
            for case, count in values.items():
                dest[case][label] += count
        for control in controls:
            result = audit_losses(matrix, held, plan['schedule'], plan['validationRows'], trace, finals[control])
            for key, counts in result.items():
                losses[control][key].update(counts)
    cases = {subject: list(values.values()) for subject, values in subjects.items()}
    return uncertainty.summarize(audit, cases), losses


def replay(plan, panels, sources):
    measured = {}
    for panel in panels:
        name = f"{panel['subject']}/{panel['model']}"
        refs = {label: source['panels'][name] for label, source in sources.items()}
        measured[name] = measure_panel(plan, panel, refs)
    points = {name: point for name, (_, point, _) in measured.items()}
    summary = frontier.summarize(points)
    paired, losses = paired_summary(plan, panels, measured, summary)
    return {'plan': plan, 'planSha256': digest(plan), 'panels': points, **summary, 'pairedCaseSensitivity': paired,
            'lossAttribution': {TARGET: losses}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels, sources = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, panels, sources)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
