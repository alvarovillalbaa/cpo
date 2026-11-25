"""Transfer the frozen validation-routed opening to the Promptolution archive."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import fixed_opening_language_transfer as language
from benchmarks import promptolution_settled_episode_transfer as transfer
from cpo._contract import digest
from cpo.full_roster_precheck import run_full_roster_feedback_episode
from cpo.full_roster_precheck.validation_routing import run_validation_routed_episode


TRANSFER_RECEIPT_SHA = '3458d801fa4f2bf94b38b01fad7934f1ecaa289cdb19fa0430468ac5fb422fab'
ROUTING_RECEIPT_SHA = '5b461240dec45149ef92e912f615a5f12b34d0ca5a8a637fa71c60e3d81607d8'
ROUTED = 'validation-routed-opening'


def routed(incumbent, _training, cycles, evaluate, *, probe, qualify):
    return run_validation_routed_episode(incumbent, cycles, evaluate, qualify=qualify)


RUNNERS = {language.ADAPTIVE: run_full_roster_feedback_episode, language.FIXED: language.play_fixed, ROUTED: routed}


def prepare():
    previous = transfer.prepare()
    original = transfer.locked('docs/promptolution-settled-episode-transfer-v1.json', TRANSFER_RECEIPT_SHA)
    reference = transfer.locked('docs/full-roster-precheck-verification-v1.json', language.BASELINE_RECEIPT)
    routing = transfer.locked('docs/validation-routed-opening-v1.json', ROUTING_RECEIPT_SHA)
    if (digest(previous) != digest(original['plan']) or digest(previous) != original['planSha256']
            or digest(routing['plan']) != routing['planSha256']):
        raise ValueError('The original transfer and routing experiment must reproduce')
    root = transfer.donor.ROOT
    files = (Path(__file__).resolve(), Path(language.__file__).resolve(), root / 'cpo/full_roster_precheck/fixed_opening.py',
             root / 'cpo/full_roster_precheck/validation_routing.py', root / 'cpo/full_roster_precheck/__init__.py')
    sources = {str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest() for file in files}
    return {**previous, 'protocol': 'cpo-validation-routed-promptolution-v1',
            'sourceSha256': {**previous['sourceSha256'], **sources},
            'originalTransferSha256': TRANSFER_RECEIPT_SHA, 'adaptiveReceiptSha256': language.BASELINE_RECEIPT,
            'routingReceiptSha256': ROUTING_RECEIPT_SHA, 'candidates': tuple(RUNNERS),
            'scope': ('Use the frozen routed and uniform openings without retuning on the two-challenger rosters. '
                      'Keep the original layouts, independent admission, and holdout. Reproduce adaptive CPO, '
                      'settled CPO, sequential and batched GEPA, halving, witness controls, and retention. '
                      'Compare realized lookup cost and resample paired held-out cases. Select the strongest '
                      'affordable control again within each bootstrap draw.')}, original, reference['archivedReplay']['promptolution']


def play(plan, matrix, windows, seed, arm):
    method = transfer.FEEDBACK if arm in RUNNERS else arm
    if arm in RUNNERS:
        with patch.dict(transfer.RUNNERS, {method: RUNNERS[arm]}):
            return transfer.play(plan, matrix, windows, seed, method)
    return transfer.play(plan, matrix, windows, seed, method)


def compare(plan, panels):
    native = plan['nativeMethods']
    simple = tuple(label for label in plan['controlSettings'] if label not in native)
    matched = {
        'nativeGepa': native, 'simpleHalving': simple,
        'allControls': (transfer.BASE, *transfer.WITNESS, *plan['controlSettings']),
    }
    direct = (language.ADAPTIVE, language.FIXED, transfer.SETTLED)
    return {**{name: transfer.compare(plan, panels, ROUTED, methods) for name, methods in matched.items()},
            **{arm: transfer.compare(plan, panels, ROUTED, (arm,), enforce_cap=False) for arm in direct}}


def measure(plan, original, reference, archive):
    controls = (transfer.BASE, *transfer.WITNESS, *plan['controlSettings'])
    methods = (*RUNNERS, transfer.SETTLED, *controls)
    reports, panels = {}, []
    for task in plan['tasks']:
        matrix = archive[task]['correctness']
        held = sorted(Random(f"{plan['holdoutSeed']}/{task}").sample(
            range(len(archive[task]['caseIDs'])), transfer.donor.HOLDOUT))
        holdout = digest([archive[task]['caseIDs'][case] for case in held])
        expected = original['tasks'][task]
        if holdout != expected['heldCaseSha256'] or len(plan['seeds']) != expected['episodes']:
            raise ValueError('Use the original Promptolution holdout and seeds')
        totals = {arm: Counter() for arm in methods}
        vectors = {arm: [0] * len(held) for arm in methods}
        traces = {arm: [] for arm in methods}
        routes = Counter()
        changed = 0
        for seed in plan['seeds']:
            windows = transfer.layout(plan, task, seed, held)
            selected = {}
            for arm in methods:
                winner, costs, trace = play(plan, matrix, windows, seed, arm)
                if arm in (language.FIXED, ROUTED) and costs.get('trainingLookups', 0):
                    raise ValueError('A no-training opening purchased a training reply')
                selected[arm] = winner
                grades = [matrix[winner][case] == '1' for case in held]
                totals[arm].update(costs, holdoutPasses=sum(grades))
                vectors[arm] = [before + grade for before, grade in zip(vectors[arm], grades, strict=True)]
                traces[arm].append(trace)
                if arm == ROUTED:
                    routes[trace[1][0][0]] += 1
            changed += int(selected[ROUTED] != selected[language.ADAPTIVE])
        hashes = {name: digest(trace) for name, trace in traces.items()}
        baseline = reference[task]
        if (totals[language.ADAPTIVE] != baseline['totals']
                or hashes[language.ADAPTIVE] != baseline['paidTraceSha256']):
            raise ValueError('The packaged adaptive baseline must reproduce exactly')
        for label in (transfer.SETTLED, *controls):
            if {**totals[label], 'traceSha256': hashes[label]} != expected['arms'][label]:
                raise ValueError(f'The original Promptolution comparator changed for {task}/{label}')
        point = totals, vectors
        panels.append(point)
        reports[task] = {'episodes': len(plan['seeds']), 'heldCaseSha256': holdout, 'totals': totals,
                         'paidTraceSha256': hashes, 'routedOpenings': routes,
                         'changedFinalPromptRelativeToAdaptive': changed, 'comparisons': compare(plan, [point])}
    pooled = {arm: sum((totals[arm] for totals, _ in panels), Counter()) for arm in methods}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'tasks': reports, 'pooledTotals': pooled, 'pooledComparisons': compare(plan, panels)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--corpus', type=Path)
    cli.add_argument('--execute', metavar='PLAN_SHA256')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, original, reference = prepare()
    seal = digest(plan)
    if not (args.corpus or args.execute or args.out):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if (not args.corpus or args.execute != seal or not args.out or args.out.exists()
            or version('gepa') != plan['gepaVersion']):
        cli.error('Replay requires the pinned corpus, current seal, pinned GEPA and a fresh output path')
    archive = transfer.donor.load_corpus(args.corpus.read_bytes())
    result = measure(plan, original, reference, archive)
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
