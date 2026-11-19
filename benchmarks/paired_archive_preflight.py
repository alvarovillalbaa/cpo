"""Measure a decision-equivalent archive qualifier and its effects on fallback budgets."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import minimum_proof_budget as parents
from benchmarks import paid_budget_frontier as frontier
from benchmarks import starting_prompt_margin as attribution
from benchmarks.prompteval_paid_witness import meets_gate
from cpo import Row
from cpo._contract import digest
from cpo.paired_qualification import certify_paired_qualification


ROOT = Path(__file__).resolve().parents[1]
CAPS = (28, 44, 52)
METHODS = frontier.METHODS
PRECHECK = archive.archive.qualify_archived
FIELDS = ('incumbent', 'challenger', 'selected', 'archiveNominee', 'archivePromoted', 'searchSha256')


def qualify_archive_pair(incumbent, challenger, cases, evaluate):
    rows = tuple(Row(str(case), 'task') for case in cases)
    result = certify_paired_qualification(incumbent, challenger, rows,
        lambda prompt, row, _: evaluate(prompt, int(row.id)))
    evidence = [(reply.prompt, int(reply.row_id), reply.passed) for reply in result.observations]
    debit = sum(prompt == challenger for prompt, _, _ in evidence)
    return result.status == 'promoted', debit, evidence


def run_episode(matrix, held, seed, original, plan, method, *, paired):
    chosen = qualify_archive_pair if paired else PRECHECK
    audit = Counter(archiveChecks=0, archiveIncumbentReads=0, archiveChallengerReads=0)

    def qualify(incumbent, challenger, cases, evaluate):
        accepted, debit, evidence = chosen(incumbent, challenger, cases, evaluate)
        expected = sum(matrix[int(challenger)][case] == '1' for case in cases) > sum(
            matrix[int(incumbent)][case] == '1' for case in cases)
        if accepted != expected or debit != sum(prompt == challenger for prompt, _, _ in evidence):
            raise ValueError('Archive check disagrees with the full qualification decision or lookup debit')
        audit.update(archiveChecks=1, archiveIncumbentReads=len(evidence) - debit, archiveChallengerReads=debit)
        return accepted, debit, evidence

    with patch.object(archive.archive, 'qualify_archived', qualify):
        if method == frontier.gepa.CPO:
            total, trace = archive.episode(matrix, held, seed, original, plan, 'recency')
            decisions = [row['decision'] for row in trace]
        else:
            _, total, peak, trace = frontier.gepa.reinvest_episode(
                matrix, held, seed, original, plan, batched=method == frontier.gepa.METHODS[1])
            if peak > plan['searchCap']:
                raise ValueError('A GEPA cycle exceeded its paid search cap')
            decisions = trace
    total.update(audit)
    signature = [{key: row[key] for key in FIELDS} for row in decisions]
    return total, trace, signature


def prepare(phase):
    parent, original, data, source = parents.prepare(phase)
    plan = {
        **{key: parent[key] for key in ('phase', 'validationRows', 'gepaVersion', 'gate', 'costFrontierReportSha256')},
        'protocol': 'cpo-paired-archive-preflight-v1', 'parentPlanSha256': digest(parent),
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'pairedQualifierSha256': sha256((ROOT / 'cpo/paired_qualification.py').read_bytes()).hexdigest(),
        'caps': list(CAPS), 'methods': list(METHODS),
        'primaryGate': ('At cap 52, CPO reproduces every search and promotion decision and uses fewer '
                        'aggregate paid lookups. Uniformly apply the same variant to both GEPA controls.'),
        'scope': ('Use the same strict archive gate, keeping the realized challenger debit and the '
                  'per-cycle caps. Evaluate deterministic archived outcomes only.'),
    }
    return plan, original, data, source


def archived_point(source, phase, method, cap):
    if phase == 'independent':
        if method == frontier.gepa.CPO:
            return source['cpo'][f'seeded-{cap}']
        return source['gepa'][method][str(cap)]
    return source[method][str(cap)]


def replay(plan, original, data, source):
    panels = {}
    for p in data:
        subject, model, matrix = (p[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        caps = {}
        for cap in CAPS:
            settings = {'searchCap': cap, 'validationRows': plan['validationRows']}
            arms = {}
            for method in METHODS:
                costs, traces, changes = (Counter(), Counter()), ([], []), Counter()
                for seed in original['seeds']:
                    base = run_episode(matrix, held, seed, original, settings, method, paired=False)
                    pair = run_episode(matrix, held, seed, original, settings, method, paired=True)
                    for index, (measured, trace, _) in enumerate((base, pair)):
                        costs[index].update(measured)
                        traces[index].append(trace)
                    base_counts, _, base_decisions = base
                    pair_counts, _, pair_decisions = pair
                    base_paid = base_counts['searchPaid'] + base_counts['qualificationPaid']
                    pair_paid = pair_counts['searchPaid'] + pair_counts['qualificationPaid']
                    changes.update(cyclesChanged=sum(a != b for a, b in zip(base_decisions, pair_decisions, strict=True)),
                                   finalsChanged=int(base_decisions[-1]['selected'] != pair_decisions[-1]['selected']),
                                   episodesSaving=int(pair_paid < base_paid), episodesAdding=int(pair_paid > base_paid))
                points = [dict(total, paidLookups=total['searchPaid'] + total['qualificationPaid'],
                               traceSha256=digest(trace)) for total, trace in zip(costs, traces, strict=True)]
                expected = archived_point(source[name], plan['phase'], method, cap)
                if any(points[0][key] != expected[key] for key in ('holdoutPasses', 'paidLookups', 'traceSha256')):
                    raise ValueError(f'{name} {cap} {method} differs from the published reference')
                arms[method] = {'incumbentFirst': points[0], 'paired': points[1], 'changes': dict(changes)}
            gates = {mode: {ref: meets_gate(arms[frontier.gepa.CPO][mode], arms[ref][mode])
                            for ref in frontier.gepa.METHODS} for mode in ('incumbentFirst', 'paired')}
            caps[str(cap)] = {'arms': arms, 'cpoGates': gates}
        panels[name] = caps
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=attribution.PHASES, required=True)
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
    result = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
