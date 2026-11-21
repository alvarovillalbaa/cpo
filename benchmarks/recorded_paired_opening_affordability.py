"""Test repair certificates that can fit without funding every missing reply."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_paired_opening_transfer as transfer
from cpo._contract import digest
from cpo.family_qualification import certify_family_qualification
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.single_finalist import FinalistResult


ROOT = transfer.prior.ROOT
REFERENCE = ROOT / 'docs/recorded-paired-opening-transfer-results-v1.json'
REFERENCE_SHA = 'd8c154968b0e031a531d3bd7887db00f83f337d6f0e75b585dba34daa2476524'
SCALES = {name: transfer.CAPS[name] for name in ('paired-opening-cap-2x', 'paired-opening-cap-2.5x')}
POLICIES = ('reserve', 'spend-remainder', 'minimum-reads')


def minimum_reads(rows, incumbent, challenger, known):
    """Return the fewest favorable missing grades that could certify this pair."""
    lower, missing, obligations = Counter(), Counter(), Counter()
    for row in rows:
        old, new = (known.get((prompt, row.id)) for prompt in (incumbent, challenger))
        lower[row.family] += -1 + (old is False) + (new is True)
        missing[row.family] += (old is None) + (new is None)
        if row.critical and old is not False and new is not True:
            if old is True and new is False:
                return None
            obligations[row.family] += 1
    family_required = {family: max(0, -score, obligations[family]) for family, score in lower.items()}
    if any(count > missing[family] for family, count in family_required.items()):
        return None
    required = max(sum(family_required.values()), 1 - sum(lower.values()))
    return required if required <= missing.total() else None


class StopProof(Exception):
    """Stop reading once the proof is settled or cannot fit the remaining allowance."""


def search(incumbent, pair, rows, evaluate, cap, seed, policy, activity):
    known = {}
    for prompt in (pair.rewrite, pair.repair):
        pending = sum((side, row.id) not in known for side in (incumbent, prompt) for row in rows)
        partial_proof = len(known) + pending > cap
        if partial_proof and (policy == 'reserve' or prompt == pair.rewrite):
            break
        start = len(known)

        def observe(side, row, _repeat):
            key = side, row.id
            if key not in known:
                if partial_proof and policy == 'minimum-reads':
                    required = minimum_reads(rows, incumbent, prompt, known)
                    if required is None or required == 0 or required > cap - len(known):
                        raise StopProof
                if len(known) == cap:
                    raise StopProof
                known[key] = evaluate(side, row).passed
            return known[key]

        try:
            proof = certify_family_qualification(incumbent, prompt, rows, observe, seed=seed)
            accepted = proof.status == 'promoted'
        except StopProof:
            accepted = minimum_reads(rows, incumbent, prompt, known) == 0
        if partial_proof:
            activity['unreservedRepairPaths'] += 1
            activity['unreservedRepairReads'] += len(known) - start
            activity['unreservedRepairCertificates'] += accepted
        if accepted:
            return FinalistResult(prompt, prompt, len(known))
    return FinalistResult(incumbent, None, len(known))


def adapter(incumbent, _train, validation, _admission, evaluate, *, opening_pair, metric_limit, seed,
            scale, policy, activity, **_):
    numerator, denominator = scale
    cap = min(metric_limit, (numerator * len(validation) + denominator - 1) // denominator)
    result = search(incumbent, opening_pair, validation, evaluate, cap, seed, policy, activity)
    return FixedPoolCycleResult(result, None)


def prepare():
    source, data, _ = transfer.prepare()
    raw = REFERENCE.read_bytes()
    expected = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA or expected['planSha256'] != digest(source):
        raise ValueError('Use the original paired-opening control source and result')
    plan = {'protocol': 'recorded-paired-opening-affordability-v1', 'parentPlanSha256': digest(source),
            'parentReceiptSha256': REFERENCE_SHA, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'searchCapPerValidationCase': SCALES, 'methods': POLICIES, 'primary': 'minimum-reads at 2.5x',
            'scope': ('Preserve the funded rewrite attempt. Try a partially funded repair only when the required '
                      'favorable evidence can fit. Keep disjoint admission and report paired losses.'),
            'costQualityGate': source['gate'],
            'originalNativeControls': list(transfer.prior.CONTROLS)}
    return plan, source, data, expected['results']


def measure_group(cells, settings, starts, expected):
    size = len(next(iter(cells.values())))
    groups = {cap: {policy: Counter() for policy in POLICIES} for cap in SCALES}
    activity = {cap: {policy: Counter() for policy in POLICIES[1:]} for cap in SCALES}
    traces = {cap: {policy: [] for policy in POLICIES} for cap in SCALES}
    grades = {cap: {policy: [0] * size for policy in POLICIES[1:]} for cap in SCALES}
    paired = {cap: {policy: Counter() for policy in POLICIES[1:]} for cap in SCALES}
    for seed in settings['seeds']:
        cohorts = transfer.prior.split_cases(size, seed, settings['cohorts'])
        for incumbent in starts:
            choices = [prompt for prompt in cells if prompt != incumbent]
            pair = Random(f'{seed}/{incumbent}').sample(choices, len(choices))[:2]
            for cap, scale in SCALES.items():
                outcomes = {}
                for policy in POLICIES:
                    choose = partial(transfer.package_adapter, scale=scale) if policy == 'reserve' else partial(
                        adapter, scale=scale, policy=policy, activity=activity[cap][policy])
                    with patch.object(transfer.prior, 'run_opening_screen_cycle', choose):
                        outcome = transfer.prior.trial(cells, incumbent, pair, cohorts, seed, transfer.prior.BASELINE)
                    groups[cap][policy].update(outcome['totals'])
                    traces[cap][policy].append([seed, incumbent, pair, outcome])
                    outcomes[policy] = outcome
                blind, bounded = (outcomes[name] for name in POLICIES[1:])
                if any(blind[field] != bounded[field] for field in ('nominee', 'selected', 'passed')):
                    raise ValueError('The funding bound changed a reachable repair decision')
                if bounded['totals']['searchReads'] > blind['totals']['searchReads']:
                    raise ValueError('The funding bound spent more paid reads than the blind proof')
                base = outcomes['reserve']
                for policy in POLICIES[1:]:
                    candidate = outcomes[policy]
                    counts = paired[cap][policy]
                    counts['changedNominees'] += candidate['nominee'] != base['nominee']
                    counts['changedAdmissions'] += candidate['selected'] != base['selected']
                    for case, before, after in zip(cohorts[-1], base['passed'], candidate['passed'], strict=True):
                        grades[cap][policy][case] += after - before
                        counts['matchedCaseLosses'] += after < before

    totals = {cap: {policy: {**values, 'traceSha256': digest(traces[cap][policy])} for policy, values in methods.items()}
              for cap, methods in groups.items()}
    if any(totals[cap]['reserve'] != expected['totals'][cap] for cap in SCALES):
        raise ValueError('The original reserve control did not reproduce')
    comparisons = {cap: {policy: {**counts, 'caseResampling95PassDifference': transfer.prior.case_resampling_range(
        (grades[cap][policy],))} for policy, counts in methods.items()} for cap, methods in paired.items()}
    inherited = {name: values for name, values in expected['totals'].items() if name not in SCALES}
    metric = 'historicalCostNanodollars' if 'historicalCostNanodollars' in inherited[transfer.METHOD] else 'paidReads'
    native = {}
    for cap, policies in totals.items():
        candidate = policies['minimum-reads']
        matched = {}
        for arm in transfer.prior.CONTROLS:
            control = inherited[arm]
            gain = candidate['holdoutPasses'] - control['holdoutPasses']
            cost, baseline = candidate[metric], control[metric]
            matched[arm] = {'passDelta': gain, 'costDelta': cost - baseline,
                            'qualifies': gain > 0 and cost <= baseline or gain == 0 and 10 * cost <= 9 * baseline}
        native[cap] = matched
    return {'paths': expected['pathsPerArm'], 'byCap': totals, 'additionalProofs': activity,
            'pairedWithSameCapReserve': comparisons, 'inheritedControls': inherited,
            'minimumReadsVsNative': {'metric': metric, 'byCap': native}}


def execute(plan, source, dataset, expected):
    if version('gepa') != source['gepaVersion']:
        raise ValueError('Use the pinned GEPA 0.1.4 package')
    results = {}
    for task, settings in source['datasets'].items():
        cells = transfer.prior.load_cells(task, dataset[task]['record'])
        starts = tuple(cells)
        results[task] = {group: measure_group(cells, settings, starts[:1] if group == 'root' else starts[1:],
                                              expected[task][group]) for group in source['incumbentGroups']}
    return {'plan': plan, 'planSha256': digest(plan), 'results': results, 'newProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Use the current plan seal and a fresh output path')
    result = execute(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
