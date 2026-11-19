"""Let official GEPA spend cache savings within the transfer's paid search cap."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import bounded_transfer_matched_cost as reference
from benchmarks import grounded
from benchmarks import prompteval_archive_cycles as archive
from benchmarks import prompteval_continuous as continuous
from benchmarks import prompteval_paid_witness as paid
from benchmarks import prompteval_transfer as legacy
from benchmarks import prompteval_validation_size as smaller
from cpo import Row
from cpo._contract import digest, unique_object
from cpo.paired_qualification import certify_paired_qualification


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '9ff02d2b6a9200dba0b573705de9036b53f00e9d1c4473221182623266003f4c'
CPO = reference.CPO_METHODS[0]
METHODS = reference.GEPA_METHODS


def optimize_by_paid_reads(initial, alternatives, train, validation, observe, spent, *, paid_limit, batched, seed):
    from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig, TrackingConfig, optimize_anything
    from gepa.strategies.proposal_sampling import SameParentSampling
    from gepa.utils.stop_condition import ScoreThresholdStopper

    width = 2 if batched else 1
    proposed = 0
    round_reserve = width * (2 * legacy.PROBES + len(validation))

    def metric(prompt, example):
        return float(observe(prompt, example['case']))

    def propose(current, _feedback, components):
        nonlocal proposed
        component, = components
        if proposed == len(alternatives):
            raise ValueError('GEPA exhausted the fixed proposal roster')
        prompt = alternatives[proposed]
        proposed += 1
        return {component: prompt}

    settings = GEPAConfig(
        engine=EngineConfig(seed=seed, parallel=False, use_cloudpickle=False, cache_evaluation=True,
                            max_candidate_proposals=len(alternatives) // width, track_best_outputs=False,
                            sampling_strategy=SameParentSampling(width) if batched else None),
        reflection=ReflectionConfig(custom_candidate_proposer=propose, reflection_lm=None,
                                    reflection_minibatch_size=legacy.PROBES),
        tracking=TrackingConfig(logger=grounded.GepaLogger()),
        stop_callbacks=[ScoreThresholdStopper(1.0), lambda _: spent() + round_reserve > paid_limit],
    )
    result = optimize_anything(initial, evaluator=metric, dataset=[{'case': row} for row in train],
                               valset=[{'case': row} for row in validation], config=settings)
    return result.best_candidate, proposed


def reinvest_episode(matrix, held, seed, original, plan, *, batched):
    incumbent, layouts = smaller.narrow_schedule(
        *continuous.schedule(len(matrix[0]), len(matrix), held, seed, original), plan['validationRows'])
    history, attempted, cache = [], set(), {}
    totals = Counter(searchPaid=0, qualificationPaid=0, searchLogical=0, proposals=0, cyclesExceedingLogicalCap=0)
    peak_paid = 0
    for layout in layouts:
        alternatives, cohort = layout['alternatives'], layout['qualify']
        nominee = archive.nominate(incumbent, history, attempted, 'runner-up')
        archive_promoted, reserved = False, 0
        qualification, search = {}, {}
        proposals = 0
        start = len(cache)
        allowed = set(layout['train']) | set(layout['validation'])

        def qualify(prompt, case):
            if case not in cohort or (prompt != incumbent and prompt != nominee and prompt not in alternatives):
                raise ValueError('Qualification left the sealed prompt or case set')
            key = (prompt, case)
            if key not in qualification:
                qualification[key] = matrix[int(prompt)][case] == '1'
            return qualification[key]

        if nominee is not None:
            attempted.add((incumbent, nominee))
            archive_promoted, reserved, _ = archive.qualify_archived(incumbent, nominee, cohort, qualify)
        limit = plan['searchCap'] - reserved

        def spent():
            return len(cache) - start

        def observe(prompt, case):
            if case not in allowed or (prompt != incumbent and prompt not in alternatives):
                raise ValueError('Search left the sealed prompt or case set')
            key = (prompt, case)
            if key not in cache:
                if spent() >= limit:
                    raise ValueError('GEPA exceeded the paid search budget')
                cache[key] = matrix[int(prompt)][case] == '1'
            search[key] = cache[key]
            return search[key]

        if archive_promoted:
            challenger = selected = nominee
        else:
            challenger, proposals = optimize_by_paid_reads(
                incumbent, alternatives, layout['train'], layout['validation'], observe, spent,
                paid_limit=limit, batched=batched, seed=layout['seed'],
            )
            rows = [Row(str(case), 'task') for case in cohort]
            decision = certify_paired_qualification(
                incumbent, challenger, rows, lambda prompt, row, _: qualify(prompt, int(row.id)),
                minimum_gain=original['minimumQualificationGain'], seed=layout['seed'],
            )
            selected = decision.prompt
        if spent() + len(qualification) > plan['searchCap'] + 2 * len(cohort) or spent() > limit:
            raise ValueError('Paid search and qualification exceed the original combined ceiling')
        peak_paid = max(peak_paid, spent() + reserved)
        totals.update(searchPaid=spent(), qualificationPaid=len(qualification), searchLogical=len(search),
                      proposals=proposals, cyclesExceedingLogicalCap=int(len(search) > limit))
        history.append({'incumbent': incumbent, 'challenger': challenger, 'selected': selected,
                        'archiveNominee': nominee, 'archivePromoted': archive_promoted, 'lookupLimit': limit,
                        'searchSha256': digest([(p, case, score) for (p, case), score in search.items()]),
                        'qualificationSha256': digest([(p, case, score) for (p, case), score in qualification.items()])})
        incumbent = selected
    totals['holdoutPasses'] = sum(matrix[int(incumbent)][case] == '1' for case in held)
    return incumbent, totals, peak_paid, history


def prepare(phase):
    raw = (ROOT / 'docs/bounded-transfer-matched-cost-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('The archived matched-cost transfer differs')
    measured = json.loads(raw, object_pairs_hook=unique_object)['runs'][phase]['report']
    parent, original, data, archived = reference.prepare(phase)
    if digest(parent) != measured['planSha256']:
        raise ValueError('The archived matched-cost plan differs')
    rows, cap = reference.first.transfer.DESIGNS['candidate']
    worst_cpo = 2 * rows - 1 + original['poolSize'] - 1
    if rows != parent['validationRows'] or worst_cpo > cap - original['qualificationRowsPerCycle']:
        raise ValueError('The fixed-pool CPO roster must fit without reallocating savings')
    plan = {
        'protocol': 'cpo-gepa-paid-cap-transfer-v1', 'phase': phase, 'parentPlanSha256': digest(parent),
        'parentReportSha256': SOURCE_SHA256, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'gepaVersion': parent['gepaVersion'], 'validationRows': rows, 'searchCap': cap,
        'worstCpoLogicalSearch': worst_cpo, 'methods': list(METHODS), 'cpo': CPO, 'gate': parent['gate'],
        'reserve': 'Keep the original full-round reserve. Charge only search cache misses against it.',
        'scope': 'Same proposal roster, archive checks, separate qualification, and episode-local paid caches.',
    }
    return plan, original, data, archived, measured['panels']


def replay(plan, original, panels, archived, measured):
    results = {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        base = measured[name]['totals']
        reference_traces = {m: [] for m in METHODS}
        new = {m: Counter() for m in METHODS}
        peaks, journals = {m: 0 for m in METHODS}, {m: [] for m in METHODS}
        for seed in original['seeds']:
            old = reference.captured_episode(matrix, held, seed, original, CPO, plan['validationRows'])
            for index, method in enumerate(METHODS):
                baseline, _ = old[method]
                reference_traces[method].append(baseline)
                selected, totals, peak, trace = reinvest_episode(matrix, held, seed, original, plan, batched=bool(index))
                new[method].update(totals)
                new[method]['changedFinalPrompts'] += int(selected != baseline['candidate'])
                peaks[method] = max(peaks[method], peak)
                journals[method].append(trace)
        if any(digest(reference_traces[method]) != archived[name]['traceSha256'][method] for method in METHODS):
            raise ValueError('The original logical-budget GEPA trace differs from the archived transfer')
        repriced = {}
        for method in METHODS:
            totals = new[method]
            repriced[method] = {**totals, 'paidLookups': totals['searchPaid'] + totals['qualificationPaid'],
                                'peakPaidSearchIncludingArchiveReserve': peaks[method],
                                'traceSha256': digest(journals[method])}
        results[name] = {'previous': {m: base[m] for m in (CPO, *METHODS)}, 'reinvested': repriced,
                         'cpoGates': {m: paid.meets_gate(base[CPO], repriced[m]) for m in METHODS}}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': results,
            'cpoPanelsClearingBothGates': [name for name, row in results.items() if all(row['cpoGates'].values())]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=reference.transfer.SOURCES, required=True)
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
