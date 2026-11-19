"""Choose a first-gain witness from validation outcomes the episode already paid for."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import episode_screen_adaptation as screens
from benchmarks.prompteval_paid_witness import meets_gate
from cpo._contract import digest
from cpo.fixed_pool_cycle import run_fixed_pool_cycle


POLICIES = ('seeded', 'known-miss', 'one-prior-pass', 'two-prior-passes')
PASS_THRESHOLD = {'known-miss': 0, 'one-prior-pass': 1, 'two-prior-passes': 2}


def choose_witness(incumbent, validation, history, policy):
    """Prefer a current validation row with a known miss and enough prior passes."""
    if policy == 'seeded':
        return None
    threshold = PASS_THRESHOLD[policy]
    eligible = []
    for row in validation:
        outcomes = history.get(row.id, {})
        if outcomes.get(incumbent) is not False:
            continue
        passes = sum(outcomes.values())  # The incumbent's known miss contributes zero.
        if passes >= threshold:
            score = Fraction(passes + 1, len(outcomes) + 1) if threshold else 0
            eligible.append((score, row))
    return max(eligible, key=lambda item: item[0], default=(None, None))[1]


def run_episode(matrix, held, seed, original, plan, policy):
    history, choices = {}, []
    counts = Counter(freshCycles=0, eligibleCycles=0, movedWitness=0, finalists=0)

    def select(incumbent, candidates, validation, qualification, evaluate, **kwargs):
        witness = choose_witness(incumbent, validation, history, policy)
        counts.update(freshCycles=1, eligibleCycles=int(witness is not None),
                      movedWitness=int(witness is not None and witness != validation[0]))
        choices.append(witness.id if witness is not None else None)
        if witness is not None:
            validation = (witness, *(row for row in validation if row != witness))

        def observe(prompt, row):
            reply = evaluate(prompt, row)
            if history.setdefault(row.id, {}).setdefault(prompt, reply.passed) is not reply.passed:
                raise ValueError('Exact cached validation outcomes must agree')
            return reply

        result = run_fixed_pool_cycle(incumbent, candidates, validation, qualification, observe, **kwargs)
        counts['finalists'] += int(result.search.finalist is not None)
        return result

    with patch.object(archive, 'run_fixed_pool_cycle', select):
        totals, journal = archive.episode(matrix, held, seed, original, plan, 'recency')
    return totals + counts, journal, choices


def prepare(phase):
    parent, original, data, gepa, fixed = archive.prepare(phase)
    plan = {
        **{k: parent[k] for k in ('phase', 'gepaReportSha256', 'fixedPoolReportSha256', 'gepaVersion',
                                'searchCap', 'validationRows', 'gate')},
        'protocol': 'cpo-cached-miss-witness-v1', 'archivePlanSha256': digest(parent),
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'pairedComparisonSourceSha256': sha256(Path(screens.__file__).read_bytes()).hexdigest(),
        'policies': list(POLICIES), 'priorPassThresholds': PASS_THRESHOLD, 'primary': 'one-prior-pass',
        'scope': ('Select a current validation row before fresh search using only earlier validation replies '
                  'from that episode. Keep candidate order, qualification, archive, and ceilings fixed.'),
    }
    return plan, original, data, gepa, fixed


def replay(plan, original, data, gepa, fixed):
    panels = {}
    for panel in data:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        variants, passes = {}, {}
        for policy in POLICIES:
            total, journals, choices = Counter(), [], []
            passes[policy] = []
            for seed in original['seeds']:
                result, journal, choice = run_episode(matrix, held, seed, original, plan, policy)
                total.update(result)
                journals.append(journal)
                choices.append(choice)
                passes[policy].append(result['holdoutPasses'])
            variants[policy] = {
                **{k: total[k] for k in ('holdoutPasses', 'searchLogical', 'searchPaid', 'qualificationPaid',
                                         'freshCycles', 'eligibleCycles', 'movedWitness', 'finalists')},
                'paidLookups': total['searchPaid'] + total['qualificationPaid'],
                'traceSha256': digest(journals), 'choicesSha256': digest(choices),
                'pairedPassesVsSeeded': screens.paired_deltas(passes[policy], passes['seeded']),
            }
        observed, expected = variants['seeded'], fixed[name][screens.DEFERRED]
        if (observed['traceSha256'] != expected['callbackTraceSha256'] or any(
                observed[key] != expected['totals'][original_key] for key, original_key in
                (('searchLogical', 'searchLookups'), ('searchPaid', 'searchAfterReuse'),
                 ('qualificationPaid', 'qualificationAfterStop'), ('holdoutPasses', 'holdoutPasses'),
                 ('paidLookups', 'paidLookups')))):
            raise ValueError(f'{name} differs from the published static CPO control')
        controls = {method: {k: result[k] for k in ('holdoutPasses', 'paidLookups')}
                    for method, result in gepa[name]['reinvested'].items()}
        gates = {policy: {mode: meets_gate(result, control) for mode, control in controls.items()}
                 for policy, result in variants.items()}
        panels[name] = {'policies': variants, 'gepa': controls, 'gates': gates}
    qualified = {p: [name for name, row in panels.items() if all(row['gates'][p].values())] for p in POLICIES}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels, 'panelsClearingBothGates': qualified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=archive.controls.reference.transfer.SOURCES, required=True)
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
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
