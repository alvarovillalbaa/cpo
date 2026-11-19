"""Reinvest paid incumbent validation replies in a tight CPO search cap."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import independent_mmlu_cost_frontier as frontier
from benchmarks import independent_mmlu_transfer as transfer
from benchmarks import low_budget_transfer as low
from cpo import Observation, Row
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
CAPS = (28, 36)
FIELDS = ('holdoutPasses', 'paidLookups')
SOURCES = {
    'development': ('independent-mmlu-transfer-v1.json', 'independent-mmlu-cost-frontier-results-v1.json',
                    '1038005684d3475e4cf05f593423f6e4e7e3c71058b006c16a0c82ba04938efa'),
    'replication': ('low-budget-transfer-v1.json', 'low-budget-transfer-results-v1.json',
                    '3e3f978892d9f60f9a04820612030e22b3341be0eed8df7caab6be0927e91163'),
}


def paid_search(known, incumbent, validation, evaluate, *, limit, credit):
    """Fund a logical cap with fresh calls and previously measured incumbent cases."""
    incumbent_credit = sum((incumbent, row.id) in known for row in validation) if credit else 0
    fresh = 0

    def measure(prompt, row):
        nonlocal fresh
        key = (prompt, row.id)
        if key not in known:
            if fresh >= limit:
                raise ValueError('Validation exceeded the remaining paid search cap')
            known[key] = evaluate(prompt, row)
            fresh += 1
        return known[key]

    return incumbent_credit, measure, lambda: fresh


def episode(matrix, held, seed, schedule, settings, *, credit):
    incumbent, layouts = archive.smaller.narrow_schedule(
        *archive.continuous.schedule(len(matrix[0]), len(matrix), held, seed, schedule), settings['validationRows'])
    totals = Counter(searchPaid=0, searchLogical=0, qualificationPaid=0, incumbentCredits=0, certificates=0,
                     archiveAttempts=0, archivePromotions=0, cyclesAboveLogicalCap=0)
    trace, history, attempted, known = [], [], set(), {}
    for layout in layouts:
        nominee = archive.archive.nominate(incumbent, history, attempted, 'runner-up')
        candidates, cohort = layout['alternatives'], layout['qualify']
        allowed_search = {incumbent, *candidates}
        allowed_qualification = allowed_search | {nominee}
        search, qualification, requested = {}, {}, []

        def qualify(prompt, case):
            if prompt not in allowed_qualification or case not in cohort:
                raise ValueError('Qualification left the sealed roster or panel')
            key = (prompt, case)
            if key not in qualification:
                qualification[key] = matrix[int(prompt)][case] == '1'
            return qualification[key]

        def qualify_fresh(prompt, row, repeat):
            passed = qualify(prompt, int(row.id))
            requested.append((prompt, row.id, repeat, passed))
            return passed

        def evaluate(prompt, row):
            passed = matrix[int(prompt)][int(row.id)] == '1'
            return Observation(passed, {'correct': passed})

        def observe(prompt, row):
            case = int(row.id)
            if prompt not in allowed_search or case not in layout['validation']:
                raise ValueError('Validation left the sealed roster or panel')
            reply = measure(prompt, row)
            search[prompt, case] = reply.passed
            return reply

        reserved = fresh = credit_count = 0
        certified = promoted = False
        if nominee is not None:
            attempted.add((incumbent, nominee))
            promoted, reserved, _ = archive.archive.qualify_archived(incumbent, nominee, cohort, qualify)
        limit = settings['searchCap'] - reserved
        if promoted:
            challenger = selected = nominee
        else:
            rows = [Row(str(case), 'task') for case in layout['validation']]
            qual_rows = [Row(str(case), 'task') for case in cohort]
            # Unread incumbent rows retire their matching logical slots. The
            # challenger reserve can therefore spend only funded fresh slots.
            credit_count, measure, paid = paid_search(known, incumbent, rows, evaluate, limit=limit, credit=credit)
            result = archive.run_fixed_pool_cycle(incumbent, candidates, rows, qual_rows, observe,
                                                  metric_limit=limit + credit_count,
                                                  qualify=qualify_fresh, seed=layout['seed'])
            fresh = paid()
            challenger, selected = result.search.prompt, result.prompt
            certified = challenger != incumbent
            if result.search.evaluations != len(search) or result.qualification_evaluations != len(requested):
                raise ValueError('Callback counts differ from the recorded evaluation journal')
        if fresh > limit or fresh + len(qualification) > settings['searchCap'] + 2 * len(cohort):
            raise ValueError('The original paid search or combined ceiling was exceeded')
        decision = {'incumbent': incumbent, 'challenger': challenger, 'selected': selected,
                    'archiveNominee': nominee, 'archivePromoted': promoted,
                    'searchSha256': digest([(p, case, passed) for (p, case), passed in search.items()])}
        trace.append({'decision': decision, 'observedQualification': requested, 'paidQualification': len(qualification)})
        history.append(decision)
        totals.update(searchPaid=fresh, searchLogical=len(search), qualificationPaid=len(qualification),
                      incumbentCredits=credit_count, certificates=int(certified), archiveAttempts=int(nominee is not None),
                      archivePromotions=int(promoted), cyclesAboveLogicalCap=int(len(search) > limit))
        incumbent = selected
    totals['holdoutPasses'] = sum(matrix[int(incumbent)][case] == '1' for case in held)
    return totals, trace


def prepare(phase):
    corpus_name, report_name, expected = SOURCES[phase]
    raw = (ROOT / 'docs' / report_name).read_bytes()
    corpus = (ROOT / 'benchmarks/data' / corpus_name).read_bytes()
    report = transfer.read_json(raw)
    data = transfer.read_json(corpus)['panels']
    if phase == 'development':
        source_plan, schedule, _, _, _, _ = frontier.prepare()
        validation_rows = source_plan['validationRows']
    else:
        source_plan = low.design()
        schedule = source_plan['schedule']
        validation_rows = source_plan['validationRows']
        with patch.object(transfer, 'EXPECTED', low.EXPECTED):
            transfer.check_corpus(transfer.read_json(corpus), source_plan)
    if (sha256(raw).hexdigest() != expected or report['planSha256'] != digest(source_plan)
            or sha256(corpus).hexdigest() != report.get('corpusSha256', source_plan.get('corpusSha256'))):
        raise ValueError('The archived scores, comparison report or source plan differ')
    plan = {
        'protocol': 'cpo-paid-incumbent-credit-v1', 'phase': phase, 'caps': list(CAPS),
        'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in (
            'benchmarks/paid_incumbent_credit.py', 'benchmarks/archive_complementarity_transfer.py',
            'cpo/fixed_pool_cycle.py', 'cpo/lazy_incumbent.py', 'cpo/challenger.py',
            'cpo/paired_qualification.py')},
        'referenceReportSha256': expected,
        'referencePlanSha256': digest(source_plan), 'corpusSha256': sha256(corpus).hexdigest(),
        'gepaVersion': source_plan['gepaVersion'], 'validationRows': validation_rows,
        'controls': ['retain-start', 'gepa-batched-39', 'gepa-batched-44'],
        'scope': ('Reinvest previously paid incumbent validation replies under the original paid cycle cap. '
                  'Keep the order, certificate, archive and independent qualification fixed. Compare with '
                  'archived official controls. Both cohorts are retrospective.'),
    }
    return plan, schedule, data, report['panels']


def measure(matrix, held, schedule, plan, cap, credit):
    costs, traces, scores = Counter(), [], []
    settings = {'searchCap': cap, 'validationRows': plan['validationRows']}
    for seed in schedule['seeds']:
        totals, trace = episode(matrix, held, seed, schedule, settings, credit=credit)
        costs.update(totals)
        traces.append(trace)
        scores.append(totals['holdoutPasses'])
    return dict(costs, paidLookups=costs['searchPaid'] + costs['qualificationPaid'], traceSha256=digest(traces)), scores


def replay(plan, schedule, data, archived):
    panels, totals = {}, {}
    for p in data:
        matrix = p['correctness']
        name = f"{p['subject']}/{p['model']}"
        past = archived[name]
        replication = plan['phase'] == 'replication'
        held = (past['holdoutCaseIDs'] if replication else schedule['holdoutCaseIDs'][p['subject']])
        if replication:
            controls = {key: past['methods'][key] for key in plan['controls']}
        else:
            reference = past['gepa'][transfer.gepa.METHODS[1]]
            controls = {'retain-start': {'holdoutPasses': past['retainStart'], 'paidLookups': 0},
                        **{f'gepa-batched-{cap}': reference[str(cap)] for cap in (39, 44)}}
        methods = {key: {k: point[k] for k in FIELDS} for key, point in controls.items()}
        changes = {}
        for cap in plan['caps']:
            base, base_scores = measure(matrix, held, schedule, plan, cap, False)
            if not replication or cap == 28:
                expected = past['methods'][f'cpo-{cap}'] if replication else past['cpo'][f'seeded-{cap}']
                frontier.expect_reference(base, expected)
            paid, paid_scores = measure(matrix, held, schedule, plan, cap, True)
            methods[f'seeded-{cap}'] = base
            methods[f'credited-{cap}'] = paid
            deltas = [after - before for before, after in zip(base_scores, paid_scores, strict=True)]
            changes[str(cap)] = {'episodesGaining': sum(delta > 0 for delta in deltas),
                                 'episodesLosing': sum(delta < 0 for delta in deltas),
                                 'grossGainedPasses': sum(max(delta, 0) for delta in deltas),
                                 'grossLostPasses': -sum(min(delta, 0) for delta in deltas)}
        panels[name] = {'methods': methods, 'changes': changes}
        for key, point in methods.items():
            totals.setdefault(key, Counter()).update({k: point[k] for k in (*FIELDS, 'certificates') if k in point})
    return {'plan': plan, 'planSha256': digest(plan), 'totals': totals, 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=SOURCES, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current phase seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
