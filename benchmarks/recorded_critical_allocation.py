"""Test whether moving available critical cases into evaluation prevents replay losses."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import combinations
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_coverage_confirmation as parent
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
PARENT_REPORT = '85bdcb19940e4800aa627696c2ad2410e407cec61b51a16c7a20deeae1eadf5a'
POLICIES = ('original', 'matched-moves', 'risk-coverage')
PRIMARY = parent.PRIMARY


def allocate(layout, risk, seed):
    """Move only cases from these three roles, keeping each critical quota."""
    rows = tuple(case for panel in layout for case in panel)
    train, validation, qualification = tuple(frozenset(panel) for panel in layout)
    if len(rows) != len(set(rows)):
        raise ValueError('Panel allocation requires disjoint original roles')
    original = train, validation, qualification
    original_critical = tuple(len(panel & risk.keys()) for panel in original)
    bank = frozenset(rows)

    def moved(panels):
        return sum(len(before - after) for before, after in zip(original, panels, strict=True))

    def priority(panels):
        validate = {risk[case] for case in panels[1] if case in risk}
        qualify = {risk[case] for case in panels[2] if case in risk}
        return len(validate | qualify), len(qualify), len(validate), -moved(panels)

    options = []
    for trained in map(frozenset, combinations(rows, len(train))):
        if len(trained & risk.keys()) != original_critical[0]:
            continue
        remaining = tuple(case for case in rows if case not in trained)
        for qualified in map(frozenset, combinations(remaining, len(qualification))):
            if len(qualified & risk.keys()) == original_critical[2]:
                options.append((trained, bank - trained - qualified, qualified))
    chosen = max(options, key=priority)
    moves = moved(chosen)
    control = Random(f'{seed}:matched-role-moves').choice([option for option in options if moved(option) == moves])

    def ordered(panels):
        # Existing case order stays intact, and incoming cases follow the original concatenated order.
        return tuple(tuple(case for case in rows if case in panel) for panel in panels)

    return {'original': layout, 'matched-moves': ordered(control), 'risk-coverage': ordered(chosen)}


def prepare():
    previous, tasks = parent.prepare()
    raw = (ROOT / 'docs/recorded-coverage-confirmation-results-v1.json').read_bytes()
    archive = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_REPORT or digest(previous) != archive['planSha256']:
        raise ValueError('The previous coverage confirmation replay differs from its seal')
    plan = {**previous, 'protocol': 'cpo-recorded-critical-allocation-v1', 'allocationPolicies': POLICIES,
            'primaryAllocation': 'risk-coverage', 'parentPlanSha256': digest(previous),
            'parentReportSha256': PARENT_REPORT,
            'sourceSha256': {**previous['sourceSha256'], str(Path(__file__).relative_to(ROOT)):
                             sha256(Path(__file__).read_bytes()).hexdigest()},
            'allocationOrder': ['distinct critical strata across validation and qualification',
                                'distinct critical strata on qualification', 'distinct critical strata on validation',
                                'fewest case role changes', 'original case order'],
            'allocationConstraints': 'The same nine cases, role sizes and critical counts. Matched role changes control.',
            'lossAudit': 'After selection, count loss strata with and without a critical case anywhere before holdout.'}
    return plan, tasks, archive['results']


def run_layout(data, held, seed, cap, layout):
    # Use the original runner and let its seeded shuffle consume the same RNG
    # state before replacing the case order. Candidate draws stay identical.
    generator = Random(seed)

    class FixedLayout:
        def shuffle(self, cases):
            generator.shuffle(cases)
            cases[:] = [case for panel in layout for case in panel]

        def sample(self, pool, size):
            return generator.sample(pool, size)

    with patch.object(parent, 'Random', return_value=FixedLayout()):
        return parent.compare(data, held, seed, cap)


def measure(data, cap, plan, reference):
    metadata, _, _, _, _, risk, _ = data
    held_sets = tuple(combinations(sorted(metadata), 3))
    cases_by_policy = {policy: [] for policy in POLICIES}
    diagnostics = {
        policy: {'coverage': Counter(), 'losses': {method: Counter(total=0, outsideAllDevelopment=0)
                                                   for method in parent.GEPA}}
        for policy in POLICIES
    }
    effects = {policy: Counter(passDelta=0, lookupDelta=0, criticalLosses=0)
               for policy in ('original', 'matched-moves')}
    for index, held in enumerate(held_sets):
        seed = plan['seedStart'] + index * plan['seedStride']
        cases = sorted(metadata.keys() - set(held))
        Random(seed).shuffle(cases)
        original = tuple(cases[:3]), tuple(cases[3:7]), tuple(cases[7:])
        accessible = {risk[case] for case in cases if case in risk}
        layouts = allocate(original, risk, seed)
        cache, selected = {}, {}
        for policy, layout in layouts.items():
            if layout not in cache:
                cache[layout] = run_layout(data, held, seed, cap, layout)
            record, validate, qualify = cache[layout]
            cases_by_policy[policy].append((record, validate, qualify))
            selected[policy] = record[PRIMARY]
            validation = {risk[case] for case in validate if case in risk}
            qualification = {risk[case] for case in qualify if case in risk}
            stats = diagnostics[policy]
            stats['coverage'].update(pool=len(accessible), evaluation=len(validation | qualification),
                                     validation=len(validation), qualification=len(qualification),
                                     moved=sum(len(set(before) - set(after))
                                               for before, after in zip(original, layout, strict=True)))
            for method, counts in stats['losses'].items():
                missed = [case for case in held if case in risk and record[method]['outcomes'][case]
                          and not record[PRIMARY]['outcomes'][case]]
                counts.update(total=len(missed), outsideAllDevelopment=sum(risk[case] not in accessible for case in missed))
        proposed = selected['risk-coverage']
        for policy, counts in effects.items():
            control = selected[policy]
            counts.update(passDelta=sum(proposed['outcomes'].values()) - sum(control['outcomes'].values()),
                          lookupDelta=proposed['total'] - control['total'],
                          criticalLosses=sum(case in risk and control['outcomes'][case] and not proposed['outcomes'][case]
                                             for case in held))

    summaries = {}
    for policy, records in cases_by_policy.items():
        with patch.object(parent, 'compare', side_effect=records):
            summaries[policy] = parent.summarize(data, cap, held_sets, plan)
    if summaries['original'] != reference:
        raise ValueError('Original allocation did not reproduce every previous arm trace and total')
    return {'allocations': summaries, 'diagnostics': diagnostics, 'coverageFirstCompared': effects}


def replay(plan, tasks, reference):
    results = {task: {str(cap): measure(data, cap, plan, reference[task][str(cap)])
                      for cap in plan['caps']}
               for task, data in sorted(tasks.items())}
    return {'plan': plan, 'planSha256': digest(plan), 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, tasks, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, tasks, reference)
    with args.out.open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
