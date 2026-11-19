"""Test bounded paired qualification of a second archive challenger."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_archive_restart as restart, recorded_archive_screen as screened
from cpo import Observation, Row
from cpo._contract import digest
from cpo.challenger import certify_challenger


SEEDS = tuple(range(74701, 75917, 19))
PRIMARY = 'cpo-paired-qualification'
POLICIES = ('cpo-rescue', PRIMARY)


def nominate(head, incumbent, order, seen, paid, validation, evaluate, *, evaluation_limit, proposal_limit):
    """Admit one recorded candidate that preserves every head validation pass."""
    journal = dict(paid)
    evaluations = 0
    proposed = []

    def observe(candidate, row):
        nonlocal evaluations
        key = candidate, row.id
        if key not in journal:
            if evaluations >= evaluation_limit:
                raise ValueError('Nomination exceeded its search allowance')
            journal[key] = evaluate(candidate, row)
            evaluations += 1
        return journal[key].passed

    required = sum((head, row.id) not in paid for row in validation)
    if required > evaluation_limit:
        return None, 0, []
    preserved = [row for row in validation if observe(head, row)]
    for candidate in order:
        if candidate in (head, incumbent):
            continue
        missing = [row for row in preserved if (candidate, row.id) not in journal]
        known_loss = any(not journal[candidate, row.id].passed for row in preserved if (candidate, row.id) in journal)
        if known_loss or len(missing) > evaluation_limit - evaluations:
            continue
        charge = candidate not in seen
        if charge and len(proposed) >= proposal_limit:
            continue
        if charge:
            proposed.append(candidate)
        if all(observe(candidate, row) for row in missing):
            return candidate, evaluations, proposed
    return None, evaluations, proposed


def qualification(incumbent, head, alternate, rows, evaluate, *, metric_limit, paired):
    challengers = tuple(dict.fromkeys(prompt for prompt in (head, alternate) if prompt and prompt != incumbent))
    if not challengers:
        return incumbent, 0, []
    if metric_limit < len(rows):
        return incumbent, 0, []
    base = {row.id: evaluate(incumbent, row).passed for row in rows}
    spent = len(rows)
    attempts = []
    winners = []
    complete_pair = paired and len(challengers) == 2 and metric_limit >= 3 * len(rows)
    limit = metric_limit if complete_pair else min(metric_limit, 2 * len(rows))

    def already_measured(_):
        raise ValueError('Paired qualification already measured the full panel')

    for challenger in challengers:
        if complete_pair:
            observed = {row.id: evaluate(challenger, row).passed for row in rows}
            result = certify_challenger(rows, base, already_measured, metric_limit=0, observed=observed)
            cost = len(rows)
        else:
            def observe(row):
                return evaluate(challenger, row)

            result = certify_challenger(rows, base, observe, metric_limit=limit - spent)
            cost = result.evaluations
        spent += cost
        attempts.append({'prompt': challenger, 'evaluations': cost, 'status': result.status,
                         'observations': result.observations})
        if result.status == 'promote':
            winners.append((result.lower_pass_bound, challenger))
            if not complete_pair:
                break
    selected = max(winners, key=lambda item: item[0])[1] if winners else incumbent
    return selected, spent, attempts


def search_prefix(data, seed, plan, run_gepa):
    visible, proposed = {}, set()
    existing_search, existing_screen, existing_run = restart.search, screened.screen, restart.run_cpo

    def capture_search(initial, train, validation, evaluate, propose, **settings):
        def measured(prompt, row):
            value = evaluate(prompt, row)
            visible[prompt, row.id] = value
            return value

        return existing_search(initial, train, validation, measured, propose, **settings)

    def capture_prefix(*args, **kwargs):
        result = existing_run(*args, **kwargs)
        proposed.update(code for _, code in result[2])
        return result

    def capture_screen(champion, candidates, observations, validation, evaluate, **settings):
        def measured(prompt, row):
            value = evaluate(prompt, row)
            visible[prompt, row.id] = value
            return value

        result = existing_screen(champion, candidates, observations, validation, measured, **settings)
        proposed.update(attempt['prompt'] for attempt in result[2])
        return result

    with patch.object(restart, 'search', capture_search), patch.object(restart, 'run_cpo', capture_prefix), \
            patch.object(screened, 'screen', capture_screen), \
            patch.object(screened, 'SCREENS', {screened.PRIMARY: screened.SCREENS[screened.PRIMARY]}):
        trial = screened.compare(data, seed, plan, run_gepa)
    return trial, visible, proposed


def compare(data, seed, plan, run_gepa):
    (root, metadata, matrix, original, _), graph, incumbent, _ = data
    order = sorted(metadata)
    Random(seed).shuffle(order)
    validation, promotion, holdout = (order[start:start + 3] for start in (3, 6, 9))
    candidate_graph, earlier = restart.proposal_graph(graph, root, incumbent, seed, 'mixed')
    trial, paid, seen = search_prefix(data, seed, plan, run_gepa)
    baseline = trial['arms'][screened.PRIMARY]
    head = baseline['challenger']
    if len(paid) != baseline['searchEvaluations']:
        raise ValueError('Search prefix accounting disagrees with the captured observations')
    head_calls = baseline['searchEvaluations']
    head_slots = baseline['proposalSlots']

    def evaluate(prompt, row):
        return Observation(matrix[prompt][row.id][0], {})

    alternatives = candidate_graph.get(incumbent, ())
    val_rows = [Row(case, 'task', metadata[case]['critical']) for case in validation]
    # A perfect recorded panel contains no strict validation gain over the deployed incumbent.
    eligible = any((incumbent, case) not in paid or not paid[incumbent, case].passed for case in validation)
    second, nomination_calls, nominations = (nominate(
        head, incumbent, alternatives, seen, paid, val_rows, evaluate,
        evaluation_limit=plan['metricLimit'] - head_calls, proposal_limit=plan['proposalSlots'] - head_slots)
        if eligible else (None, 0, []))
    first_stage_cost = head_calls + nomination_calls
    slots = head_slots + len(nominations)
    qual_rows = [Row(case, 'task', metadata[case]['critical']) for case in promotion]
    combined_limit = plan['metricLimit'] + 2 * len(qual_rows)

    for arm in POLICIES:
        if second is None:
            chosen, cost, receipts = baseline['chosen'], baseline['qualificationEvaluations'], []
        else:
            mode_limit = (min(3 * len(qual_rows), combined_limit - first_stage_cost)
                          if arm == PRIMARY else 2 * len(qual_rows))
            chosen, cost, receipts = qualification(incumbent, head, second, qual_rows, evaluate,
                                                    metric_limit=mode_limit, paired=arm == PRIMARY)
        if first_stage_cost + cost > combined_limit or slots > plan['proposalSlots']:
            raise ValueError('Qualification exceeded the combined budget')
        trial['arms'][arm] = {
            **baseline, 'chosen': chosen, 'calls': first_stage_cost + slots + cost,
            'searchEvaluations': first_stage_cost, 'proposalSlots': slots,
            'archiveLookups': baseline['archiveLookups'] + sum(prompt in earlier for prompt in nominations),
            'qualificationEvaluations': cost, 'promotion': 'promote' if chosen != incumbent else 'retain',
            'outcomes': {case: matrix[chosen][case][0] for case in holdout},
            'originalHoldout': {case: value[0] for case, value in original.get(chosen, {}).items()},
            'second': second, 'nominationEvaluations': nomination_calls, 'nominationProposals': nominations, 'attempts': receipts}
    return trial


def summarize(trials):
    with patch.object(restart, 'PRIMARY', PRIMARY):
        result = restart.summarize(trials)
    for arm in POLICIES:
        rows = [trial['arms'][arm] for trial in trials]
        baseline = [trial['arms'][screened.PRIMARY]['chosen'] for trial in trials]
        result['totals'][arm].update(nominated=sum(row['second'] is not None for row in rows),
                                     actualComparisons=sum(len(row['attempts']) == 2 for row in rows),
                                     changes=sum(row['chosen'] != old for row, old in zip(rows, baseline)),
                                     secondPromotions=sum(row['chosen'] == row['second'] for row in rows),
                                     nominationEvaluations=sum(row['nominationEvaluations'] for row in rows))
    return result


def prepare():
    plan, data, run_gepa = screened.prepare()
    earlier = digest(plan)
    path = Path(__file__)
    plan['sourceSha256']['benchmarks/recorded_archive_qualification.py'] = sha256(path.read_bytes()).hexdigest()
    return {**plan, 'protocol': 'cpo-recorded-archive-qualification-v1', 'screenPlanSha256': earlier,
            'seeds': list(SEEDS), 'policies': list(POLICIES), 'primary': PRIMARY,
            'maximumCombinedEvaluations': plan['metricLimit'] + 6,
            'sharedIncumbentQualification': True}, data, run_gepa


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, run_gepa = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    results = {task: summarize([compare(inputs, seed, plan, run_gepa) for seed in plan['seeds']])
               for task, inputs in sorted(data.items())}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
