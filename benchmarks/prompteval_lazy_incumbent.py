"""Measure deferred incumbent reads with exact nomination and promotion replay."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_archive_cycles as archive
from benchmarks import prompteval_paid_witness as paid
from benchmarks import prompteval_screen_coverage_rotation as rotation
from benchmarks import prompteval_single_finalist as first
from benchmarks.prompteval_validation_transfer import CPO, paired
from cpo._contract import digest, unique_object
from cpo.lazy_incumbent import select_with_lazy_incumbent


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '2bcaddf44cfd682035c78721af40e9477e1e9bbd12ec91d177fef49348ac192f'
POLICIES = {
    'deferred-first-gain': (False, False, 'first-gain'),
    'deferred-rotation': (True, False, 'rotate-misses'),
    'paired-rotation': (True, True, 'rotate-misses'),
}
DECISIONS = ('incumbent', 'challenger', 'selected', 'archiveNominee', 'archivePromoted', 'qualification')


def measured_episode(matrix, held, seed, original, rotate, paired_proof):
    def select(incumbent, candidates, validation, evaluate, *, metric_limit, screen):
        if screen != 'first-gain':
            raise ValueError('Deferral requires an original first-gain screen')
        return select_with_lazy_incumbent(incumbent, candidates, validation, evaluate,
                                          metric_limit=metric_limit, rotate_misses=rotate, paired_proof=paired_proof)

    with patch.object(first, 'select_single_finalist', select):
        return first.screened_episode(matrix, held, seed, original, 'first-gain')[CPO]


def prepare(phase):
    raw = (ROOT / 'docs/prompteval-coverage-rotation-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('The archived coverage replay differs')
    stored = json.loads(raw, object_pairs_hook=unique_object)['runs'][phase]['report']
    parent, original, source, first_gain = rotation.prepare(phase)
    if digest(parent) != stored['planSha256']:
        raise ValueError('The archived coverage seal differs')
    plan = {
        'protocol': 'cpo-prompteval-lazy-incumbent-v1', 'phase': phase, 'parentPlanSha256': digest(parent),
        'parentReportSha256': SOURCE_SHA256, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'selectorSha256': sha256((ROOT / 'cpo/lazy_incumbent.py').read_bytes()).hexdigest(),
        'pairedProofSha256': sha256((ROOT / 'cpo/paired_qualification.py').read_bytes()).hexdigest(),
        'gepaVersion': parent['gepaVersion'], 'rowsAndCap': parent['rowsAndCap'], 'gate': parent['gate'],
        'scope': 'Preserve CPO nominations and promotions. Measure deferral and paired proof order with fixed controls.',
        'policies': {policy: {'rotateMisses': rotate, 'pairedProof': pair, 'reference': reference}
                     for policy, (rotate, pair, reference) in POLICIES.items()},
    }
    return plan, original, source, stored['panels'], first_gain


def accounting(current, reference, paired_proof):
    if current['candidate'] != reference['candidate'] or current['holdoutPasses'] != reference['holdoutPasses']:
        raise ValueError('Deferral changed the final prompt or holdout score')
    result = Counter()
    for original, measured in zip(reference['steps'], current['steps'], strict=True):
        if any(original[key] != measured[key] for key in DECISIONS):
            raise ValueError('Deferral changed a nomination, archive decision, or qualification')
        reports = [step.get('validationByCandidate', {}) for step in (original, measured)]
        old_inc, new_inc = (r.get('incumbent', 0) for r in reports)
        old_total, new_total = (sum(r.values()) for r in reports)
        if old_total != original['searchLookups'] or new_total != measured['searchLookups']:
            raise ValueError('The accounted validation costs differ from the paid journal')
        incumbent_savings = old_inc - new_inc
        challenger_savings = (old_total - old_inc) - (new_total - new_inc)
        if not paired_proof and (incumbent_savings < 0 or challenger_savings != 0):
            raise ValueError('Eager-order deferral changed challenger cost or added incumbent replies')
        result.update(incumbentLookupsSaved=incumbent_savings, challengerLookupsSaved=challenger_savings,
                      cyclesSavingLookups=int(new_total < old_total),
                      cyclesAddingLookups=int(new_total > old_total))
    if result['incumbentLookupsSaved'] + result['challengerLookupsSaved'] != (
            reference['evaluations'] - current['evaluations']):
        raise ValueError('The total savings differ from the phase ledger')
    return result


def replay(plan, original, source, archived, first_gain):
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held, seeds = original['holdoutCaseIDs'][subject], original['seeds']
        baseline = [first.screened_episode(matrix, held, seed, original, 'first-gain') for seed in seeds]
        traces = {method: [episode[method] for episode in baseline] for method in first.METHODS}
        known_totals = {m: first.totals(trace) for m, trace in traces.items()}
        if (known_totals != archived[name]['baseline'] or
                digest(traces[CPO]) != first_gain[name]['baselineFirstGainTraceSha256']):
            raise ValueError('Baseline or control drift relative to the published replay')
        candidates = {}
        with patch.object(archive, 'METHODS', archive.METHODS[:1]):
            eager = [rotation.measured_episode(matrix, held, seed, original, 'rotate-misses', Counter())[CPO]
                     for seed in seeds]
            if digest(eager) != archived[name]['candidates']['rotate-misses']['traceSha256']:
                raise ValueError('The measured rotation does not reproduce its archived decisions and costs')
            references = {'first-gain': traces[CPO], 'rotate-misses': eager}
            for policy, (rotate, pair, reference) in POLICIES.items():
                trace = [measured_episode(matrix, held, seed, original, rotate, pair) for seed in seeds]
                savings = Counter()
                for current, previous in zip(trace, references[reference], strict=True):
                    savings.update(accounting(current, previous, pair))
                candidates[policy] = {'totals': first.totals(trace), 'reference': reference, 'savings': dict(savings),
                                      'traceSha256': digest(trace),
                                      'comparisons': {m: paired(trace, traces[m]) for m in first.METHODS[1:]}}
        panels[name] = {'original': {**known_totals, 'rotate-misses': first.totals(eager)}, 'candidates': candidates}
    qualified = {policy: [name for name, panel in panels.items() if all(
        panel['candidates'][policy]['comparisons'][m]['qualified'] for m in first.METHODS[1:])]
                 for policy in POLICIES}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels, 'panelsClearingBothGates': qualified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=paid.PHASES, required=True)
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
