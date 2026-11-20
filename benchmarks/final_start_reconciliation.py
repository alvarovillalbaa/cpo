"""Use the reserved starting-prompt comparison after the last fresh search."""

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import case_difficulty_allocation as parent
from benchmarks import paid_start_retention as retention
from benchmarks import routed_score_allocation as route
from cpo._contract import digest
from cpo.fixed_pool_cycle import FixedPoolCycleResult


ROOT = Path(__file__).resolve().parents[1]
PARENT_REPORT = '48fdcd163f677fa88c40e1f98212b87cea2d3a44fe024749e5da2f721f72a9a9'
METHODS = ('after-finalist', 'fallback-only')
CONTROLS = ('strict', *route.GEPA, 'retain-start')


@dataclass(frozen=True)
class ReconciledCycle(FixedPoolCycleResult):
    deployment: str

    @property
    def prompt(self):
        return self.deployment


def reconcile(fresh, start, cases, evaluate, qualify_archive, *, always):
    if fresh.promoted and not always:
        return fresh, []
    preferred, _, observations = qualify_archive(fresh.prompt, start, cases, evaluate)
    choice = start if preferred else fresh.prompt
    return ReconciledCycle(fresh.search, fresh.qualification, choice), observations


def episode(matrix, held, seed, plan, start, method):
    split = route.ties.split
    run = split.run
    cycle = split.fixed_pool_cycle
    archive = split.archive.archive
    expected_cycle = plan['schedule']['cycles'] - 1
    deferred = None
    in_final_cycle = False
    details = None
    stats = Counter()

    def capture(*args):
        original_fresh = cycle.run_fixed_pool_cycle
        original_archive, original_nominate = archive.qualify_archived, archive.nominate

        def nominate(incumbent, history, attempted, policy):
            nonlocal in_final_cycle
            in_final_cycle = len(history) == expected_cycle
            return original_nominate(incumbent, history, attempted, policy)

        def preflight(incumbent, challenger, cases, qualify):
            nonlocal deferred
            if in_final_cycle and challenger == start:
                if incumbent == start or deferred is not None:
                    raise ValueError('The final cycle should defer one comparison against a distinct start')
                deferred = tuple(cases), qualify
                return False, len(cases), []
            return original_archive(incumbent, challenger, cases, qualify)

        def fresh(incumbent, candidates, rows, cohort, evaluate, *, qualify, metric_limit, **kwargs):
            nonlocal details
            if deferred is None:
                return original_fresh(incumbent, candidates, rows, cohort, evaluate, metric_limit=metric_limit,
                                      qualify=qualify, **kwargs)
            cases, assess = deferred
            if (tuple(int(row.id) for row in cohort) != cases or not in_final_cycle
                    or metric_limit + len(cases) != plan['searchCap']):
                raise ValueError('Use the existing final panel and reserve one challenger within the original cap')
            read = set()

            def paid_qualification(prompt, row, repeat):
                reply = qualify(prompt, row, repeat)
                read.add((prompt, int(row.id)))
                return reply

            result = original_fresh(incumbent, candidates, rows, cohort, evaluate, metric_limit=metric_limit,
                                    qualify=paid_qualification, **kwargs)
            final, observed = reconcile(result, start, cases, assess, original_archive, always=method == METHODS[0])
            extra = {(prompt, case) for prompt, case, _ in observed} - read
            if result.search.evaluations + len(read) + len(extra) > plan['searchCap'] + 2 * len(cases):
                raise ValueError('The deferred start comparison exceeded the original combined limit')
            stats.update(deferred=1, freshPromotion=int(result.promoted), startChecks=int(bool(observed)),
                         startReturns=int(final.prompt == start), startOverridesFresh=int(result.promoted and final.prompt == start),
                         lateQualificationLookups=len(extra))
            details = {'provisional': result.prompt, 'selection': final.prompt, 'archiveReplySha256': digest(observed),
                       'lookupLimit': metric_limit, 'extraQualificationLookups': len(extra)}
            return final

        with (patch.object(archive, 'nominate', nominate), patch.object(archive, 'qualify_archived', preflight),
              patch.object(cycle, 'run_fixed_pool_cycle', fresh)):
            return run(*args)

    with patch.object(split, 'run', capture):
        counts, trace = route.run(matrix, held, seed, plan, start, 'strict')
    if (deferred is not None) != (details is not None):
        raise ValueError('Every deferral must reach the final search')
    if details is not None:
        trace[-1]['startReconciliation'] = details
    counts.update(stats)
    return counts, trace


def prepare():
    known, inputs = parent.prepare()
    parent.checked_file('docs/paid-start-retention-results-v1.json', PARENT_REPORT)
    audit = parent.checked_file('docs/priced-gate-reachability-results-v1.json', retention.AUDIT_REPORT)
    files = ('benchmarks/final_start_reconciliation.py', 'benchmarks/archive_complementarity_transfer.py',
             'benchmarks/routed_start_protection.py', 'benchmarks/routed_witness_split.py',
             'benchmarks/prompteval_archive_cycles.py', 'cpo/fixed_pool_cycle.py')
    design = {'protocol': 'cpo-final-start-reconciliation-v1', 'parentDesignSha256': digest(known),
              'parentReportSha256': PARENT_REPORT, 'reachabilityReportSha256': retention.AUDIT_REPORT,
              'primary': METHODS[0], 'methods': METHODS, 'controls': CONTROLS,
              'scope': ('If the last cycle nominates the start from the archive, reserve the width of the '
                        'qualification panel for an extra challenger and run fresh search first. Compare the '
                        'start with the policy-selected provisional prompt on the same qualification cases. '
                        'Fallback-only skips that comparison if fresh qualification promotes a candidate.'),
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in files}}
    return design, {name: (*item, audit['results'][name]['panels']) for name, item in inputs.items()}


