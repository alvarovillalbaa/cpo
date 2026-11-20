"""Measure exact terminal validation cost on the published staged repair paths."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_residual_retry as prior
from cpo._contract import digest
from cpo.anchored_validation import certify_validation_gain
from cpo.opening_repair_cycle import _first_proposal


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = '0cd73511836db8a5ee2dccace2c8222d94a9e1eecf1a3ac2b8b9906f34eee5f9'


def measure_cycle(features, measured):
    baseline = prior.retry_cycle(features)

    def run(incumbent, train, validation, holdout, evaluate, propose, **options):
        observed, chain = {}, []
        before_repairs = set()

        def observe(prompt, row):
            reply = evaluate(prompt, row)
            observed[prompt, row.id] = reply.passed
            return reply

        def propose_and_track(parent, *arguments):
            if not chain:
                chain.append(parent)
                before_repairs.update(observed)
            elif chain[-1] != parent:
                raise ValueError('Unexpected repair chain parent')
            result = propose(parent, *arguments)
            candidate = _first_proposal(result)
            if isinstance(candidate, str) and candidate.strip() and candidate not in (incumbent, *chain):
                chain.append(candidate)
            return result

        result = baseline(incumbent, train, validation, holdout, observe, propose_and_track, **options)
        if len(chain) < 2:
            return result

        anchor, final = chain[0], chain[-1]
        event = result.search.events[-1]
        stage = len(chain) - 1
        earlier_rows = {row_id for when, row_id, _ in event.get('residualChecks', ()) if when == stage}
        cached = {row.id: observed[final, row.id] for row in validation
                  if row.id in earlier_rows or (final, row.id) in before_repairs}
        anchor_passes = {row.id: observed[anchor, row.id] for row in validation}
        final_reads = [row_id for prompt, row_id in observed
                       if prompt == final and row_id in anchor_passes and row_id not in cached]
        expected_reads = [row.id for row in validation if row.id not in cached]
        if final_reads != expected_reads:
            raise ValueError('The terminal read sequence does not match the measured repair path')

        reads = []

        def reveal(row):
            reads.append(row.id)
            return observed[final, row.id]

        accepted = certify_validation_gain(validation, anchor_passes, reveal, known=cached)
        if accepted != (event['status'] == 'accepted') or result.search.prompt != (final if accepted else anchor):
            raise ValueError('The certificate changed the full terminal validation decision')
        measured.update({'terminalValidations': 1, 'accepted': accepted, 'originalReads': len(final_reads),
                         'certificateReads': len(reads), 'cachedBeforeTerminal': len(cached)})
        return result

    return run


def measure_trial(task, profile, seed, groups, measured):
    source, typed = prior.SOURCE, prior.TYPED
    with (patch.object(typed, 'FAMILY_FIELD', {key: value[0][0] for key, value in source.TASKS.items()}),
          patch.object(typed.fixture, 'respond', lambda request: source.opening(profile, request)),
          patch.object(typed.programs, 'complete', source.complete),
          patch.object(typed.feedback, 'observed_repair', source.repair)):
        cycle = measure_cycle(source.feature_map(task, groups, True), measured)
        return source.diagnostic.rerun_repair(task, groups, seed, source.CAP, cycle)


def prepare():
    source, cohorts, _ = prior.prepare()
    baseline = prior.checked_file('docs/opening-residual-retry-results-v1.json', REFERENCE)
    if digest(source) != baseline['designSha256']:
        raise ValueError('The published retry comparison design changed')
    names = ('benchmarks/opening_validation_certificate.py', 'cpo/anchored_validation.py')
    plan = {'protocol': 'cpo-opening-validation-certificate-v1', 'baselineReportSha256': REFERENCE,
            'baselineDesignSha256': digest(source),
            'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in names}}
    return plan, cohorts, baseline['results']['phases']


def measure(cohorts, baseline):
    result = {}
    for phase, panels in cohorts.items():
        result[phase] = {}
        for mode in ('held-out', 'shifted-exceptions'):
            totals, work, by_panel = Counter(), Counter(), {}
            reference = baseline[phase][mode]
            for name, (original, alternate, shifted) in panels.items():
                task, profile, seed = name.split('/')
                measured = Counter()
                if mode == 'held-out':
                    arm = measure_trial(task, profile, int(seed), original, measured)
                else:
                    with patch.object(prior.SOURCE, 'FAULTS', shifted):
                        arm = measure_trial(task, profile, int(seed), alternate, measured)
                totals.update({key: arm[key] for key in ('searchLookups', 'qualificationLookups', 'proposalCalls',
                                                        'nominated', 'promoted')})
                totals['holdoutPasses'] += sum(arm['holdout'].values())
                work.update(measured)
                if measured:
                    by_panel[name] = dict(measured)
            totals['countedCalls'] = sum(totals[key] for key in ('searchLookups', 'qualificationLookups', 'proposalCalls'))
            if totals != reference['totals'][prior.PRIMARY]:
                raise ValueError(f'The published CPO totals changed for {phase}/{mode}')
            saved = work['originalReads'] - work['certificateReads']
            result[phase][mode] = {'original': dict(totals), 'terminal': dict(work), 'byPanel': by_panel,
                                   'lookupsSaved': saved, 'certifiedCountedCalls': totals['countedCalls'] - saved,
                                   'gepaCountedCalls': {arm: reference['totals'][arm]['countedCalls']
                                                        for arm in prior.TYPED.GEPA}}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, cohorts, baseline = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(seal)
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Use the current seal and a fresh output path')
    report = {'design': plan, 'designSha256': seal, 'results': measure(cohorts, baseline)}
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
