"""Compute the hindsight certificate floor of the frozen narrow routed policy."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import validation_routed_exact_order as previous
from cpo._contract import digest
from cpo.full_roster_precheck import validation_routing
from cpo.settled_episode_schedule import choose_schedule


math_transfer, depth, transfer, archive = previous.math, previous.depth, previous.transfer, previous.archive
recorded_math = math_transfer.math
REFERENCE = 'f0a2f1111131b7ff610307ca4a18c70f0ccfded3b606103e8303bb9e21aa8cc0'


def certificate(grades, costs, winner, prepaid, *, complete_scores):
    """Minimize cost of sufficient observed replies, with the incumbent winning ties."""
    depth = len(grades[0])
    locked = [set(prepaid), set(), set()]
    if winner and complete_scores:
        locked[0] = locked[winner] = set(range(depth))
    fixed = sum(costs[prompt][row] for prompt, seen in enumerate(locked) for row in seen)
    passes = sum(grades[winner][row] for row in locked[winner])
    available_passes = sorted(price for row, price in enumerate(costs[winner])
                              if row not in locked[winner] and grades[winner][row])
    losers = []
    for prompt, row_grades in enumerate(grades):
        if prompt != winner:
            observed_fails = sum(not row_grades[row] for row in locked[prompt])
            failures = sorted(price for row, price in enumerate(costs[prompt])
                              if row not in locked[prompt] and not row_grades[row])
            losers.append((observed_fails, failures, prompt < winner))
    options = []
    for extra in range(len(available_passes) + 1):
        lower = passes + extra
        needed = [max(0, depth + earlier - seen - lower) for seen, _, earlier in losers]
        if all(amount <= len(prices) for amount, (_, prices, _) in zip(needed, losers, strict=True)):
            options.append(fixed + sum(available_passes[:extra]) + sum(
                sum(prices[:amount]) for amount, (_, prices, _) in zip(needed, losers, strict=True)))
    if not options:
        raise ValueError('The archived outcomes do not certify the recorded nominee')
    return min(options)


def prepare():
    original, math_corpus, *_ = previous.prepare()
    reference = transfer.locked('docs/validation-routed-exact-order-v1.json', REFERENCE)
    if reference['planSha256'] != digest(original) or digest(reference['plan']) != digest(original):
        raise ValueError('The measured read-order plan must reproduce')
    prompt_plan, *_ = archive.prepare()
    path = Path(__file__)
    plan = {**{key: original[key] for key in ('datasets', 'corpusSha256', 'incumbentGroups', 'gepaVersion',
                                             'validationPerCycle', 'admissionPerCycle', 'promptolutionCorpusSha256')},
            'protocol': 'cpo-validation-routed-certificate-floor-v1', 'policy': depth.ROUTED,
            'baselineReceiptSha256': REFERENCE, 'baselinePlanSha256': reference['planSha256'],
            'sourceSha256': {**original['sourceSha256'], str(path.relative_to(transfer.donor.ROOT)):
                             sha256(path.read_bytes()).hexdigest()},
            'scope': ('Replay the exact original routed path and leave opening, other schedules, and qualification '
                      'paid replies fixed. Count the cheapest sufficient subset of recorded uniform grades, once '
                      'with complete proof score inputs and once with only the same exact nominee. Include prepaid '
                      'opening replies. Minimize lookup counts and historical ARC charges separately. Compare the '
                      'complete-score floor with stalled-tail costs. These are hindsight limits.')}
    return plan, math_corpus, prompt_plan, reference['results']


def inspect_cycle(base, roster, cases, finalist, paid, prepaid, matrix, prices, audit):
    prompts = (base, *roster)
    grades = tuple(tuple(matrix[prompt][case] == '1' for case in cases) for prompt in prompts)
    scores = tuple(map(sum, grades))
    winner = max(range(len(prompts)), key=scores.__getitem__)
    if (prompts[winner] if winner else None) != finalist or not all((base, case) in paid for case in cases):
        raise ValueError('The replay must match the full uniform decision and charged incumbent score')
    unit = ((1,) * len(cases),) * len(prompts)
    objectives = [('Lookups', unit, len(paid))]
    if prices is not None:
        weights = tuple(tuple(prices[prompt][case] for case in cases) for prompt in prompts)
        objectives.append(('Nanodollars', weights, sum(prices[prompt][case] for prompt, case in paid)))
    for name, weights, charge in objectives:
        complete = certificate(grades, weights, winner, prepaid, complete_scores=True)
        nominee = certificate(grades, weights, winner, prepaid, complete_scores=False)
        if not nominee <= complete <= charge:
            raise ValueError('Both certificate floors must lower-bound the recorded cost')
        audit.update({f'uniformActual{name}': charge, f'uniformCompleteFloor{name}': complete,
                      f'uniformNomineeFloor{name}': nominee})
        if name == 'Lookups':
            audit.update(uniformAtCompleteLookupFloor=int(complete == charge),
                         uniformNominees=int(winner != 0))


def play(plan, start, matrix, windows, held, seed, prices, audit):
    with patch.object(transfer.donor, 'START', start):
        chosen, costs, (_, steps, ledger) = archive.play(plan, matrix, windows, seed, depth.ROUTED)
    observed = {(prompt, case): grade for (role, prompt, case), grade in ledger if role == 'validation'}
    opening = []

    def routing_grade(prompt, case):
        opening.append((prompt, case))
        return observed[prompt, case]

    if choose_schedule(start, windows[0][2][:2], routing_grade, actions=validation_routing._ACTIONS) != steps[0][0]:
        raise ValueError('The original charged routing probes must reproduce')

    incumbent = start
    for index, ((roster, _, cases, _), (schedule, finalist, deployed)) in enumerate(zip(windows, steps, strict=True)):
        if schedule == depth.language.OPENING and len(roster) == 2 and 3 <= len(cases) <= 6:
            local = {(prompt, case) for prompt, case in observed if case in cases}
            prepaid = tuple(cases.index(case) for _, case in opening) if not index else ()
            if local == (set(opening) if not index else set()):
                if finalist is not None:
                    raise ValueError('A skipped uniform screen cannot nominate')
                audit['uniformSkippedByPrecheck'] += 1
            else:
                audit['uniformScreens'] += 1
                inspect_cycle(incumbent, roster, cases, finalist, local, prepaid, matrix, prices, audit)
        incumbent = deployed

    audit.update(actualLookups=costs['paidLookups'], episodes=1,
                 holdoutPasses=sum(matrix[chosen][case] == '1' for case in held))
    if prices is not None:
        audit['actualNanodollars'] += sum(prices[prompt][case] for (_, prompt, case), _ in ledger)


def summarize(audit, reference):
    routed, stalled = reference['totals'][depth.ROUTED], reference['totals'][math_transfer.STALLED]
    if (audit['episodes'] != reference['episodes'] or audit['actualLookups'] != routed['paidLookups']
            or audit['holdoutPasses'] != routed['holdoutPasses']
            or ('actualNanodollars' in audit and audit['actualNanodollars'] != routed[math_transfer.PRICE])):
        raise ValueError('The complete routed baseline must match its sealed receipt')
    for suffix, key in (('Lookups', 'paidLookups'), ('Nanodollars', math_transfer.PRICE)):
        if key not in routed:
            continue
        for mode in ('Complete', 'Nominee'):
            save = audit[f'uniformActual{suffix}'] - audit[f'uniform{mode}Floor{suffix}']
            audit[f'{mode.lower()}Headroom{suffix}'] = save
            audit[f'{mode.lower()}TotalFloor{suffix}'] = audit[f'actual{suffix}'] - save
        audit[f'stalled{suffix}'] = stalled[key]
    return audit


def replay(plan, math_corpus, prompt_plan, reference, predictions):
    results = {'math': {}, 'promptolution': {}}
    for subject, settings in plan['datasets'].items():
        cells = recorded_math.math.load_cells(subject, math_corpus[subject]['record'])
        matrix = {prompt: ''.join(str(int(cell[0])) for cell in row) for prompt, row in cells.items()}
        prices = {prompt: tuple(cell[1] for cell in row) for prompt, row in cells.items()} if subject == 'arc' else None
        results['math'][subject] = {}
        for group in plan['incumbentGroups']:
            audit, layout = Counter(), []
            trials = recorded_math.trials(cells, settings, group, math_transfer.WIDTH)
            for start, roster, (train, validation, proof, held), seed in trials:
                windows = [(tuple(roster), tuple(train), tuple(validation[:plan['validationPerCycle']]),
                            tuple(proof[:plan['admissionPerCycle']]))]
                play(plan, start, matrix, windows, held, seed, prices, audit)
                layout.append((start, windows, held, seed))
            baseline = reference['math'][subject][group]
            if digest(layout) != baseline['layoutSha256']:
                raise ValueError('The original math layout must reproduce')
            results['math'][subject][group] = summarize(audit, baseline)
    for task in prompt_plan['tasks']:
        panel = predictions[task]
        case_ids = panel['caseIDs']
        held = sorted(Random(f"{prompt_plan['holdoutSeed']}/{task}").sample(range(len(case_ids)), transfer.donor.HOLDOUT))
        audit = Counter()
        for seed in prompt_plan['seeds']:
            windows = transfer.layout(prompt_plan, task, seed, held)
            play(prompt_plan, transfer.donor.START, panel['correctness'], windows, held, seed, None, audit)
        results['promptolution'][task] = summarize(audit, reference['promptolution']['tasks'][task])
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if not (args.execute or args.out or args.corpus):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if (args.execute != seal or args.out is None or args.out.exists() or args.corpus is None
            or version('gepa') != plan['gepaVersion']):
        parser.error('Replay requires the pinned corpus, current seal, pinned GEPA and a fresh output path')
    predictions = transfer.donor.load_corpus(args.corpus.read_bytes())
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs, predictions)}
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
