"""Use stranded validation allowance to finish the last opened proposal."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import expected_cost_proposal_replay as source
from benchmarks.case_difficulty_allocation import checked_file
from cpo import expected_cost_proposal_cycle as cycle
from cpo._contract import digest
from cpo.challenger import certify_challenger


ROOT = Path(__file__).resolve().parents[1]
PARENT = 'a340fc3fc1ea6757a691ad594a54a13f500adf2d22328db65707e48b9c1289e5'
CAP = 72
POLICIES = ('finish', 'certificate')
CAPS = (CAP, 104, *POLICIES, 171)


def complete(result, rows, journal, evaluate, *, cap, policy, audit):
    remaining = cap - result.evaluations
    terminal = result.events[-1]
    if terminal['kind'] != 'budget' or not 0 < remaining <= len(rows):
        return result
    if len({row.family for row in rows}) != 1:
        raise ValueError('The terminal replay requires a single validation family')

    nominee, candidate = result.prompt, terminal['prompt']
    incumbent = {row.id: journal[nominee, row.id] for row in rows}
    unread = set(terminal['unobserved'])
    observed = {case: journal[candidate, case] for case in incumbent if (candidate, case) in journal}
    prefix = incumbent.keys() - unread
    if not unread <= incumbent.keys() or not prefix <= observed.keys() or set(terminal['passed']) != {
            case for case in prefix if observed[case]}:
        raise ValueError('The terminal event does not describe the recorded validation prefix')
    pending = incumbent.keys() - observed.keys()
    audit.update(strandedPartial=1, unusedLookups=remaining, canFinish=int(len(pending) <= remaining),
                 optimisticGain=int(sum(observed.values()) + len(pending) > sum(incumbent.values())))
    if sum(observed.values()) + len(pending) <= sum(incumbent.values()):
        return result

    ordered = sorted(rows, key=lambda row: (not row.critical, incumbent[row.id]))
    if policy == 'finish':
        if len(pending) > remaining:
            return result
        suffix = {row.id: evaluate(candidate, row).passed for row in ordered if row.id in pending}
        scores = {**observed, **suffix}
        safe = all(scores[row.id] for row in rows if row.critical and incumbent[row.id])
        promoted = safe and sum(scores.values()) > sum(incumbent.values())
        spent = len(suffix)
    else:
        answer = certify_challenger(ordered, incumbent, lambda row: evaluate(candidate, row), metric_limit=remaining,
                                    observed=observed)
        scores, spent = answer.observations, answer.evaluations
        promoted = answer.status == 'promote'
    audit.update(tailLookups=spent, changedNominee=int(promoted),
                 certifiedWhilePartial=int(promoted and len(scores) < len(rows)))
    event = {'kind': 'terminal_certificate', 'prompt': candidate, 'accepted': promoted,
             'lookups': spent, 'passed': sorted(case for case, passed in scores.items() if passed),
             'unobserved': sorted(incumbent.keys() - scores.keys())}
    return replace(result, prompt=candidate if promoted else nominee, evaluations=result.evaluations + spent,
                   events=[*result.events, event])


def terminal_engine(policy, audit):
    original = cycle.search

    def search(initial, train, validation, evaluate, propose, **options):
        allowed = {row.id for row in validation}
        ledger = {}

        def recorded(prompt, row):
            reply = evaluate(prompt, row)
            if row.id in allowed:
                ledger[prompt, row.id] = reply.passed
            return reply

        result = original(initial, train, validation, recorded, propose, **options)
        return complete(result, validation, ledger, recorded, cap=options['metric_limit'], policy=policy, audit=audit)

    return search


def prepare():
    old, phases = source.prepare()
    archive = checked_file('docs/expected-cost-proposal-replay-results-v1.json', PARENT)
    if digest(old) != archive['designSha256']:
        raise ValueError('The proposal-cycle source must reproduce the published design')
    paths = ('benchmarks/proposal_terminal_completion.py', 'benchmarks/expected_cost_proposal_replay.py',
             'cpo/challenger.py', 'cpo/optimizer.py', 'cpo/expected_cost_proposal_cycle.py')
    design = {'protocol': 'cpo-proposal-terminal-completion-v1', 'baselineReportSha256': PARENT,
              'baselineDesignSha256': digest(old), 'searchCap': CAP, 'comparedCaps': CAPS, 'primary': POLICIES[1],
              'scope': ('Recover only the last candidate left partially validated at a budget boundary. Reuse '
                        'paid replies and spend only the original cycle allowance. The new nominee needs a '
                        'strict exact validation gain and the unchanged independent qualification.'),
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}}
    return design, phases, archive['results']


def diagnose(matrix, layout, result, stats):
    search = result.search
    terminal = search.events[-1]
    remaining = CAP - search.evaluations
    if terminal['kind'] != 'budget' or not 0 < remaining <= len(layout['validation']):
        return
    validation = layout['validation']
    incumbent = search.events[0]['prompt']
    can_win = sum((matrix[int(terminal['prompt'])][case] == '1') - (matrix[int(search.prompt)][case] == '1')
                  for case in validation) > 0
    would_promote = can_win and sum(
        (matrix[int(terminal['prompt'])][case] == '1') - (matrix[int(incumbent)][case] == '1')
        for case in layout['qualify']) > 0
    stats.update(strandedPartial=1, unusedLookups=remaining,
                 canFinish=int(len(terminal['unobserved']) <= remaining),
                 archivedValidationWins=int(can_win), archivedAlsoQualifies=int(would_promote))


def replay(plan, panels, references, previous):
    inherited_episode, inherited_step = source.proposal_episode, source.archive_step
    audit = Counter()

    def episode(matrix, start, layouts, settings):
        cap = settings['evaluationLookupLimit']
        if cap == CAP:
            def observed(matrix, incumbent, layout, policy):
                outcome = inherited_step(matrix, incumbent, layout, policy)
                diagnose(matrix, layout, outcome[0], audit)
                return outcome

            with patch.object(source, 'archive_step', observed):
                return inherited_episode(matrix, start, layouts, settings)
        if cap not in POLICIES:
            return inherited_episode(matrix, start, layouts, settings)
        total, trace = Counter(), []
        incumbent = start
        settings = {**settings, 'evaluationLookupLimit': CAP}
        with patch.object(cycle, 'search', terminal_engine(cap, total)):
            for layout in layouts:
                result, _, search_hash = inherited_step(matrix, incumbent, layout, settings)
                receipts = result.qualification.observations if result.qualification is not None else ()
                total.update(searchLookups=result.search.evaluations, expected=len(receipts),
                             promotions=int(result.promoted), reflections=result.search.reflections)
                trace.append((incumbent, result.search.prompt, result.prompt, search_hash,
                              [(item.prompt, item.row_id, item.repeat, item.passed) for item in receipts]))
                incumbent = result.prompt
        return int(incumbent), total, trace

    with patch.multiple(source, CAPS=CAPS, proposal_episode=episode):
        report = source.measure_phase(plan, panels, references)
    controls = (*source.continuous.GEPA, 'cpo-72', 'cpo-104', 'cpo-171')
    for name, points in report['panels'].items():
        if any(points[label] != previous[name][label] for label in controls):
            raise ValueError(f'An unchanged proposal or GEPA control differs for {name}')
    return {**report, 'baselineAudit': audit}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, phases, archive = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for plan, *_ in phases.values()):
        cli.error('Use pinned GEPA 0.1.4')
    report = {'design': design, 'designSha256': seal, 'results': {
        phase: replay(*inputs, archive[phase]['panels']) for phase, inputs in phases.items()}}
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
