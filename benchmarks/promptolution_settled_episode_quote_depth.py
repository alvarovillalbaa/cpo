"""Keep a quoted CPO screen at its nominal validation depth on smaller rosters."""

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
from benchmarks import promptolution_settled_episode_transfer as transfer
from cpo import Observation
from cpo import feedback_episode as feedback, settled_episode as settled
from cpo._contract import digest
from cpo.bounded_uniform_validation import screen as bounded_screen
from cpo.ordered_uniform_validation import MISSES, screen as ordered_screen
from cpo.qualification_prefix_cycle import run_qualification_prefix_cycle
from cpo.quoted_shared_validation_cycle import _schedule
from cpo.settled_episode_schedule import choose_schedule
from cpo.two_sided_certificate_cycle import _run


BASE, UNIFORM, HALVING = settled._ACTIONS
NOMINAL_SETTLED, NOMINAL_FEEDBACK = 'nominal-depth-settled', 'nominal-depth-feedback'
VARIANTS = {NOMINAL_SETTLED: transfer.SETTLED, NOMINAL_FEEDBACK: transfer.FEEDBACK}


def preserve_depth(screen, width, quote, halve, incumbent, candidates, rows, evaluate, cap):
    if len(candidates) < width and not any(row.critical for row in rows):
        nominal = _schedule(width, rows, min(quote, cap), halve)
        rows = rows[:len(nominal)]
    return screen(incumbent, candidates, rows, evaluate, cap)


def quoted_runner(screen, width, quote, *, halve):
    limited = partial(settled._limit, screen, width, quote)
    return partial(_run, screen=partial(preserve_depth, limited, width, quote, halve))


_SHALLOW_HALVING = partial(preserve_depth, settled._OPENING_HALVING, 8, 9, True)
_SHALLOW_OPENING = partial(preserve_depth, settled._OPENING_LIMIT, 8, 9, True)
RUNNERS = {
    BASE: partial(run_qualification_prefix_cycle,
                  screens=(settled._incumbent_first, _SHALLOW_HALVING, _SHALLOW_HALVING, _SHALLOW_OPENING)),
    UNIFORM: quoted_runner(partial(ordered_screen, order=MISSES), 8, 18, halve=False),
    HALVING: quoted_runner(partial(bounded_screen, halve=True), 4, 6, halve=True),
    feedback._HALVING: quoted_runner(partial(bounded_screen, halve=True), 8, 14, halve=True),
}


def play(matrix, windows, seed, *, adapt):
    paid, decisions = {}, []

    def grade(prompt, case, role):
        key = role, prompt, case
        if key in paid:
            raise ValueError('A disjoint episode must pay for each observed grade once')
        passed = matrix[prompt][case] == '1'
        paid[key] = passed
        return passed

    def qualify(prompt, row, repeat):
        if repeat != 0:
            raise ValueError('The archive records one admission prediction per prompt and case')
        return grade(prompt, int(row.id), 'admission')

    incumbent = transfer.donor.START
    opening = choose_schedule(incumbent, windows[0][1][:2],
                              lambda prompt, case: grade(prompt, case, 'training'), actions=settled._ACTIONS)
    rejected, dispatched = False, 2
    switched = 0
    for index, (roster, _, validation, admission) in enumerate(windows):
        schedule = feedback._FOLLOW_UP[opening] if adapt and rejected else opening
        switched += schedule != opening
        if schedule == feedback._RETAIN:
            rejected = False
            decisions.append((schedule, None, incumbent))
            continue
        decision = RUNNERS[schedule](
            incumbent, roster, transfer.rows(validation), transfer.rows(admission),
            lambda prompt, row: Observation(grade(prompt, int(row.id), 'validation'), {}),
            metric_limit=settled._MAX_VALIDATION_READS, qualify=qualify, seed=seed + index,
        )
        nominee = decision.search.finalist
        incumbent = decision.prompt
        rejected = nominee is not None and decision.qualification.status == 'rejected'
        decisions.append((schedule, nominee, incumbent))
        dispatched += decision.search.evaluations + decision.qualification_evaluations
    if dispatched != len(paid):
        raise ValueError('The nominal-depth runner must reconcile each callback')
    counts = Counter(paidLookups=len(paid))
    counts.update(f'{role}Lookups' for role, _, _ in paid)
    if adapt:
        counts['scheduleSwitches'] = switched
    return incumbent, counts, (incumbent, decisions, list(paid.items()))


