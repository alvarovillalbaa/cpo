"""Spend the unused quote slot on a second round before cutting two challengers."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import language_roster_budget_frontier as frontier
from benchmarks import promptolution_settled_episode_headroom as headroom
from benchmarks import promptolution_settled_episode_read_order as prior
from benchmarks import promptolution_settled_episode_transfer as transfer
from cpo import feedback_episode as feedback, settled_episode as settled
from cpo._contract import digest
from cpo.bounded_uniform_validation import screen as bounded_screen
from cpo.certified_shared_validation_cycle import _shortlist
from cpo.quoted_shared_validation_cycle import _schedule
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run


PARENT_SHA = 'da440a89f18e6b6d9c3e61f7281b51b3a89ab51af4bce9b5013a5ccf29db6998'
REFERENCES = {'two-round-settled': transfer.SETTLED, 'two-round-feedback': transfer.FEEDBACK}
_ORIGINAL = partial(bounded_screen, halve=True)


def screen(incumbent, candidates, rows, evaluate, cap):
    if len(candidates) != 2 or any(row.critical for row in rows):
        return _ORIGINAL(incumbent, candidates, rows, evaluate, cap)
    funded = tuple(row for row, _ in _schedule(2, rows, cap, True))
    depth = len(funded)
    # Price the full incumbent and eventual finalist, plus two observations
    # for the other challenger. Retain the original funded depth.
    if depth < 2 or 2 * depth + 2 > cap:
        return _ORIGINAL(incumbent, candidates, rows, evaluate, cap)
    if depth == 2:
        return bounded_screen(incumbent, candidates, funded, evaluate, cap, halve=False)

    paid = 0

    def read(prompt, row):
        nonlocal paid
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Shared validation requires exact boolean replies')
        paid += 1
        return grade

    base_passes = sum(read(incumbent, row) for row in funded)
    if base_passes == depth:
        return FinalistResult(incumbent, None, paid), None
    active = candidates
    scores = {}
    priority = {prompt: index for index, prompt in enumerate(candidates)}
    for seen, row in enumerate(funded, 1):
        threshold = base_passes + 1 - (depth - seen)
        active = _shortlist(active, scores, priority, 2 if seen == 1 else 1,
                            threshold, partial(read, row=row))
        if not active:
            return FinalistResult(incumbent, None, paid), None
    winner = active[0]
    return FinalistResult(winner, winner, paid), ((base_passes, depth), (scores[winner], depth))


OVERRIDES = {
    settled._ACTIONS[2]: partial(_run, screen=partial(settled._limit, screen, 4, 6)),
    feedback._HALVING: partial(_run, screen=partial(settled._limit, screen, 8, 14)),
}


def prepare():
    receipt = transfer.locked('docs/promptolution-settled-episode-read-order-v1.json', PARENT_SHA)
    plan, original, parent = prior.prepare()
    if digest(plan) != receipt['planSha256'] or digest(receipt['plan']) != receipt['planSha256']:
        raise ValueError('The read-order replay must reproduce its original plan')
    source = Path(__file__).resolve()
    plan = {**plan, 'protocol': 'cpo-promptolution-two-round-halving-v1',
            'readOrderReceiptSha256': PARENT_SHA, 'readOrderPlanSha256': receipt['planSha256'],
            'sourceSha256': {**plan['sourceSha256'], str(source.relative_to(transfer.donor.ROOT)):
                             sha256(source.read_bytes()).hexdigest()},
            'method': 'If both challengers can be priced through round two at the original halving depth, '
                      'move the first shortlist cut to round two. Preserve the full original validation quote, '
                      'roster ties, feedback rules, independent qualification and original held-out cases. '
                      'Record changed cycle decisions and their episode-level effects.'}
    return plan, original, parent


def measure(plan, original, parent, archive):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA environment')
    baseline = headroom.capture(original, archive, parent)
    native = (transfer.BASE, *original['nativeMethods'])
    controls = (transfer.BASE, *transfer.WITNESS, *original['controlSettings'])
    methods = (*transfer.RUNNERS, *controls, *REFERENCES)
    tasks, pooled, observations = {}, [], []

    def compare(data, menus):
        return {variant: {
            'packaged': transfer.compare(original, data, variant, (method,), enforce_cap=False),
            'nativeGEPA': transfer.compare(original, data, variant, original['nativeMethods']),
            'allControls': transfer.compare(original, data, variant, controls),
            'nativeHindsight': headroom.evaluate(menus, variant, native, None),
            'allControlsHindsight': headroom.evaluate(menus, variant, controls, None),
        } for variant, method in REFERENCES.items()}

    for task, menus in baseline.items():
        panel = archive[task]
        matrix = panel['correctness']
        held = sorted(Random(f"{original['holdoutSeed']}/{task}").sample(
            range(len(panel['caseIDs'])), transfer.donor.HOLDOUT,
        ))
        counts = {method: Counter() for method in methods}
        vectors = {method: [0] * len(held) for method in methods}
        changes = {name: [] for name in REFERENCES}
        traces = {name: [] for name in REFERENCES}
        for seed, menu in zip(original['seeds'], menus, strict=True):
            windows = transfer.layout(original, task, seed, held)
            packaged = {}
            for method in methods:
                if method in REFERENCES:
                    reference = REFERENCES[method]
                    winner, costs, trace = prior.play(original, matrix, windows, seed, reference, OVERRIDES)
                    old_winner, old_cost, old_trace, old_score = packaged[reference]
                    traces[method].append(trace)
                else:
                    winner, costs, trace = transfer.play(original, matrix, windows, seed, method)
                grades = [matrix[winner][case] == '1' for case in held]
                score = sum(grades)
                if method in REFERENCES and trace[1] != old_trace[1]:
                    changes[method].append({
                        'seed': seed, 'packagedTransitions': old_trace[1], 'twoRoundTransitions': trace[1],
                        'winnerChanged': winner != old_winner, 'holdoutPassDelta': score - old_score,
                        'paidLookupDelta': costs['paidLookups'] - old_cost['paidLookups'],
                    })
                if method in transfer.RUNNERS:
                    packaged[method] = winner, costs, trace, score
                counts[method].update(costs, holdoutPasses=score)
                vectors[method] = [a + b for a, b in zip(vectors[method], grades, strict=True)]
                point = frontier.Point(score, costs['paidLookups'], (method,))
                if method in menu and menu[method] != point:
                    raise ValueError('Each original reference score and cost must reproduce')
                menu[method] = point
        tasks[task] = {'episodes': len(menus), 'changedEpisodes': changes,
                       'traceSha256': {m: digest(t) for m, t in traces.items()},
                       'comparisons': compare([(counts, vectors)], menus)}
        pooled.extend(menus)
        observations.append((counts, vectors))
    return {'plan': plan, 'planSha256': digest(plan), 'tasks': tasks,
            'pooled': compare(observations, pooled), 'providerRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, original, parent = prepare()
    seal = digest(plan)
    if not (args.corpus or args.execute or args.out):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if not args.corpus or args.execute != seal or not args.out or args.out.exists():
        parser.error('Replay requires the pinned corpus, current seal, and a fresh output')
    report = measure(plan, original, parent, transfer.donor.load_corpus(args.corpus.read_bytes()))
    with args.out.open('x') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
