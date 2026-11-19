"""Spread gain probes while capping extra incumbent reads during screening."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_archive_cycles as archive
from benchmarks import prompteval_lazy_incumbent as deferred
from benchmarks import prompteval_paid_witness as paid
from benchmarks import prompteval_single_finalist as first
from benchmarks.prompteval_validation_transfer import CPO, paired
from cpo._contract import digest, unique_object
from cpo.bounded_discovery import select_with_bounded_discovery


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '0a45817c2f8cce8e65f152fe52af370fdefc3094fe469f7efc00c1725b0eaec3'
POLICIES = {'two-reads': (2, 1), 'four-reads': (4, 1), 'two-reads-after-four': (2, 4)}


def measured_episode(matrix, held, seed, original, policy, audit):
    discovery_limit, shared_prefix = POLICIES[policy]

    def select(incumbent, candidates, validation, evaluate, *, metric_limit, screen):
        if screen != 'first-gain':
            raise ValueError('Bounded discovery requires a first-gain screen')
        return select_with_bounded_discovery(incumbent, candidates, validation, evaluate,
                                             metric_limit=metric_limit, discovery_limit=discovery_limit,
                                             shared_prefix=shared_prefix, audit=audit)

    with patch.object(first, 'select_single_finalist', select):
        return first.screened_episode(matrix, held, seed, original, 'first-gain')[CPO]


def prepare(phase):
    raw = (ROOT / 'docs/prompteval-lazy-incumbent-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('The archived deferred replay differs')
    stored = json.loads(raw, object_pairs_hook=unique_object)['runs'][phase]['report']
    parent, original, source, _, _ = deferred.prepare(phase)
    if digest(parent) != stored['planSha256']:
        raise ValueError('The archived deferral seal differs')
    plan = {
        'protocol': 'cpo-prompteval-bounded-discovery-v1', 'phase': phase, 'parentPlanSha256': digest(parent),
        'parentReportSha256': SOURCE_SHA256, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'selectorSha256': sha256((ROOT / 'cpo/bounded_discovery.py').read_bytes()).hexdigest(),
        'gepaVersion': parent['gepaVersion'], 'rowsAndCap': parent['rowsAndCap'], 'gate': parent['gate'],
        'primary': 'two-reads',
        'scope': 'Limit new incumbent reads during screening. Preserve archive nomination and exact qualification.',
        'policies': {policy: {'discoveryLimit': limit, 'sharedPrefix': prefix}
                     for policy, (limit, prefix) in POLICIES.items()},
    }
    return plan, original, source, stored['panels']


def replay(plan, original, source, archived):
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held, seeds = original['holdoutCaseIDs'][subject], original['seeds']
        reference = [first.screened_episode(matrix, held, seed, original, 'first-gain') for seed in seeds]
        traces = {method: [episode[method] for episode in reference] for method in first.METHODS[1:]}
        stored = archived[name]
        if any(first.totals(trace) != stored['original'][m] for m, trace in traces.items()):
            raise ValueError('The GEPA controls differ from the archived totals')
        candidates = {}
        with patch.object(archive, 'METHODS', archive.METHODS[:1]):
            baseline = [deferred.measured_episode(matrix, held, seed, original, False, False) for seed in seeds]
            expected = stored['candidates']['deferred-first-gain']
            if digest(baseline) != expected['traceSha256']:
                raise ValueError('The deferred first-gain trace does not reproduce')
            traces['deferred-first-gain'] = baseline
            for policy in POLICIES:
                audit = Counter()
                measured = [measured_episode(matrix, held, seed, original, policy, audit) for seed in seeds]
                candidates[policy] = {'totals': first.totals(measured), 'audit': dict(audit),
                                      'traceSha256': digest(measured),
                                      'comparisons': {m: paired(measured, trace) for m, trace in traces.items()}}
        panels[name] = {'baseline': {m: first.totals(t) for m, t in traces.items()}, 'candidates': candidates}
    qualified = {policy: [name for name, panel in panels.items() if all(
        panel['candidates'][policy]['comparisons'][method]['qualified'] for method in first.METHODS[1:])]
                 for policy in POLICIES}
    qualified['deferred-first-gain'] = [name for name, panel in panels.items() if all(
        paid.meets_gate(panel['baseline']['deferred-first-gain'], panel['baseline'][m]) for m in first.METHODS[1:])]
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels, 'panelsClearingBothGates': qualified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=paid.PHASES, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
