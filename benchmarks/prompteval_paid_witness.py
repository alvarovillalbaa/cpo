"""Choose a first-gain witness using earlier paid outcomes in the same episode."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_single_finalist as prior
from benchmarks import prompteval_validation_size as smaller
from benchmarks.prompteval_validation_transfer import CPO, paired
from cpo._contract import digest, unique_object
from cpo.single_finalist import select_single_finalist


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'prompteval-single-finalist-results-v1.json': 'd74cbfe37948db493599fd0c3c0ba419253972356b9bd76018d29572aeda780a',
    'prompteval-validation-size-results-v1.json': '813c13e13bfb81a58e83a1eb1e58cf87954e8601aa3e62c4848d583411bbcbd9',
}
POLICIES = ('avoid-two-failures', 'smoothed-pass-rate')
PHASES = ('finalist-transfer', 'development', 'retrospective-transfer')


def select_witness(failures, incumbent, history, policy):
    """Use only previous paid observations from distinct non-incumbent prompts."""
    def score(row):
        samples = [passed for prompt, passed in history.get(row.id, {}).items() if prompt != incumbent]
        passes = sum(samples)
        if policy == POLICIES[0]:
            return len(samples) < 2 or passes > 0
        if policy == POLICIES[1]:
            return Fraction(1 + passes, 2 + len(samples))
        raise ValueError('Unknown witness policy')

    return max(failures, key=score, default=None)


def use_history(incumbent, candidates, validation, evaluate, *, metric_limit, history, policy, audit):
    rows = tuple(validation)
    observed = {}

    def record(prompt, row):
        key = prompt, row.id
        if key not in observed:
            observed[key] = evaluate(prompt, row)
        return observed[key]

    failures = []
    if candidates:
        failures = [row for row in rows if not record(incumbent, row).passed]
    witness = select_witness(failures, incumbent, history, policy)
    if witness is not None:
        audit['cyclesWithMisses'] += 1
        if witness != failures[0]:
            audit['changedWitness'] += 1
            rows = (witness, *(row for row in rows if row.id != witness.id))
    result = select_single_finalist(incumbent, candidates, rows, record,
                                    metric_limit=metric_limit, screen='first-gain')
    if result.evaluations != len(observed):
        raise ValueError('First-gain charges differ from the paid evidence')
    if witness is not None and result.finalist is None:
        audit['noNominee'] += 1
    if result.prompt != incumbent:
        audit['certified'] += 1
    for (prompt, case), reply in observed.items():
        if history.setdefault(case, {}).setdefault(prompt, reply.passed) is not reply.passed:
            raise ValueError('Recorded outcomes disagreed on a repeated observation')
    return result


def measured_episode(matrix, held, seed, original, policy, audit):
    history = {}

    def select(incumbent, candidates, validation, evaluate, *, metric_limit, screen):
        if screen != 'first-gain':
            raise ValueError('The witness policy requires first-gain')
        return use_history(incumbent, candidates, validation, evaluate, metric_limit=metric_limit,
                           history=history, policy=policy, audit=audit)

    with patch.object(prior, 'select_single_finalist', select):
        return prior.screened_episode(matrix, held, seed, original, 'first-gain')


def checked_reports():
    reports = []
    for name, expected in SOURCES.items():
        raw = (ROOT / 'docs' / name).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError('An archived result differs from its verified source')
        reports.append(json.loads(raw, object_pairs_hook=unique_object))
    return reports


def prepare(phase):
    first, size = checked_reports()
    if phase == PHASES[0]:
        parent, original, source, _ = prior.prepare()
        published = first
        fixed_totals = {panel: data['baseline'] for panel, data in first['panels'].items()}
        fixed_digests = {panel: data['candidates']['first-gain']['traceSha256']
                         for panel, data in first['panels'].items()}
    else:
        parent, original, source, _, _ = smaller.prepare(phase)
        published = next(entry for entry in size['runs'] if entry['phase'] == phase)
        if size['panelColumns'][:2] != ['passes', 'lookups'] or tuple(
                published['fixedDesigns']['half-scaled-budget']) != prior.transfer.DESIGNS['candidate']:
            raise ValueError('The comparison requires the published half-scaled budget')
        fixed_totals = {
            name: {method: dict(zip(('holdoutPasses', 'paidLookups'), totals[:2], strict=True))
                   for method, totals in panel['half-scaled-budget']['totals'].items()}
            for name, panel in published['panels'].items()
        }
        fixed_digests = {}
    if digest(parent) != published['planSha256']:
        raise ValueError('Archived parent seal differs')
    plan = {
        'protocol': 'cpo-prompteval-paid-witness-v1', 'phase': phase, 'parentPlanSha256': digest(parent),
        'reportsSha256': SOURCES, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'parentRunnerSha256': sha256(Path(prior.__file__).read_bytes()).hexdigest(),
        'selectorSha256': sha256((ROOT / 'cpo/single_finalist.py').read_bytes()).hexdigest(),
        'gepaVersion': original['gepaVersion'], 'rowsAndCap': prior.transfer.DESIGNS['candidate'],
        'policies': list(POLICIES), 'primary': POLICIES[0],
        'scope': 'Paid validation observations only, from earlier cycles in the same episode',
        'gate': 'Match both official GEPA controls at no extra cost, with more passes or 10% fewer lookups',
    }
    return plan, original, source, fixed_totals, fixed_digests


def replay(plan, original, source, fixed_totals, fixed_digests):
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        seeds = original['seeds']
        references = [prior.screened_episode(matrix, held, seed, original, 'first-gain') for seed in seeds]
        traces = {method: [episode[method] for episode in references] for method in prior.METHODS}
        if name in fixed_digests and digest(traces[CPO]) != fixed_digests[name]:
            raise ValueError('The archived first-gain trace differs')
        if any(prior.totals(traces[m]) != fixed_totals[name][m] for m in prior.METHODS[1:]):
            raise ValueError('Published GEPA lookup or pass totals differ')
        candidates = {}
        for policy in POLICIES:
            audit = Counter()
            episodes = [measured_episode(matrix, held, seed, original, policy, audit) for seed in seeds]
            if any([episode[m] for episode in episodes] != traces[m] for m in prior.METHODS[1:]):
                raise ValueError('A witness policy changed a matched GEPA trace')
            measured = [episode[CPO] for episode in episodes]
            candidates[policy] = {'totals': prior.totals(measured), 'audit': dict(audit),
                                  'traceSha256': digest(measured),
                                  'comparisons': {m: paired(measured, trace) for m, trace in traces.items()}}
        panels[name] = {'baseline': {m: prior.totals(trace) for m, trace in traces.items()},
                        'baselineFirstGainTraceSha256': digest(traces[CPO]), 'candidates': candidates}
    qualified = {policy: [name for name, panel in panels.items() if all(
        panel['candidates'][policy]['comparisons'][m]['qualified'] for m in prior.METHODS[1:])]
                 for policy in POLICIES}
    baseline_qualified = [name for name, panel in panels.items() if all(
        meets_gate(panel['baseline'][CPO], panel['baseline'][m]) for m in prior.METHODS[1:])]
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels,
            'panelsClearingBothGates': {'first-gain': baseline_qualified, **qualified}}


def meets_gate(candidate, control):
    passes, cost = candidate['holdoutPasses'], candidate['paidLookups']
    reference, cap = control['holdoutPasses'], control['paidLookups']
    return passes >= reference and cost <= cap and (passes > reference or 10 * cost <= 9 * cap)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=PHASES, required=True)
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
