"""Compare rotating witnesses on the local, parent-linked Sol proposal archive."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cpo._contract import digest
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.optimizer import balanced_order
from cpo.rotating_witness import _nominate
from cpo.single_finalist import FinalistResult


REVISION = 'da79a2a378f190526255b6a78a7d0bf5f7885e8a'
OVERLAY_REVISION = 'e1e34941051a5e1dc7fb4bc9ff82503b257d471b'
WITNESS_PATH = 'cpo/rotating_witness/__init__.py'
WITNESS_SHA = '299a48086605c6804af0249b605c50b7b617cb95654a2828bf827c22215175c8'
REFERENCE = 'docs/results/2026/11-19/cpo-recorded-gepa-disjoint-frontier-v1.json'
REFERENCE_SHA = '15a427fb2e98118cc61cf98082051b8506028f6dfdf6c500f4fdb3ecf6820fde'
CONTROLS = ('opening-only', 'staged', 'gepa-sequential', 'gepa-batched')
WITNESS = ('witness-opening', 'witness-branch')
FOLLOWUPS = ('paired-opening-proof', 'witness-ordered-proof')
LATER_SLOTS = 4
PROBES = 2


def budgeted_observer(observed, evaluate, cap):
    def observe(prompt, row):
        key = prompt, row.id
        if key not in observed:
            if len(observed) >= cap:
                raise ValueError('The witness graph exceeded the shared paid search ceiling')
            observed[key] = evaluate(prompt, row)
        return observed[key]

    return observe


def search(initial, train, validation, evaluate, propose, *, opening, cap, seed, later_slots):
    observed = {}
    activity = Counter()
    observe = budgeted_observer(observed, evaluate, cap)
    current = _nominate(initial, opening, validation, observe, metric_limit=cap, seed=seed).prompt
    activity['openingMoves'] += current != initial
    visited = {initial, *opening}
    for index in range(later_slots):
        if all((current, row.id) in observed and observed[current, row.id].passed for row in validation):
            break
        # Fund training and a pass/miss screen before asking for the next edge.
        remaining = cap - len(observed)
        if remaining < PROBES + 2 * len(validation):
            break
        probes = balanced_order(train, seed + index)[:PROBES]
        feedback = tuple((row, observe(current, row)) for row in probes)
        child = propose(current, feedback)
        activity['rootSlots' if current == initial else 'descendantSlots'] += 1
        if child == current:
            activity['unavailableSlots'] += 1
            break
        if child in visited:
            activity['repeatedPrompts'] += 1
            continue
        visited.add(child)
        chosen = _nominate(current, (child,), validation, observe, metric_limit=cap - len(observed),
                           seed=seed + index + 1).prompt
        activity['laterMoves'] += chosen != current
        current = chosen
    return FinalistResult(current, current if current != initial else None, len(observed)), activity


def compare(candidate, control, metadata):
    return {
        'passDelta': sum(candidate['holdout'].values()) - sum(control['holdout'].values()),
        'criticalLosses': sum(control['holdout'][case] and not passed and metadata[case]['critical']
                              for case, passed in candidate['holdout'].items()),
        'costDeltaMicrousd': candidate['historicalMicrousd'] - control['historicalMicrousd'],
        'changedPrompts': int(candidate['selected'] != control['selected']),
    }


def opening_proof(initial, opening, validation, evaluate, certify, *, cap, seed, prioritize):
    observed = {}
    observe = budgeted_observer(observed, evaluate, cap)
    activity = Counter()
    if prioritize:
        nominee = _nominate(initial, opening, validation, observe, metric_limit=cap, seed=seed).prompt
        if nominee != initial:
            opening = (nominee, *(prompt for prompt in opening if prompt != nominee))

    for contender in opening:
        # Give the exact gate a conservative budget for reads still missing.
        pending = sum((prompt, row.id) not in observed for prompt in (initial, contender) for row in validation)
        if len(observed) + pending > cap:
            break
        activity['proofsAttempted'] += 1
        result = certify(initial, contender, validation, lambda prompt, row, _: observe(prompt, row).passed, seed=seed)
        if result.status == 'promoted':
            return FinalistResult(contender, contender, len(observed)), activity
    return FinalistResult(initial, None, len(observed)), activity


def overlay(source, *, method, activity):
    def choose(incumbent, train, validation, admission, evaluate, propose, *, opening_pair, metric_limit,
               qualify, seed, **_settings):
        opening = opening_pair.rewrite, opening_pair.repair
        if method in WITNESS:
            nominee, counters = search(incumbent, train, validation, evaluate, propose, opening=opening,
                                       cap=metric_limit, seed=seed, later_slots=LATER_SLOTS if method == WITNESS[1] else 0)
        else:
            nominee, counters = opening_proof(incumbent, opening, validation, evaluate,
                                              source.certify_family_qualification, cap=metric_limit, seed=seed,
                                              prioritize=method == FOLLOWUPS[1])
        activity.update(counters)
        decision = source.certify_family_qualification(incumbent, nominee.prompt, admission, qualify, seed=seed)
        return FixedPoolCycleResult(nominee, decision)

    return choose


def prepare(source, frontier):
    raw = Path(REFERENCE).read_bytes()
    if sha256(raw).hexdigest() != REFERENCE_SHA:
        raise ValueError('The previous split-safe GEPA result differs from its seal')
    saved = json.loads(raw)
    design, parent, inputs, origin, _ = frontier.prepare()
    if saved['designSha256'] != digest(design):
        raise ValueError('The native control plan differs from the saved result')
    paths = (Path(__file__), Path(source.__file__), Path(frontier.__file__))
    plan = {'protocol': 'sol-recorded-rotating-witness-graph-v1', 'sourceRevision': REVISION,
            'witnessSourceSha256': WITNESS_SHA, 'previousDesignSha256': digest(design),
            'previousResultSha256': REFERENCE_SHA, 'historicalOverlayRevision': OVERLAY_REVISION,
            'sharedSearchCap': parent['metricCap'], 'laterProposalSlots': LATER_SLOTS,
            'trainProbes': PROBES, 'seedSets': parent['seedSets'], 'splitSizes': parent['cohortSizes'],
            'methods': [*CONTROLS, *WITNESS, *FOLLOWUPS], 'primary': WITNESS[1],
            'exploratoryFollowups': list(FOLLOWUPS),
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'gate': ('Each task and seed set must preserve every comparator critical pass. Require higher held-out '
                     'passes at no greater historical cost, or equal passes with at least 10 percent savings.')}
    return plan, inputs, origin, saved['correctedCap56Reference']


def measure(source, frontier, plan, inputs, origin, reference):
    cohorts = {}
    prices = {task: source.archive.observations(task, matrix, start, rewrite)
              for task, ((start, _, matrix, _, _), _, rewrite, _) in inputs.items()}
    for phase, seeds in plan['seedSets'].items():
        tasks = {}
        for task, data in inputs.items():
            metadata = data[0][1]
            previous = origin['cohorts'][phase]['trials'][task]
            configs = [(task, data, seed, row['heldOut'], prices[task]) for seed, row in zip(seeds, previous, strict=True)]
            with patch.object(source.opening_screen_typed, 'gepa_select', frontier.disjoint.select):
                baseline = [source.trial(*args) for args in configs]
            if digest(baseline) != reference['cohorts'][phase]['trialSha256ByTask'][task]:
                raise ValueError(f'A split-safe native or CPO trace changed for {phase}/{task}')
            rows = {method: [record['arms'][method] for record in baseline] for method in CONTROLS}
            totals, comparisons = {}, {}
            for method in (*WITNESS, *FOLLOWUPS):
                events = Counter()
                with patch.multiple(source, ARMS=('staged',), run_validation_guided_repair_cycle=overlay(
                        source, method=method, activity=events)):
                    rows[method] = [source.trial(*args)['arms']['staged'] for args in configs]
                totals[method] = {'searchActivity': events}
            for method, records in rows.items():
                counts = Counter()
                for record in records:
                    counts.update({field: record[field] for field in ('searchReads', 'admissionReads',
                        'laterProposalSlots', 'laterRecordedReflections', 'historicalMicrousd')})
                    counts['holdoutPasses'] += sum(record['holdout'].values())
                totals.setdefault(method, {}).update({**counts, 'traceSha256': digest(records)})
            for method in (*WITNESS, *FOLLOWUPS):
                comparisons[method] = {}
                for control in (*CONTROLS, *(arm for arm in (*WITNESS, *FOLLOWUPS) if arm != method)):
                    delta = Counter()
                    for candidate, matched in zip(rows[method], rows[control], strict=True):
                        delta.update(compare(candidate, matched, metadata))
                    cost = totals[control]['historicalMicrousd']
                    delta_cost = delta['costDeltaMicrousd']
                    qualified = delta['criticalLosses'] == 0 and (
                        delta['passDelta'] > 0 and delta_cost <= 0 or
                        delta['passDelta'] == 0 and 10 * (cost + delta_cost) <= 9 * cost
                    )
                    comparisons[method][control] = {**delta, 'qualifies': qualified}
            tasks[task] = {'paths': len(configs), 'totals': totals, 'comparisons': comparisons}
        cohorts[phase] = tasks
    return cohorts


def staged(args):
    import benchmark_recorded_gepa_disjoint_frontier as frontier
    import benchmark_recorded_staged_opening_ablation as source

    plan, inputs, origin, reference = prepare(source, frontier)
    seal = digest(plan)
    if args.execute is None:
        print(json.dumps({'design': plan, 'designSha256': seal}, indent=2, sort_keys=True))
        return 0
    if args.execute != seal or args.out.exists() or args.out.is_relative_to(source.archive.source.ARCHIVE.resolve()):
        raise ValueError('Use the current seal and a fresh output outside the provider archive')
    result = {'design': plan, 'designSha256': seal, 'newProviderRequests': 0,
              'cohorts': measure(source, frontier, plan, inputs, origin, reference)}
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')
    return 0


def launch(args):
    sys.path.insert(0, str(args.research_root.resolve()))
    try:
        from run_recorded_gepa_disjoint_frontier import stage_experiment
        from run_recorded_opening_price_bounds import REVISION as staged_revision
    finally:
        sys.path.pop(0)
    if staged_revision != OVERLAY_REVISION:
        raise ValueError('The historical CPO overlay changed')
    project = Path(__file__).resolve().parents[1]
    raw = subprocess.check_output(['git', '-C', str(project), 'show', f'{REVISION}:{WITNESS_PATH}'])
    if sha256(raw).hexdigest() != WITNESS_SHA:
        raise ValueError('The package witness source differs from the release hash')
    with TemporaryDirectory(prefix='cpo-witness-graph-') as directory:
        scratch = Path(directory).resolve()
        workspace, env = stage_experiment(scratch)
        path = scratch / 'source' / WITNESS_PATH
        path.parent.mkdir()
        path.write_bytes(raw)
        entry = workspace / Path(__file__).name
        entry.write_bytes(Path(__file__).read_bytes())
        guard = subprocess.run([sys.executable, '-B', '-c', 'import socket; socket.getaddrinfo("localhost", 443)'],
                               cwd=workspace, env=env, capture_output=True)
        if guard.returncode != 1 or b'Offline ablation forbids sockets and DNS' not in guard.stderr:
            raise ValueError('The offline network guard did not reject DNS')
        options = [] if args.execute is None else ['--execute', args.execute, '--out', str(args.out.resolve())]
        return subprocess.run([sys.executable, '-B', str(entry), '--staged', *options], cwd=workspace, env=env).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--research-root', type=Path)
    mode.add_argument('--staged', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=lambda path: Path(path).resolve())
    args = parser.parse_args()
    if bool(args.execute) != bool(args.out):
        parser.error('Execution requires a seal and a fresh output path')
    return staged(args) if args.staged else launch(args)


if __name__ == '__main__':
    raise SystemExit(main())
