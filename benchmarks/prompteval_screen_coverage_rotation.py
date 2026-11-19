"""Compare distributed miss probes and a bounded retention check."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import islice
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_gate_reachability as reach
from benchmarks import prompteval_paid_witness as paid
from benchmarks import prompteval_single_finalist as first
from benchmarks.prompteval_validation_transfer import CPO, paired
from cpo._contract import digest, unique_object
from cpo.challenger import certify_challenger
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '15b7eea63193805aaf8ef383863e185875f589daaca7a04b4b4763edca093977'
POLICIES = {'rotate-misses': (True, False), 'retention-duel': (False, True), 'rotate-and-duel': (True, True)}
LOOKAHEAD = 3


def select_covered_finalist(incumbent, candidates, validation, evaluate, *, metric_limit, rotate, duel, audit):
    """Probe each visited candidate on one miss and certify at most one candidate."""
    rows, candidates = tuple(validation), tuple(candidates)
    if len({row.id for row in rows}) != len(rows) or not rows:
        raise ValueError('The validation panel must be nonempty and have distinct cases')
    if len(set(candidates)) != len(candidates) or incumbent in candidates:
        raise ValueError('The challenger pool must be distinct from the incumbent')
    if type(metric_limit) is not int or metric_limit < len(rows):
        raise ValueError('The evaluation cap must fund the incumbent')
    if not candidates:
        return FinalistResult(incumbent, None, 0)
    spent = 0

    def observe(prompt, row):
        nonlocal spent
        reply = evaluate(prompt, row)
        if type(reply.passed) is not bool:
            raise ValueError('Validation requires exact boolean outcomes')
        spent += 1
        return reply

    baseline = {row.id: observe(incumbent, row).passed for row in rows}
    misses = [row for row in rows if not baseline[row.id]]
    if not misses:
        return FinalistResult(incumbent, None, spent)
    audit['cyclesWithMisses'] += 1

    def probe(index, prompt):
        row = misses[index % len(misses)] if rotate else misses[0]
        audit['gainProbes'] += 1
        if row != misses[0]:
            audit['probesOnOtherMisses'] += 1
        return row if observe(prompt, row).passed else None

    offers = iter(enumerate(candidates))
    finalist, evidence = None, {}
    for index, prompt in offers:
        if spent + len(rows) > metric_limit:
            break
        gain = probe(index, prompt)
        if gain is not None:
            finalist, evidence = prompt, {gain.id: True}
            break
    if finalist is None:
        audit['noNominee'] += 1
        return FinalistResult(incumbent, None, spent)

    retained = min((row for row in rows if baseline[row.id]), key=lambda row: not row.critical, default=None)
    if duel and retained is not None:
        audit['retentionProbes'] += 1
        evidence[retained.id] = observe(finalist, retained).passed
        if not evidence[retained.id]:
            for index, prompt in islice(offers, LOOKAHEAD):
                if spent + len(rows) > metric_limit:
                    break
                gain = probe(index, prompt)
                if gain is None:
                    continue
                audit['retentionProbes'] += 1
                if observe(prompt, retained).passed:
                    finalist, evidence = prompt, {gain.id: True, retained.id: True}
                    audit['duelChangedNominee'] += 1
                    break
    order = sorted(rows, key=lambda row: baseline[row.id])
    certificate = certify_challenger(order, baseline, lambda row: observe(finalist, row),
                                     metric_limit=metric_limit - spent, observed=evidence)
    audit['certificate.' + certificate.status] += 1
    selected = finalist if certificate.status == 'promote' else incumbent
    return FinalistResult(selected, finalist, spent)


def measured_episode(matrix, held, seed, original, policy, audit):
    rotate, duel = POLICIES[policy]

    def select(incumbent, candidates, validation, evaluate, *, metric_limit, screen):
        if screen != 'first-gain':
            raise ValueError('The coverage experiment requires first-gain')
        return select_covered_finalist(incumbent, candidates, validation, evaluate, metric_limit=metric_limit,
                                     rotate=rotate, duel=duel, audit=audit)

    with patch.object(first, 'select_single_finalist', select):
        return first.screened_episode(matrix, held, seed, original, 'first-gain')


def prepare(phase):
    raw = (ROOT / 'docs/prompteval-gate-reachability-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('The reachability evidence differs from the verified source')
    evidence = json.loads(raw, object_pairs_hook=unique_object)['runs'][phase]['report']
    parent, original, source, published = reach.prepare(phase)
    if digest(parent) != evidence['planSha256']:
        raise ValueError('The reachability seal differs')
    plan = {
        'protocol': 'cpo-prompteval-screen-coverage-rotation-v1', 'phase': phase,
        'parentPlanSha256': digest(parent), 'parentReportSha256': SOURCE_SHA256,
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'gepaVersion': parent['gepaVersion'], 'rowsAndCap': parent['rowsAndCap'],
        'lookaheadLimit': LOOKAHEAD, 'primary': 'rotate-misses',
        'policies': {name: {'rotateMisses': rotate, 'retentionDuel': duel}
                     for name, (rotate, duel) in POLICIES.items()},
        'scope': 'Fixed prompt streams, original archive nomination, strict certificate and independent qualification',
        'gate': 'Match both official GEPA controls at no extra cost, with more passes or 10% fewer lookups',
    }
    return plan, original, source, published


def replay(plan, original, source, published):
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[field] for field in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        seeds = original['seeds']
        reference = [first.screened_episode(matrix, held, seed, original, 'first-gain') for seed in seeds]
        traces = {method: [episode[method] for episode in reference] for method in first.METHODS}
        baseline = {method: first.totals(trace) for method, trace in traces.items()}
        if (baseline != published[name]['baseline'] or
                digest(traces[CPO]) != published[name]['baselineFirstGainTraceSha256']):
            raise ValueError('The measured selection or controls differ from their archived results')
        candidates = {}
        for policy in POLICIES:
            audit = Counter()
            episodes = [measured_episode(matrix, held, seed, original, policy, audit) for seed in seeds]
            if any([episode[method] for episode in episodes] != traces[method] for method in first.METHODS[1:]):
                raise ValueError('A coverage policy changed a matched GEPA trace')
            measured = [episode[CPO] for episode in episodes]
            candidates[policy] = {'totals': first.totals(measured), 'audit': dict(audit),
                                  'traceSha256': digest(measured),
                                  'comparisons': {m: paired(measured, trace) for m, trace in traces.items()}}
        panels[name] = {'baseline': baseline, 'candidates': candidates}
    qualified = {policy: [name for name, panel in panels.items() if all(
        panel['candidates'][policy]['comparisons'][method]['qualified'] for method in first.METHODS[1:])]
                 for policy in POLICIES}
    qualified['first-gain'] = [name for name, panel in panels.items() if all(
        paid.meets_gate(panel['baseline'][CPO], panel['baseline'][m]) for m in first.METHODS[1:])]
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