def measure(panels, references, plan, prior):
    labels = (*CONTROLS, *METHODS)
    totals = {label: Counter() for label in labels}
    results, vectors, holdouts = {}, {method: {} for method in METHODS}, {}
    for panel in panels:
        subject, model, matrix = (panel[field] for field in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        uncertainty = route.CONFIRMATION.uncertainty
        held = route.CONFIRMATION.holdout(subject, len(matrix[0]))
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('Both model splits must share the holdout cases')
        starts = route.ties.costs.retained_prompts(matrix, held, plan['schedule'])
        finals, points = {label: [] for label in labels}, {}
        finals['retain-start'] = starts
        points['retain-start'] = {'holdoutPasses': sum(uncertainty.case_totals(matrix, held, starts).values()),
                                  'paidLookups': 0}
        for label in route.GEPA:
            mode, cap = label.split('/')
            finals[label], points[label] = uncertainty.final_prompts(matrix, held, plan['schedule'], plan, mode, int(cap))

        counts, traces = ({label: factory() for label in ('strict', *METHODS)} for factory in (Counter, list))
        for index, (seed, start) in enumerate(zip(plan['schedule']['seeds'], starts, strict=True)):
            baseline, original = route.run(matrix, held, seed, plan, str(start), 'strict')
            decision = original[-1]['decision']['selected']
            counts['strict'].update(baseline)
            traces['strict'].append(original)
            finals['strict'].append(int(decision))
            audited = prior[name]['episodes'][index]
            if audited['seed'] != seed or audited['cpoPaidLookups'] != baseline['searchPaid'] + baseline['qualificationPaid']:
                raise ValueError('Baseline costs differ from the costed audit')
            for label in METHODS:
                used, trace = episode(matrix, held, seed, plan, str(start), label)
                selection = trace[-1]['decision']['selected']
                if original[:-1] != trace[:-1] or not used['deferred'] and original != trace:
                    raise ValueError('The experiment modified a nondeferred cycle')
                delta = used['holdoutPasses'] - baseline['holdoutPasses']
                counts[label].update(used)
                counts[label].update(changedFinal=int(selection != decision), improvedEpisodes=int(delta > 0),
                                     regressedEpisodes=int(delta < 0), grossGains=max(delta, 0), grossLosses=max(-delta, 0),
                                     matchedStartRecoveries=sum(selection != decision and selection == str(start)
                                                                and bound == 'retain-start'
                                                                for bound in audited['firstBound'].values()))
                traces[label].append(trace)
                finals[label].append(int(selection))
        for label, count in counts.items():
            points[label] = {**count, 'paidLookups': count['searchPaid'] + count['qualificationPaid'],
                             'traceSha256': digest(traces[label])}
        for label in CONTROLS:
            for key in parent.FIELDS:
                if key in references[name][label] and references[name][label][key] != points[label][key]:
                    raise ValueError(f'A published control differs: {name}/{label}')

        outcomes = {label: uncertainty.case_totals(matrix, held, choices) for label, choices in finals.items()}
        if any(sum(outcomes[label].values()) != point['holdoutPasses'] for label, point in points.items()):
            raise ValueError('Holdout totals differ from the selected final prompts')
        for label, point in points.items():
            totals[label].update({key: val for key, val in point.items() if type(val) is int})
        for label in METHODS:
            margins = vectors[label].setdefault(subject, {ctrl: [0] * len(held) for ctrl in CONTROLS})
            for control, scores in margins.items():
                for i, case in enumerate(held):
                    scores[i] += outcomes[label][case] - outcomes[control][case]
        results[name] = points

    comparisons = {}
    for label, scores in vectors.items():
        ranges = route.transfer.ranges(scores, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
        paid = totals[label]['paidLookups']
        savings = {control: 1 - paid / totals[control]['paidLookups'] for control in route.GEPA}
        threshold = 100 - plan['minimumLookupSavingPercent']
        funded = all(100 * paid <= threshold * totals[control]['paidLookups'] for control in route.PRIMARY)
        low, high = ranges['joint']
        gate = 'failed' if not funded or high < 0 else 'passed' if low >= 0 else 'inconclusive'
        comparisons[label] = {'gate': gate, 'lookupSavings': savings, 'pairedRanges': ranges}
    return {'totals': totals, 'comparisons': comparisons, 'panels': results}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, inputs = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for _, _, plan, _ in inputs.values()):
        cli.error('Use pinned GEPA 0.1.4')
    results = {key: measure(*data) for key, data in inputs.items()}
    with args.out.open('x') as stream:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