def prepare():
    plan, original, parent = headroom.prepare()
    plan = {**plan, 'protocol': 'cpo-promptolution-settled-episode-quote-depth-v1',
            'sourceSha256': {**plan['sourceSha256'],
                             str(Path(__file__).resolve().relative_to(transfer.donor.ROOT)):
                                 sha256(Path(__file__).read_bytes()).hexdigest()},
            'method': 'For each quoted noncritical screen, preserve the case depth funded at full nominal width. '
                      'Use the original screen, roster order, qualification proof, and feedback rules. '
                      'Replay all original methods and compare at the new realized lookup budgets.'}
    return plan, original, parent


def measure(plan, original, parent, archive):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA environment')
    controls = (transfer.BASE, *transfer.WITNESS, *original['controlSettings'])
    prior_methods = (*transfer.RUNNERS, *controls)
    methods = (*prior_methods, *VARIANTS)
    native = (transfer.BASE, *original['nativeMethods'])

    def compare(data, menus):
        return {candidate: {
            'originalPolicy': transfer.compare(original, data, candidate, (reference,), enforce_cap=False),
            'nativeGEPA': transfer.compare(original, data, candidate, original['nativeMethods']),
            'allControls': transfer.compare(original, data, candidate, controls),
            'nativeHindsight': headroom.evaluate(menus, candidate, native, None),
            'allControlsHindsight': headroom.evaluate(menus, candidate, controls, None),
        } for candidate, reference in VARIANTS.items()}

    tasks, observed, pooled_menus = {}, [], []
    for task in original['tasks']:
        panel = archive[task]
        matrix = panel['correctness']
        held = sorted(Random(f"{original['holdoutSeed']}/{task}").sample(
            range(len(panel['caseIDs'])), transfer.donor.HOLDOUT,
        ))
        prior = parent['tasks'][task]
        if digest([panel['caseIDs'][case] for case in held]) != prior['heldCaseSha256']:
            raise ValueError('The original reserved holdout must reproduce')
        totals, vectors, traces = ({method: Counter() for method in methods},
                                   {method: [0] * len(held) for method in methods},
                                   {method: [] for method in methods})
        menus = []
        for seed in original['seeds']:
            windows = transfer.layout(original, task, seed, held)
            menu = {}
            for method in methods:
                if method in VARIANTS:
                    winner, costs, trace = play(matrix, windows, seed, adapt=method == NOMINAL_FEEDBACK)
                else:
                    winner, costs, trace = transfer.play(original, matrix, windows, seed, method)
                grades = [matrix[winner][case] == '1' for case in held]
                totals[method].update(costs, holdoutPasses=sum(grades))
                vectors[method] = [a + b for a, b in zip(vectors[method], grades, strict=True)]
                traces[method].append(trace)
                menu[method] = frontier.Point(sum(grades), costs['paidLookups'], (method,))
            menus.append(menu)
        arms = {method: dict(totals[method], traceSha256=digest(traces[method])) for method in methods}
        if {method: arms[method] for method in prior_methods} != prior['arms']:
            raise ValueError('All original arm traces must reproduce before measuring the variant')
        tasks[task] = {'episodes': len(menus), 'arms': arms, 'comparisons': compare([(totals, vectors)], menus)}
        observed.append((totals, vectors))
        pooled_menus.extend(menus)
    pooled = {method: frontier.summarize([menu[method] for menu in pooled_menus]) for method in methods}
    return {'plan': plan, 'planSha256': digest(plan), 'tasks': tasks, 'totals': pooled,
            'pooledComparisons': compare(observed, pooled_menus), 'providerRequests': 0}


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
