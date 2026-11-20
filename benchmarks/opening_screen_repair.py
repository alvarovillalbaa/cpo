"""Test a single funded repair after the opening screen finds validation errors."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_screen_typed as prior
from benchmarks.case_difficulty_allocation import checked_file
from cpo._contract import digest
from cpo.expected_cost_proposal_cycle import ExpectedCostProposalCycleResult
from cpo.opening_screen_cycle import run_opening_screen_cycle
from cpo.optimizer import balanced_order
from cpo.paired_qualification import certify_paired_qualification


REFERENCE = '4183804b13f86da23aca78e8af4bb98868225994128b32c78b82a560e2a485aa'
POLICIES = {'repair-two': 2, 'repair-four': 4}
PRIMARY = 'repair-two'


def staged_cycle(max_probes):
    def run(incumbent, train, validation, holdout, evaluate, propose, *, metric_limit, rounds, train_per_round,
            opening_pair, qualify, seed, field_credit, repeats):
        ledger = {}

        def observe(prompt, row):
            key = prompt, row.id
            if key not in ledger:
                if len(ledger) >= metric_limit:
                    raise ValueError('The staged cycle exceeded the paid search ceiling')
                ledger[key] = evaluate(prompt, row)
            return ledger[key]

        def forbidden(*_args):
            raise ValueError('Only the final nominee may dispatch qualification')

        opening = run_opening_screen_cycle(
            incumbent, train, validation, holdout, observe, opening_pair=opening_pair,
            metric_limit=metric_limit, qualify=forbidden, seed=seed, field_credit=field_credit,
            repeats=repeats, qualification_limit=0)
        result = opening.search
        parent = result.prompt
        if parent == incumbent:
            return ExpectedCostProposalCycleResult(result, None)
        reflections = 0
        status = 'validation-complete'
        candidate = parent
        if any(not ledger[parent, row.id].passed for row in validation):
            probes = min(max_probes, len(train), metric_limit - len(ledger) - len(validation))
            status = 'unfunded'
            if probes > 0:
                examples = [(row, observe(parent, row)) for row in balanced_order(train, seed)[:probes]]
                status = 'no-training-error'
                if any(not reply.passed for _, reply in examples):
                    repaired = propose(parent, examples, [], 1).rewrite
                    reflections = 1
                    status = 'duplicate'
                    if repaired not in (incumbent, parent):
                        gains = Counter()
                        critical_loss = False
                        for row in validation:
                            old = ledger[parent, row.id].passed
                            new = observe(repaired, row).passed
                            critical_loss |= row.critical and old and not new
                            gains[row.family] += new - old
                        accepted = not critical_loss and min(gains.values()) >= 0 and sum(gains.values()) > 0
                        status = 'accepted' if accepted else 'rejected'
                        candidate = repaired if accepted else parent
        events = [*result.events, {'kind': 'targeted-repair', 'prompt': candidate,
                                   'status': status, 'addedLookups': len(ledger) - result.evaluations}]
        result = replace(result, prompt=candidate, evaluations=len(ledger), reflections=reflections, events=events)
        decision = certify_paired_qualification(incumbent, candidate, holdout, qualify, repeats=repeats, seed=seed)
        return ExpectedCostProposalCycleResult(result, decision)

    return run


def run_trials(design, cohorts, published):
    results = {}
    for cap in design['searchCaps']:
        all_trials = [prior.trial(task, groups, seed, cap)
                      for seed, tasks in cohorts.items() for task, groups in tasks.items()]
        frozen = published[str(cap)]
        if all_trials != frozen['trials'] or prior.summary(all_trials) != {
                key: frozen[key] for key in ('totals', 'comparisons')}:
            raise ValueError('A published typed search, score, or accounting trace changed')
        for t in all_trials:
            seed, task = t['seed'], t['task']
            for label, probes in POLICIES.items():
                with (patch.object(prior, 'ARMS', (prior.CPO[1],)),
                      patch.object(prior, 'run_expected_cost_proposal_cycle', staged_cycle(probes))):
                    repaired = prior.trial(task, cohorts[seed][task], seed, cap)
                t['arms'][label] = repaired['arms'][prior.CPO[1]]
        with (patch.object(prior, 'ARMS', (*prior.ARMS, *POLICIES)),
              patch.object(prior, 'CPO', (PRIMARY, 'cpo-adaptive'))):
            measured = prior.summary(all_trials)
        repair_trials = [{**t, 'arms': {arm: t['arms'][arm] for arm in POLICIES}} for t in all_trials]
        results[str(cap)] = {**measured, 'repairTrials': repair_trials,
                             'verifiedReferencePanelPaths': len(all_trials) * len(prior.ARMS)}
    return results


def prepare():
    parent, cohorts = prior.prepare()
    frozen = checked_file('docs/opening-screen-typed-results-v1.json', REFERENCE)
    if digest(parent) != frozen['designSha256']:
        raise ValueError('The published typed benchmark design changed')
    design = {'protocol': 'cpo-opening-screen-repair-v1', 'referenceReportSha256': REFERENCE,
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'searchCaps': parent['searchCaps'], 'primaryCap': parent['primaryCap'],
              'primary': PRIMARY, 'trainingProbeCaps': POLICIES, 'laterProposalCap': 1,
              'gepaVersion': parent['gepaVersion'], 'gate': parent['gate'],
              'scope': ('Keep the opening nominee when all validation cases pass. Otherwise fund one repair '
                        'and complete its validation if training reveals errors. Qualify only the final nominee.')}
    return design, cohorts, frozen['results']


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, cohorts, published = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        cli.error('Use GEPA 0.1.4')
    report = {'design': design, 'designSha256': seal, 'results': run_trials(design, cohorts, published)}
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
