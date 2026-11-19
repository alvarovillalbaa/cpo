"""Audit missed GEPA winners and test a stronger gate for leaving the starting prompt."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_after_fresh_search as fresh
from benchmarks import archive_complementarity_transfer as archive
from benchmarks import independent_mmlu_transfer as independent
from benchmarks.prompteval_paid_witness import meets_gate
from cpo._contract import digest
from cpo.fixed_pool_cycle import run_fixed_pool_cycle


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'benchmarks/data/independent-mmlu-transfer-v1.json'
INDEPENDENT_REPORT = ROOT / 'docs/independent-mmlu-transfer-results-v1.json'
INDEPENDENT_SHA256 = '11e88e6eaacd7a03ee503e1e0a9389b5d1a76c24d6ee5b511b7d47ee1c45a51a'
PHASES = ('independent', *archive.controls.reference.transfer.SOURCES)
POLICIES = {'seeded': (1, 1), 'start-gain-two': (2, 1), 'start-gain-three': (3, 1), 'all-gain-two': (2, 2)}
BATCHED = independent.gepa.METHODS[1]
BASELINE_FIELDS = ('holdoutPasses', 'searchLogical', 'searchPaid', 'qualificationPaid', 'paidLookups')
preflight = archive.archive.qualify_archived


def qualify_archive_margin(incumbent, challenger, cohort, evaluate, minimum_gain):
    """Use the same incumbent-first proof with a larger required exact gain."""
    baseline = sum(evaluate(incumbent, case) for case in cohort)
    target = baseline + minimum_gain
    passed = 0
    evidence = []
    for case in cohort:
        if passed >= target or passed + len(cohort) - len(evidence) < target:
            break
        observed = evaluate(challenger, case)
        evidence.append((challenger, case, observed))
        passed += observed
    return passed >= target, len(evidence), evidence


def run_cpo(matrix, held, seed, original, plan, policy):
    start, layouts = archive.smaller.narrow_schedule(
        *archive.continuous.schedule(len(matrix[0]), len(matrix), held, seed, original), plan['validationRows'])
    at_start, after_start = POLICIES[policy]
    nominations = []

    def select(incumbent, *args, **kwargs):
        result = run_fixed_pool_cycle(incumbent, *args, minimum_gain=at_start if incumbent == start else after_start,
                                      **kwargs)
        nominations.append(result.search.finalist)
        return result

    def qualify(incumbent, challenger, cohort, evaluate):
        minimum = at_start if incumbent == start else after_start
        if minimum == 1:
            return preflight(incumbent, challenger, cohort, evaluate)
        return qualify_archive_margin(incumbent, challenger, cohort, evaluate, minimum)

    with patch.object(archive, 'run_fixed_pool_cycle', select), patch.object(archive.archive, 'qualify_archived', qualify):
        totals, journal = archive.episode(matrix, held, seed, original, plan, 'recency')
    trace = [row['decision'] for row in journal]
    finalists = iter(nominations)
    aligned = [None if row['archivePromoted'] else next(finalists) for row in trace]
    return totals, journal, (start, layouts, trace, aligned)


def attribute_loss(matrix, held, state, winner):
    start, layouts, steps, finalists = state
    retained = sum(matrix[int(start)][case] == '1' for case in held)
    if winner == start:
        return {'reason': 'gepa-retained-start', 'startHoldoutPasses': retained}
    if any(step['selected'] == winner for step in steps):
        return {'reason': 'cpo-later-replaced-winner', 'startHoldoutPasses': retained}
    if any(winner in (step['challenger'], step['archiveNominee']) for step in steps):
        return {'reason': 'winner-reached-qualification', 'startHoldoutPasses': retained}
    for index, (layout, step, finalist) in enumerate(zip(layouts, steps, finalists, strict=True), 1):
        if winner not in layout['alternatives']:
            continue
        candidate, base = matrix[int(winner)], matrix[int(step['incumbent'])]
        val_gain = sum((candidate[case] == '1') - (base[case] == '1') for case in layout['validation'])
        qual_gain = sum((candidate[case] == '1') - (base[case] == '1') for case in layout['qualify'])
        if step['archivePromoted']:
            reason = 'fresh-search-skipped-by-archive'
        elif finalist == winner:
            reason = 'winner-uncertified'
        elif val_gain <= 0:
            reason = 'nonpositive-validation-gain'
        elif qual_gain <= 0:
            reason = 'validation-gain-only'
        else:
            reason = 'strict-gain-winner-missed-by-screen'
        return {'reason': reason, 'startHoldoutPasses': retained, 'cycle': index,
                'exactValidationGainOnArchivedOutcomes': val_gain, 'exactQualificationGainOnArchivedOutcomes': qual_gain}
    raise ValueError('A GEPA winner must belong to the shared starting prompt or proposal schedule')


def prepare(phase):
    prior, original, data, controls, _ = archive.prepare(phase if phase != 'independent' else 'mmlu')
    if phase == 'independent':
        raw = INDEPENDENT_REPORT.read_bytes()
        source = CORPUS.read_bytes()
        parent = independent.read_json(raw)
        frozen = independent.design()
        if (sha256(raw).hexdigest() != INDEPENDENT_SHA256 or parent['planSha256'] != digest(frozen) or
                parent['corpusSha256'] != sha256(source).hexdigest()):
            raise ValueError('The independent study must match its original design and capture')
        corpus = independent.read_json(source)
        independent.check_corpus(corpus, frozen)
        data = corpus['panels']
        original = {**frozen['schedule'], 'holdoutCaseIDs': {p['subject']: independent.transfer.holdout(
            p['subject'], len(p['correctness'][0])) for p in data}}
        known = {name: row['methods'][independent.CPO[0]] for name, row in parent['panels'].items()}
        controls = {name: {m: row['methods'][m] for m in independent.gepa.METHODS}
                    for name, row in parent['panels'].items()}
        sealed = digest(frozen)
    else:
        parent = archive.checked_report('cached-miss-witness-results-v1.json', fresh.CACHED_REPORT_SHA256, phase)
        known = {name: row['policies']['seeded'] for name, row in parent['panels'].items()}
        controls = {name: row['reinvested'] for name, row in controls.items()}
        sealed = digest(prior)
    plan = {
        **{key: prior[key] for key in ('searchCap', 'validationRows', 'gepaVersion', 'gate')},
        'protocol': 'cpo-starting-prompt-margin-v1', 'phase': phase,
        'parentPlanSha256': sealed, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'referenceReportSha256': INDEPENDENT_SHA256 if phase == 'independent' else fresh.CACHED_REPORT_SHA256,
        'policies': {p: {'whenIncumbentIsStart': g[0], 'afterLeavingStart': g[1]} for p, g in POLICIES.items()},
        'scope': 'Change the qualification margin for fresh and archived challengers within the original budgets.',
    }
    return plan, original, data, controls, known


def replay(plan, original, data, controls, known):
    panels = {}
    for panel in data:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        control = controls[name]
        methods, losses = {}, []
        for policy in POLICIES:
            total, journals, batch_trace = Counter(), [], []
            for seed in original['seeds']:
                counts, journal, state = run_cpo(matrix, held, seed, original, plan, policy)
                total.update(counts)
                journals.append(journal)
                total['finalRetainedStart'] += int(state[2][-1]['selected'] == state[0])
                if policy == 'seeded' and plan['phase'] == 'independent':
                    winner, gp, _, trace = independent.gepa.reinvest_episode(matrix, held, seed, original, plan, batched=True)
                    batch_trace.append(trace)
                    delta = gp['holdoutPasses'] - counts['holdoutPasses']
                    if delta > 0:
                        loss = attribute_loss(matrix, held, state, winner)
                        losses.append({'seed': seed, 'passDeficit': delta, 'cpoHoldoutPasses': counts['holdoutPasses'],
                                       'gepaHoldoutPasses': gp['holdoutPasses'], 'gepaWinner': winner, **loss})
            if batch_trace and digest(batch_trace) != control[BATCHED]['traceSha256']:
                raise ValueError('Loss attribution must replay the published batched GEPA trace')
            result = dict(total, paidLookups=total['searchPaid'] + total['qualificationPaid'],
                          traceSha256=digest(journals))
            if policy == 'seeded' and any(result[k] != known[name][k] for k in (*BASELINE_FIELDS, 'traceSha256')):
                raise ValueError(f'{name} differs from the published seeded result')
            methods[policy] = result
        gates = {policy: {m: meets_gate(result, ref) for m, ref in control.items()}
                 for policy, result in methods.items()}
        panels[name] = {'methods': methods, 'gepa': {m: {k: r[k] for k in ('holdoutPasses', 'paidLookups')}
                                                  for m, r in control.items()},
                        'gates': gates, 'seededLossesToBatched': losses}
    qualified = {method: [name for name, row in panels.items() if all(row['gates'][method].values())]
                 for method in POLICIES}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels, 'panelsClearingBothGates': qualified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=PHASES)
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
    report = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
