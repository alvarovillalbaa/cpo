"""Bound the fallback's new lookups and avoid grades halving does not need."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from random import Random

from benchmarks import pool
from benchmarks import prompteval_witness_fallback as transfer
from benchmarks import promptolution_witness_episode as episode
from cpo import Row
from cpo._contract import digest
from cpo.halving import HalvingSearch
from cpo.paired_qualification import certify_paired_qualification


CAPS = (4, 8, 12, 16, 24, 32)
PLAIN, CERTIFIED = 'plain', 'certified'
REFERENCE = {
    'docs/promptolution-witness-fallback-results-v1.json': '5fde4bdad8e2710a70bad119b2d7791387e2880b7399e4b8b5285f033ba3f68f',
    'docs/prompteval-witness-fallback-results-v1.json': '5fc91d84659e5bb1a5ac4d2c99a9362e5ad45f0d731414f1bec53bd7996fea03',
}


def prepare():
    references = []
    for name, fingerprint in REFERENCE.items():
        raw = (episode.ROOT / name).read_bytes()
        if sha256(raw).hexdigest() != fingerprint:
            raise ValueError('Use the published fallback receipts')
        references.append(json.loads(raw))
    benchmark, *transfer_inputs = transfer.prepare()
    if references[1]['planSha256'] != digest(benchmark):
        raise ValueError('The transfer inputs differ from the recorded fallback')
    names = ('benchmarks/witness_fallback_caps.py', 'benchmarks/promptolution_witness_fallback.py',
             'benchmarks/promptolution_witness_episode.py', 'benchmarks/prompteval_witness_fallback.py',
             'benchmarks/pool.py', 'cpo/halving/__init__.py', 'cpo/paired_qualification.py')
    plan = {'protocol': 'witness-fallback-new-lookup-caps-v1', 'parentReportSha256': REFERENCE,
            'sourceSha256': {name: sha256((episode.ROOT / name).read_bytes()).hexdigest() for name in names},
            'publicPredictionArchiveSha256': episode.CORPUS_SHA, 'extraValidationLookupCaps': CAPS,
            'logicalHalvingCapPerCycle': 8, 'maxAdmissions': 1,
            'budgetRule': 'Charge new fallback validation grades. Retain the start if the next grade cannot be bought.',
            'proofRule': 'A completed nomination funds the original independent paired proof separately.',
            'certificateRule': ('Carry the original cumulative prefixes and tie order. Skip reads only if bounds '
                                'settle the exact ordered survivors.'),
            'scope': 'Replay every published episode and verify full-budget deployments against plain halving.'}
    return plan, references, transfer_inputs


class LookupLimit(Exception):
    """Stop only when the next uncached grade would exceed the fallback budget."""


class PlainHalving:
    def __init__(self, *, metric_limit, paid):
        self.observations = dict(paid)
        self.remaining = metric_limit
        self.evaluations = 0
        self.exhausted = False

    def select(self, prompts, cases, observe):
        if self.exhausted:
            return None

        def read(prompt, case):
            key = prompt, case
            if key not in self.observations:
                if not self.remaining:
                    raise LookupLimit
                self.observations[key] = observe(prompt, case)
                self.remaining -= 1
                self.evaluations += 1
            return self.observations[key]

        try:
            return pool.successive_halving(prompts, cases, read, 8)
        except LookupLimit:
            self.exhausted = True
            return None


def promptolution_trial(matrix, layouts, seed, trial):
    start = episode.START
    for index, (roster, cases, _, proof_cases) in enumerate(layouts):
        score = lambda prompt, case: matrix[prompt][case] == '1'
        nominee = trial.select((start, *roster), cases, score)
        if nominee is None:
            break
        if nominee != start:
            proof_reads = []

            def qualify(prompt, row, _repeat):
                proof_reads.append((prompt, row.id))
                return score(prompt, int(row.id))

            rows = tuple(Row(str(case), 'task') for case in proof_cases)
            proof = certify_paired_qualification(start, nominee, rows, qualify, seed=seed + index)
            return proof.prompt, len(proof_reads)
    return start, 0


def transfer_trial(matrix, held, start, layouts, active, policy, trial):
    def select(incumbent, layout, observe, _limits):
        nominee = trial.select((incumbent, *layout['alternatives']), layout['validation'], observe)
        return incumbent if nominee is None else nominee

    selected, _, _, _, proof = transfer.play(matrix, held, start, layouts, active, policy, select)
    return selected, proof


def measure_fallback(base, base_cases, run, score):
    results, full = {}, {}
    for mode, halving in ((PLAIN, PlainHalving), (CERTIFIED, HalvingSearch)):
        for cap in CAPS:
            trial = halving(metric_limit=cap, paid=base_cases)
            final, proof_reads = run(trial)
            if trial.exhausted and proof_reads:
                raise ValueError('An unfinished search started independent proof')
            results[f'{mode}/{cap}'] = Counter(addedPasses=score(final) - score(base), validationLookups=trial.evaluations,
                                               proofLookups=proof_reads, promotions=int(final != base),
                                               cappedEpisodes=int(trial.exhausted), eligibleEpisodes=1)
            if cap == CAPS[-1]:
                full[mode] = final, proof_reads, set(trial.observations)
                if trial.exhausted:
                    raise ValueError('The full cap must fund every plain and certified path')
    selection, proof, keys = full[CERTIFIED]
    if (selection, proof) != full[PLAIN][:2] or not keys <= full[PLAIN][2]:
        raise ValueError('Certified halving changed the selection, proof, or enrolled lookup scope')
    return results


def execute(plan, corpus, references, transfer_inputs):
    scopes = defaultdict(lambda: defaultdict(Counter))
    baseline = defaultdict(Counter)

    def record(scope, measured):
        for method, totals in measured.items():
            scopes[scope][method].update(totals)

    configuration = episode.prepare()
    for task, bits in corpus.items():
        matrix = bits['correctness']
        held = set(Random(f"{configuration['holdoutSeed']}/{task}").sample(range(300), episode.HOLDOUT))
        for seed in episode.SEEDS:
            layouts = episode.schedule(configuration, task, seed, held)
            selected, totals, trace = episode.play(matrix, layouts, seed, episode.CPO, held)
            score = lambda prompt: sum(matrix[prompt][case] == '1' for case in held)
            baseline[task].update(holdoutPasses=score(selected), paidLookups=totals['paidLookups'])
            if not totals['admissions']:
                run = lambda trial: promptolution_trial(matrix, layouts, seed, trial)
                record(task, measure_fallback(selected, dict(trace['search']), run, score))

    inputs, panels, receipt = transfer_inputs
    active = {**inputs['schedule'], 'evaluationLookupLimit': receipt['plan']['conditions'][transfer.BASE]['searchCap']}
    policy = inputs['qualificationBank']
    for panel in panels:
        subject, matrix = panel['subject'], panel['correctness']
        held = transfer.REPLAY.transfer.holdout(subject, len(matrix[0]))
        for seed in active['seeds']:
            start, layouts = transfer.REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, active)
            selected, paid, _, grades, proof = transfer.play(matrix, held, start, layouts, active, policy, transfer.witness)
            score = lambda prompt: sum(matrix[int(prompt)][case] == '1' for case in held)
            baseline['bbh-lmentry'].update(holdoutPasses=score(selected), paidLookups=paid)
            if not proof:
                run = lambda trial: transfer_trial(matrix, held, start, layouts, active, policy, trial)
                measured = measure_fallback(selected, grades, run, score)
                record('bbh-lmentry', measured)
                record(subject.split('-', 1)[0], measured)

    expected = {task: (row['arms'][episode.CPO], row['arms']['witness-then-halving'])
                for task, row in references[0]['tasks'].items()}
    expected['bbh-lmentry'] = tuple(references[1]['totals'][method] for method in (transfer.BASE, transfer.FALLBACK))
    for scope, (original, full) in expected.items():
        top = scopes[scope][f'{PLAIN}/{CAPS[-1]}']
        if (any(baseline[scope][key] != original[key] for key in ('holdoutPasses', 'paidLookups')) or
                baseline[scope]['holdoutPasses'] + top['addedPasses'] != full['holdoutPasses'] or
                baseline[scope]['paidLookups'] + top['validationLookups'] + top['proofLookups'] != full['paidLookups']):
            raise ValueError('Plain full-budget replay differs from the published fallback')
    for points in scopes.values():
        for totals in points.values():
            totals['addedLookups'] = totals['validationLookups'] + totals['proofLookups']
    return {'plan': plan, 'planSha256': digest(plan), 'baseline': baseline, 'fallbackDeltas': scopes,
            'verifiedFullBudgetParity': True, 'newProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, references, transfer_inputs = prepare()
    seal = digest(plan)
    if args.corpus is None and args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.corpus is None or args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the pinned archive, current seal, and a fresh report path')
    result = execute(plan, episode.load_corpus(args.corpus.read_bytes()), references, transfer_inputs)
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
