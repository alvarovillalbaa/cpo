"""Replay the frozen CPO router with a joint qualification ordering model."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import adaptive_archive_search as adaptive
from cpo import two_sided_certificate_cycle
from cpo._contract import digest
from cpo.joint_order_qualification import finish_joint_order, validation_context


continuous, native, transfer = adaptive.continuous, adaptive.native, adaptive.transfer
ROUTED, RETAIN = adaptive.ROUTED, adaptive.RETAIN
DISCOVERY = 'docs/adaptive-archive-search-fit-v1.json'
DISCOVERY_SHA = 'b239af9f482b08c024a16c11f60e3a5b91fd64cab98b19f15e132cf46a999da2'
ORIGINAL_FINISH = two_sided_certificate_cycle._finish_with_partner_evidence


def source_hashes():
    paths = (Path(__file__), Path(adaptive.__file__), Path(two_sided_certificate_cycle.__file__),
             *(transfer.ROOT / 'cpo' / f'{name}.py' for name in
               ('joint_order_qualification', 'paired_order_certificate_cycle', 'expected_qualification')))
    return {str(path.relative_to(transfer.ROOT)): sha256(path.read_bytes()).hexdigest() for path in paths}


def training():
    source = json.loads(transfer.read_locked(DISCOVERY, DISCOVERY_SHA))
    base = source['plan']
    discovery, groups, *_ = native.prepare()
    if digest(base) != source['planSha256'] or digest(discovery) != base['discoveryPlanSha256']:
        raise ValueError('The discovery archive and enrollment must reproduce')
    _, models, static = adaptive.promotion.training_plan()
    plan = {**base, 'protocol': 'joint-archive-proof-fit-v1', 'parentFitSha256': DISCOVERY_SHA,
            'sourceSha256': {**base['sourceSha256'], **source_hashes()},
            'scope': 'Use only task-disjoint discovery episodes and the frozen router. After its nomination, '
                     'fit four favorable-bit joint frequencies from each archived qualification pair, grouped by '
                     'coarse validation pass rates. Add one to each combination and use the pooled counts for '
                     'missing contexts. Empirical weights order lookups but never settle a proof.'}
    return plan, groups, models, static


def context_key(counts):
    return '/'.join(map(str, validation_context(counts)))


def validation_reads(ledger):
    return [(key, grade) for key, grade in ledger.items() if key[0] == 'validation']


def fit(plan, groups, models, static):
    runner = adaptive.routed_runner(plan, models, static)
    run = native.paired.cycle.execute_path
    frequencies = {'pooled': [1] * 4}
    observed = Counter()
    totals = {}
    for cohort, panels in groups.items():
        enrollment = set(map(tuple, plan['fitEnrollment'][cohort]))
        if not enrollment:
            continue
        totals[cohort] = Counter()
        for subject, model, matrix in panels:
            if (subject, model) not in enrollment:
                continue
            cells, _ = transfer.case_cells(matrix)

            def collect(incumbent, challenger, rows, read, history, counts, minimum, seed):
                key = context_key(counts)
                row_counts = frequencies.setdefault(key, [1] * 4)
                for row in rows:
                    index = int(row.id)
                    bit = 2 * (not cells[incumbent][index]) + cells[challenger][index]
                    frequencies['pooled'][bit] += 1
                    row_counts[bit] += 1
                observed[key] += 1
                return ORIGINAL_FINISH(incumbent, challenger, rows, read, history, counts, minimum, seed)

            with patch.object(two_sided_certificate_cycle, '_finish_with_partner_evidence', collect):
                for seed in plan['seeds']:
                    current, stages = continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
                    held = stages[0][2][-1]
                    for local_seed, roster, roles in stages:
                        result, ledger = run(runner, cells, current, roster, roles, local_seed, plan['fullRosterCap'], 1)
                        totals[cohort]['paidLookups'] += len(ledger)
                        current = result.prompt
                    totals[cohort]['holdoutPasses'] += sum(cells[current][case] for case in held)
    if totals != json.loads(transfer.read_locked(DISCOVERY, DISCOVERY_SHA))['baseline']:
        raise ValueError('The frozen discovery router must reproduce score and cost before fitting')
    return {'plan': plan, 'planSha256': digest(plan), 'weights': frequencies, 'nominationsByContext': observed,
            'discoveryTotals': totals, 'providerRequests': 0}


def prepare(cohort, fit_bytes):
    trained = json.loads(fit_bytes)
    training = trained['plan']
    sources = source_hashes()
    if (training['protocol'] != 'joint-archive-proof-fit-v1' or training['parentFitSha256'] != DISCOVERY_SHA
            or trained['planSha256'] != digest(training)
            or any(training['sourceSha256'].get(path) != sha for path, sha in sources.items())):
        raise ValueError('The fitted source and plan must match the running scheduler')
    base, panels, models, static, _ = continuous.prepare(cohort)
    lock = adaptive.promotion.RECEIPTS[cohort]
    ref = json.loads(transfer.read_locked(f'docs/continuous-archive-routing-{cohort.lower()}-v1.json', lock))
    simple_lock = adaptive.RECEIPTS[cohort]
    simple = json.loads(transfer.read_locked(f'docs/continuous-search-controls-{cohort.lower()}-v1.json', simple_lock))
    if ref['planSha256'] != digest(base):
        raise ValueError('The transfer layout must match the original continuous replay')
    plan = {**base, 'protocol': 'joint-archive-proof-transfer-v1', 'fitSha256': sha256(fit_bytes).hexdigest(),
            'parentReceiptSha256': lock, 'simpleControlSha256': simple_lock,
            'sourceSha256': {**base['sourceSha256'], **sources},
            'scope': 'Freeze every routed nomination and deployment. Compare the former one-step partner ordering '
                     'with exact expected remaining reads under the fitted paired-grade model. Verify every original '
                     'path hash. Count each added or saved lookup, and audit against the attainable proof floor '
                     'with knowledge of unseen grades. Reprice the simple controls at the new realized budget.'}
    return plan, panels, models, static, trained, ref['results'], simple['results']


def measure(plan, panels, models, static, fit, reference, simple):
    priors = {tuple(map(int, key.split('/'))) if key != 'pooled' else None: values
              for key, values in fit['weights'].items()}
    runner = adaptive.routed_runner(plan, models, static)
    run = native.paired.cycle.execute_path
    point = native.paired.reference.point
    totals, hashes = Counter(), {}
    for subject, model, matrix in panels:
        cells, _ = transfer.case_cells(matrix)
        paths, revised_paths = [], []

        def finish(incumbent, challenger, rows, read, history, counts, minimum, seed):
            initial = tuple(history)
            gain = sum(cells[challenger][int(row.id)] - cells[incumbent][int(row.id)] for row in rows)
            hits = sum(not event.passed for event in initial)
            needed = len(rows) + minimum - hits if gain >= minimum else len(rows) - minimum + 1 - (len(initial) - hits)
            floor = len(initial) + max(0, needed)
            result = finish_joint_order(incumbent, challenger, rows, read, history, counts, minimum, seed, priors=priors)
            evidence.append((floor, initial))
            return result

        for seed in plan['seeds']:
            current, stages = continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
            held = stages[0][2][-1]
            trajectory, revised = [], []
            for local_seed, roster, roles in stages:
                inputs = runner, cells, current, roster, roles, local_seed, plan['fullRosterCap'], 1
                before, paid = run(*inputs)
                evidence = []
                with patch.object(two_sided_certificate_cycle, '_finish_with_partner_evidence', finish):
                    after, repriced = run(*inputs)
                if (before.search != after.search or before.prompt != after.prompt
                        or before.qualification.status != after.qualification.status
                        or validation_reads(paid) != validation_reads(repriced)):
                    raise ValueError('Only qualification after nomination may change')
                if evidence:
                    (floor, initial), = evidence
                    if any(result.qualification.observations[:len(initial)] != initial for result in (before, after)):
                        raise ValueError('The paid incumbent precheck must stay unchanged')
                    if min(before.qualification_evaluations, after.qualification_evaluations) < floor:
                        raise ValueError('A certificate cannot finish below the hindsight floor')
                    continuous.routing.verify_qualification(cells, current, roles, after, repriced, 1)
                    totals.update(nominations=1, proofFloor=floor,
                                  originalNominatedProof=before.qualification_evaluations,
                                  jointNominatedProof=after.qualification_evaluations)
                elif paid != repriced:
                    raise ValueError('Without a nomination every lookup must stay unchanged')
                saved = len(paid) - len(repriced)
                totals.update(cycles=1, originalLookups=len(paid), jointLookups=len(repriced), saved=max(0, saved),
                              added=max(0, -saved), cheaper=int(saved > 0), dearer=int(saved < 0))
                trajectory.append((current, before.prompt, point(cells, held, before, paid)[2]))
                revised.append((current, after.prompt, point(cells, held, after, repriced)[2]))
                current = after.prompt
            paths.append(trajectory)
            revised_paths.append(revised)
            totals['holdoutPasses'] += sum(cells[current][case] for case in held)
        panel = f'{subject}/{model}'
        if digest(paths) != reference['panelTrajectoryHashes'][panel][ROUTED]:
            raise ValueError('The original route must match its archived trace in every panel')
        hashes[panel] = digest(revised_paths)
    if (totals['holdoutPasses'], totals['originalLookups']) != (
            reference['cpo'][ROUTED]['holdoutPasses'], reference['cpo'][ROUTED]['paidLookups']):
        raise ValueError('The original route must match the published score and price')
    settings = tuple(name for name in simple['settingsTotals'] if name != RETAIN)
    budget = totals['jointLookups']
    common = native.gepa.best_fixed(simple['settingsTotals'], settings, budget)
    repriced = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling(
        simple['settingsBySubject'], settings, {'joint': budget})['joint']
    return {'pairedProofCost': totals, 'jointPanelHashes': hashes,
            'commonSimple': common, 'subjectTunedSimple': repriced,
            'priorBestCommonGepa': reference['bestCommonGepa'][ROUTED],
            'priorSubjectTunedGepa': reference['subjectTunedGepa'][ROUTED]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--fit', type=Path)
    modes.add_argument('--cohort', choices=continuous.COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.fit is not None:
        if args.fit.exists() or any((args.fitted, args.execute, args.out)):
            parser.error('Fit requires only a fresh output path')
        plan, *inputs = training()
        if version('gepa') != plan['gepaVersion']:
            parser.error('Replay requires pinned GEPA')
        report, path = fit(plan, *inputs), args.fit
    else:
        if args.fitted is None:
            parser.error('Transfer requires a fitted receipt')
        plan, *inputs = prepare(args.cohort, args.fitted.read_bytes())
        seal = digest(plan)
        if args.execute is None and args.out is None:
            print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
            return
        if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
            parser.error('Transfer requires its current seal, pinned GEPA and a fresh output path')
        report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': measure(plan, *inputs)}
        path = args.out
    with path.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
