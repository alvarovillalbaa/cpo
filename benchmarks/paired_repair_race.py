"""Race candidates on paid incumbent misses and a shared preservation check."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import incumbent_first_paid_repair as previous
from benchmarks.validation_repair_anchor import MMLU, attaining_trial, gepa_bounds, repair_screen, verify_witness
from cpo._contract import digest
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run, _screen as strict_screen


prior = previous.prior
BASE = 'incumbent-first'
BASELINES = (BASE, 'single-repair')
RACES = {'preserve-one': 1, 'repair-twice-or-preserve': 2}
REFERENCE = 'docs/incumbent-first-paid-repair-results-v1.json'
REFERENCE_SHA = '9e5a822b1215aa31bfb771c0449eac0e040824f7ca5c054dbd7af5f575e60a8e'


def paired_repair_screen(incumbent, candidates, rows, evaluate, cap, *, miss_limit):
    if any(row.critical for row in rows):
        return strict_screen(incumbent, candidates, rows, evaluate, cap, expected=True)
    paid = 0

    def observe(prompt, row):
        nonlocal paid
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Validation requires exact boolean replies')
        paid += 1
        return grade

    misses, passing = [], None
    for row in rows:
        if observe(incumbent, row):
            if passing is None:
                passing = row
        elif len(misses) < miss_limit:
            misses.append(row)
        if passing is not None and len(misses) == miss_limit:
            break
    if not misses:
        return FinalistResult(incumbent, None, paid), None

    for prompt in candidates:
        if paid == cap:
            break
        known = {}
        for row in misses:
            if paid == cap:
                break
            known[row.id] = observe(prompt, row)
            if known[row.id]:
                break
        if not any(known.values()):
            continue
        if passing is None:
            measured = len(known)
            return FinalistResult(prompt, prompt, paid), ((0, measured), (1, measured))
        if paid == cap:
            break
        keeps_pass = observe(prompt, passing)
        if not keeps_pass:
            for row in misses:
                if paid == cap:
                    break
                if row.id not in known:
                    known[row.id] = observe(prompt, row)
        score = sum(known.values()) + keeps_pass
        if score > 1:
            measured = len(known) + 1
            return FinalistResult(prompt, prompt, paid), ((1, measured), (score, measured))
    return FinalistResult(incumbent, None, paid), None


def prepare():
    parent, panels, controls, references, _ = previous.prepare()
    read = prior.paired.frontier.cost.prior.baseline.read_reference
    receipt = read(REFERENCE, REFERENCE_SHA, parent)['results']
    plan = {**parent, 'protocol': 'paired-repair-race-v1', 'parentPlanSha256': digest(parent),
            'incumbentFirstReceiptSha256': REFERENCE_SHA, 'pairedRaceSourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'races': RACES, 'primary': 'repair-twice-or-preserve',
            'scope': 'Use the first incumbent pass and at most two incumbent misses in the original validation '
                     'panel. A challenger must repair a miss before purchasing a preservation check. If it '
                     'fails the preservation case, the two-miss arm can still certify a strict paired gain '
                     'with two distinct repairs. Use the same precheck and independently qualify one nominee. '
                     'Keep rosters, roles and margins fixed. Replay the published MMLU GEPA attainers for paired '
                     'case ranges. Use split-safe budget bounds on all eight cohorts.',
            'gate': 'At one gain on both MMLU cohorts, the primary race must beat the affordable GEPA '
                    'ceiling and achieve a positive paired lower endpoint against both CPO baselines at no '
                    'higher lookup cost than incumbent-first.'}
    return plan, panels, controls, references, receipt


def audit_paired_margin(start, nominee, ledger, cases):
    paired_grades = [(ledger.get(('validation', start, str(case))), ledger.get(('validation', nominee, str(case))))
                     for case in cases]
    if sum(new - old for old, new in paired_grades if old is not None and new is not None) < 1:
        raise ValueError('Every race nominee must show a strict gain on the same paid validation cases')


def measure(cohort, panels, plan, controls, reference, receipt):
    run = prior.paired.cycle.execute_path
    add = prior.paired.frontier.transfer.fitted.prior.add_vector
    paired = prior.frozen.paired_effects.paired_effect
    runners = {BASE: partial(_run, screen=previous.incumbent_first_screen),
               'single-repair': partial(_run, screen=partial(repair_screen, repairs=1))}
    runners.update({name: partial(_run, screen=partial(paired_repair_screen, miss_limit=limit))
                    for name, limit in RACES.items()})
    totals = {label: {method: Counter() for method in runners} for label in controls.values()}
    vectors = {label: {} for label in controls.values()}
    native_scores, native_points = {}, {}
    attainer = reference['comparisons'][controls[1]]
    retained, trace_hashes = 0, {}
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        native_cells = {prompt: tuple((grade, None, False) for grade in row) for prompt, row in cells.items()}
        traces = {label: {method: [] for method in runners} for label in controls.values()}
        for seed in plan['seeds']:
            start, roster, roles = prior.paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            retained += sum(cells[start][case] for case in roles[-1])
            if cohort in MMLU:
                _, held, cost = attaining_trial(attainer['splitSafeCombined']['settingsBySubject'][subject],
                                                (native_cells, start, roster, roles, seed))
                native_points.setdefault(subject, Counter()).update(holdoutPasses=sum(held), paidLookups=cost)
                add(native_scores.setdefault(subject, [0] * len(held)), held)
            for gain, label in controls.items():
                scores = vectors[label].setdefault(subject, {})
                for method, runner in runners.items():
                    result, ledger = run(runner, cells, start, roster, roles, seed, plan['fullRosterCap'], gain)
                    point, grades, path = prior.paired.reference.point(cells, roles[-1], result, ledger)
                    traces[label][method].append(path)
                    add(scores.setdefault(method, [0] * len(grades)), grades)
                    nominee = result.search.finalist
                    if method in RACES:
                        verify_witness(cells, start, roles, result, ledger, gain)
                        if nominee is not None:
                            audit_paired_margin(start, nominee, ledger, roles[1])
                    totals[label][method].update(**point, searchLookups=result.search.evaluations,
                                                 qualificationLookups=result.qualification_evaluations,
                                                 nominees=int(nominee is not None), deployments=int(result.promoted))
        panel = f'{subject}/{model}'
        trace_hashes[panel] = {label: {method: digest(path) for method, path in arm.items()}
                               for label, arm in traces.items()}
        for label, arm in trace_hashes[panel].items():
            if arm[BASE] != receipt['incumbentFirstPanelPaths'][panel][label]:
                raise ValueError('The incumbent-first receipt must reproduce on every panel')

    if cohort in MMLU and native_points != attainer['attainingSubjectPoints']:
        raise ValueError('The published MMLU comparator must reproduce for every subject')
    for label, methods in totals.items():
        base = methods[BASE]
        original = receipt['comparisons'][label]
        if (base['holdoutPasses'], base['paidLookups']) != (original['holdoutPasses'], original['incumbentFirstLookups']):
            raise ValueError('The incumbent-first approved path must reconcile in score and cost')
        for subject, grades in native_scores.items():
            vectors[label][subject]['published-gepa'] = grades
        for method, point in methods.items():
            point['splitSafeGepaBounds'] = gepa_bounds(reference['comparisons'], retained, point['paidLookups'])
            if method in RACES:
                point['pairedDifferences'] = {control: paired(vectors[label], method, control, plan)
                                             for control in BASELINES}
                if native_scores:
                    point['pairedDifferences']['published-gepa'] = paired(vectors[label], method, 'published-gepa', plan)
    return {'comparisons': totals, 'traceHashes': trace_hashes, 'retainedStartPasses': retained,
            'publishedGepaBySubject': native_points}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels, controls, references, receipt = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path and the pinned GEPA version')
    results = {cohort: measure(cohort, panels[cohort], plan, controls, reference, receipt[cohort])
               for cohort, reference in references.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results}, out,
                  indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
