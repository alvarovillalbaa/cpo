"""Test one extra funded repair on incomplete opening improvements."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_repair_policy_transfer as source
from benchmarks.case_difficulty_allocation import checked_file
from cpo._contract import digest
from cpo.expected_cost_proposal_cycle import ExpectedCostProposalCycleResult
from cpo.opening_repair_cycle import run_opening_repair_cycle
from cpo.optimizer import balanced_order
from cpo.paired_qualification import certify_paired_qualification


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = '64e41a917886c1448c112137bcca69037182135a0279c0521433483cc982a30c'
PRIMARY = 'second-repair'
PROBES = 2


def second_repair_cycle(incumbent, train, validation, holdout, evaluate, propose, *, opening_pair,
                        metric_limit, qualify, seed, field_credit, repeats, rounds, train_per_round):
    ledger = {}

    def observe(prompt, row):
        key = prompt, row.id
        if key not in ledger:
            if len(ledger) >= metric_limit:
                raise ValueError('The second repair exceeded the search ceiling')
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Search requires an exact boolean outcome')
            ledger[key] = reply
        return ledger[key]

    def deferred(*_):
        raise ValueError('Only the final nominee can qualify')

    once = run_opening_repair_cycle(
        incumbent, train, validation, holdout, observe, propose, opening_pair=opening_pair,
        metric_limit=metric_limit, qualify=deferred, diagnostic_prompt=source.api.strip_demonstrations,
        max_training_probes=PROBES, seed=seed, field_credit=field_credit, repeats=repeats, qualification_limit=0,
    )
    result = once.search
    parent = result.prompt
    if parent == incumbent:
        return once

    candidate, calls, status = parent, result.reflections, 'first-repair-not-accepted'
    if result.events[-1]['status'] == 'accepted':
        status = 'validation-complete'
        if any(not ledger[parent, row.id].passed for row in validation):
            used = {probe['row_id'] for probe in result.events[-1]['probes']}
            distinct = [row for row in balanced_order(train, seed) if row.id not in used]
            funded = min(PROBES, len(distinct), metric_limit - len(ledger) - len(validation))
            status = 'unfunded'
            if funded > 0:
                diagnostic = source.api.strip_demonstrations(parent)
                feedback = [(row, observe(diagnostic, row)) for row in distinct[:funded]]
                status = 'no-training-error'
                if any(not reply.passed for _, reply in feedback):
                    repair = propose(parent, feedback, [], 1).rewrite
                    calls += 1
                    status = 'duplicate'
                    if repair not in (incumbent, parent):
                        gains = Counter()
                        critical_loss = False
                        for row in validation:
                            previous = ledger[parent, row.id].passed
                            current = observe(repair, row).passed
                            critical_loss |= row.critical and previous and not current
                            gains[row.family] += current - previous
                        accepted = not critical_loss and min(gains.values()) >= 0 and sum(gains.values()) > 0
                        candidate = repair if accepted else parent
                        status = 'accepted' if accepted else 'rejected'
    event = {'kind': PRIMARY, 'status': status, 'addedLookups': len(ledger) - result.evaluations}
    result = replace(result, prompt=candidate, evaluations=len(ledger), reflections=calls,
                     events=[*result.events, event])
    decision = certify_paired_qualification(incumbent, candidate, holdout, qualify, repeats=repeats, seed=seed)
    return ExpectedCostProposalCycleResult(result, decision)


def prepare():
    parent, panels = source.prepare()
    previous = checked_file('docs/opening-repair-policy-transfer-results-v1.json', REFERENCE)
    if digest(parent) != previous['designSha256']:
        raise ValueError('The published policy transfer changed')
    design = {'protocol': 'cpo-opening-second-repair-v1', 'referenceReportSha256': REFERENCE,
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'searchCap': parent['searchCap'], 'gepaVersion': parent['gepaVersion'],
              'primary': PRIMARY, 'gate': parent['gate'], 'laterProposalCap': 2, 'probesPerRepair': PROBES,
              'scope': ('Fund a second repair only after an accepted first repair leaves validation errors. '
                        'Use other training rows and qualify once against the original incumbent.')}
    return design, panels, previous['results']


def measure(panels, frozen):
    typed = source.typed
    summarize = typed.summary
    references = []

    def capture(trials):
        if len(trials) == len(panels):
            references.extend(trials)
        return summarize(trials)

    with patch.object(typed, 'summary', capture):
        if source.measure(panels) != frozen:
            raise ValueError('The earlier transfer outcomes or trace changed')

    for item in references:
        task, seed, profile = item['task'], item['seed'], item['profile']
        groups = panels[f'{task}/{profile}/{seed}']
        with (patch.object(typed, 'FAMILY_FIELD', {key: data[0][0] for key, data in source.TASKS.items()}),
              patch.object(typed.fixture, 'respond', source.opening_response(profile)),
              patch.object(typed.programs, 'complete', source.complete),
              patch.object(typed.feedback, 'observed_repair', source.repair_response)):
            point = source.diagnostic.rerun_repair(task, groups, seed, source.CAP, second_repair_cycle)
        baseline = item['arms'][source.PRIMARY]
        if point['events'][-1]['kind'] == PRIMARY and point['events'][-1]['addedLookups'] == 0:
            if {**point, 'events': point['events'][:-1]} != baseline:
                raise ValueError('An unused second repair changed the first-repair trace')
        item['arms'][PRIMARY] = point

    with (patch.object(typed, 'ARMS', (*typed.ARMS, 'repair-two', source.PRIMARY, PRIMARY)),
          patch.object(typed, 'CPO', (PRIMARY, 'cpo-adaptive'))):
        results = typed.summary(references)
        results['profiles'] = {profile: typed.summary([t for t in references if t['profile'] == profile])
                               for profile in source.PROFILES}
    results['statuses'] = dict(Counter(
        next((event['status'] for event in t['arms'][PRIMARY]['events'] if event['kind'] == PRIMARY),
             'no-opening-nominee') for t in references))
    results['traceSha256'] = digest(references)
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, panels, frozen = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        cli.error('Use GEPA 0.1.4')
    result = {'design': design, 'designSha256': seal, 'results': measure(panels, frozen)}
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
