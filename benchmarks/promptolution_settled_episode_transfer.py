"""Transfer the two frozen settled episode runners to the Promptolution score archive."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import pool, promptolution_witness_episode as donor
from benchmarks.prompteval_transfer import PROBES
from cpo import Observation, Row
from cpo._contract import digest
from cpo.feedback_episode import run_feedback_episode
from cpo.paired_qualification import certify_paired_qualification
from cpo.rotating_witness.episode import WitnessCycle, run_rotating_witness_episode
from cpo.settled_episode import EpisodeCycle, run_settled_episode


SETTLED, FEEDBACK = 'cpo-settled', 'cpo-feedback'
RUNNERS = {SETTLED: run_settled_episode, FEEDBACK: run_feedback_episode}
WITNESS = (donor.CPO, donor.UNRESTRICTED)
BASE = donor.RETAIN
VALIDATION, ADMISSION = 6, 4
API_SHA = 'a690b791eedeb3db94ca718fbd20a968d542b4dfef14e383d73301590c5e29e4'
OLDER_SHA = 'dae0668544760478ec45b1dd64270c03f13ba6a7766e5dcb398c0a0686a0e92a'


def locked(path, expected):
    raw = (donor.ROOT / path).read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError(f'The preceding archive evidence changed at {path}')
    return json.loads(raw)


def prepare():
    native = {
        f'gepa-{kind}/validation-{width}/cap-{width + slots * (width + 2 * PROBES)}':
            {'mode': kind, 'validationRows': width, 'searchCap': width + slots * (width + 2 * PROBES)}
        for width in (2, 4, 6)
        for kind, slots in (('sequential', 1), ('sequential', 2), ('batched', 2))
    }
    native.update({f'gepa-{kind}/validation-6/cap-32': {'mode': kind, 'validationRows': 6, 'searchCap': 32}
                   for kind in ('sequential', 'batched')})
    halving = {f'halving/cap-{cap}': {'mode': 'halving', 'validationRows': VALIDATION, 'searchCap': cap}
               for cap in (4, 6, 8, 12, 19)}
    api = locked('docs/settled-episode-feedback-api-parity-v1.json', API_SHA)
    sources = {path: sha256((donor.ROOT / path).read_bytes()).hexdigest() for path in (
        'benchmarks/promptolution_settled_episode_transfer.py', 'benchmarks/promptolution_witness_episode.py',
        'benchmarks/grounded_witness_episode.py', 'benchmarks/prompteval_transfer.py', 'benchmarks/pool.py',
        'benchmarks/gepa_disjoint_cases.py', 'cpo/feedback_episode.py', 'cpo/settled_episode.py',
        'cpo/paired_qualification.py', 'cpo/rotating_witness/episode.py',
    )}
    if any(api['sourceSha256'][name] != sources[name] for name in ('cpo/feedback_episode.py', 'cpo/settled_episode.py')):
        raise ValueError('Use the two frozen packaged episode policies')
    return {'protocol': 'cpo-promptolution-settled-episode-transfer-v1',
            'sourceSha256': sources, 'corpusSha256': donor.CORPUS_SHA, 'apiReceiptSha256': API_SHA,
            'priorPromptolutionReceiptSha256': OLDER_SHA, 'gepaVersion': '0.1.4',
            'tasks': donor.TASKS, 'programs': donor.PROGRAMS, 'startingProgram': donor.START,
            'seeds': donor.SEEDS, 'holdoutSeed': 'promptolution-heldout-v1',
            'validationPerCycle': VALIDATION, 'admissionPerCycle': ADMISSION, 'openingTrainingProbes': 2,
            'witnessSearchCap': 19, 'controlSettings': {**native, **halving},
            'nativeMethods': tuple(native), 'witnessMethods': WITNESS, 'candidates': tuple(RUNNERS),
            'draws': 4096, 'resampleSeed': 20261125,
            'layout': 'Keep the existing rosters and holdout. Split the original validation panel into nonoverlapping '
                      'six-case panels in order. Consume the first four existing admission cases per cycle. Use the '
                      'first two training cases in the first cycle for the CPO opening probe.',
            'comparison': 'Carry forward qualified incumbents across all three cycles. Compare against the best '
                          'affordable native and overall controls, reselected within each paired case-bootstrap draw.'}


def layout(plan, task, seed, held):
    windows = donor.schedule(plan, task, seed, held)
    cycles = []
    seen = set(held)
    for index, (roster, shared, train, qualification) in enumerate(windows):
        validation = tuple(shared[index * VALIDATION:(index + 1) * VALIDATION])
        proof = tuple(qualification[:ADMISSION])
        current = (*train, *validation, *proof)
        if len(set(current)) != len(current) or seen.intersection(current):
            raise ValueError('Training, validation, admission and held-out cases must stay disjoint')
        seen.update(current)
        cycles.append((roster, tuple(train), validation, proof))
    return cycles


def rows(cases):
    return tuple(Row(str(case), 'task') for case in cases)


def play(plan, matrix, windows, seed, method):
    observations = {}
    selected, decisions = donor.START, []
    allowed = {
        'training': {case for _, training, _, _ in windows for case in training},
        'validation': {case for _, _, validation, _ in windows for case in validation},
        'admission': {case for _, _, _, proof in windows for case in proof},
    }

    def grade(prompt, case, role):
        if prompt not in matrix or case not in allowed[role]:
            raise ValueError('A lookup left its program or case role')
        key = role, prompt, case
        if key not in observations:
            observations[key] = matrix[prompt][case] == '1'
        return observations[key]

    def qualify(prompt, row, repeat):
        if repeat != 0:
            raise ValueError('The archive records one prediction per prompt and case')
        return grade(prompt, int(row.id), 'admission')

    def evaluate(prompt, row):
        return Observation(grade(prompt, int(row.id), 'validation'), {})

    if method in RUNNERS:
        cycles = [EpisodeCycle(roster, rows(validation), rows(proof), seed + i)
                  for i, (roster, _, validation, proof) in enumerate(windows)]
        training = rows(windows[0][1][:2])
        result = RUNNERS[method](selected, training, cycles, evaluate,
                                 probe=lambda p, row: grade(p, int(row.id), 'training'), qualify=qualify)
        if result.evaluations != len(observations):
            raise ValueError('CPO must charge every callback exactly once on the disjoint paths')
        selected = result.prompt
        schedules = getattr(result, 'cycle_schedules', (result.schedule,) * len(cycles))
        decisions = [(schedule, step.search.finalist, step.prompt) for schedule, step in
                     zip(schedules, result.cycles, strict=True)]
    elif method in WITNESS:
        cycles = [WitnessCycle(roster, rows(validation), rows(proof), seed + i)
                  for i, (roster, _, validation, proof) in enumerate(windows)]
        result = run_rotating_witness_episode(
            selected, cycles, evaluate, qualify=qualify, metric_limit=plan['witnessSearchCap'],
            max_admissions=1 if method == WITNESS[0] else len(cycles),
        )
        selected = result.prompt
        decisions = [(step.search.finalist, step.prompt) for step in result.cycles]
    elif method != BASE:
        condition = plan['controlSettings'][method]
        native = condition['mode'] != 'halving'
        cap = condition['searchCap']
        for index, (roster, train, validation, proof) in enumerate(windows):
            validation = validation[:condition['validationRows']]
            training, anchors = set(train), set(validation)
            charged = set()

            def lookup(prompt, case):
                if prompt not in (selected, *roster) or (case not in anchors and (not native or case not in training)):
                    raise ValueError('A control left its current cycle roster or evidence scope')
                charged.add((prompt, case))
                if len(charged) > cap:
                    raise ValueError('A control exceeded its paid evaluation cap')
                return grade(prompt, case, 'training' if case in training else 'validation')

            if native:
                winner = donor.portable.native(selected, roster, train, validation, lookup,
                                               batched=condition['mode'] == 'batched', cap=cap, seed=seed + index)
            else:
                winner = pool.successive_halving((selected, *roster), validation, lookup, cap)
            if winner not in (selected, *roster):
                raise ValueError('A nominee left its current cycle roster')
            proof_result = certify_paired_qualification(selected, winner, rows(proof), qualify, seed=seed + index)
            selected = proof_result.prompt
            decisions.append((winner, selected))
    counts = Counter({'paidLookups': len(observations)})
    counts.update(f'{role}Lookups' for role, _, _ in observations)
    if method == FEEDBACK:
        counts['scheduleSwitches'] = sum(schedule != result.schedule for schedule in schedules)
    return selected, counts, (selected, decisions, list(observations.items()))


def compare(plan, panels, candidate, methods, *, enforce_cap=True):
    scores, costs = Counter(), Counter()
    for totals, vectors in panels:
        scores.update({method: sum(vector) for method, vector in vectors.items()})
        costs.update({method: stats['paidLookups'] for method, stats in totals.items()})
    eligible = tuple(method for method in methods if not enforce_cap or costs[method] <= costs[candidate])
    if not eligible:
        return None
    winner = donor.strongest(eligible, scores, costs)
    rng, differences = Random(plan['resampleSeed']), []
    for _ in range(plan['draws']):
        sampled = Counter()
        for _, vectors in panels:
            indices = rng.choices(range(donor.HOLDOUT), k=donor.HOLDOUT)
            sampled.update({method: sum(vectors[method][index] for index in indices)
                            for method in (candidate, *eligible)})
        control = donor.strongest(eligible, sampled, costs)
        differences.append(sampled[candidate] - sampled[control])
    paired = donor.ranges(differences, len(panels) * donor.HOLDOUT * len(plan['seeds']))
    compared = 'affordableControls' if enforce_cap else 'comparedControls'
    return {'control': winner, 'controlPasses': scores[winner], 'controlPaidLookups': costs[winner],
            'passDelta': scores[candidate] - scores[winner], 'paidLookupDelta': costs[candidate] - costs[winner],
            compared: eligible, **paired}


def measure(plan, archive):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Load the pinned GEPA 0.1.4 environment')
    original = locked('docs/promptolution-witness-small-native-results-v1.json', OLDER_SHA)
    controls = (BASE, *WITNESS, *plan['controlSettings'])
    methods = (*RUNNERS, *controls)

    def comparisons(data):
        return {candidate: {'nativeGEPA': compare(plan, data, candidate, plan['nativeMethods']),
                            'allControls': compare(plan, data, candidate, controls)}
                for candidate in RUNNERS} | {
                    'feedbackVsSettled': compare(plan, data, FEEDBACK, (SETTLED,), enforce_cap=False),
                }

    tasks, measured = {}, []
    for task in plan['tasks']:
        panel = archive[task]
        matrix = panel['correctness']
        held = sorted(Random(f"{plan['holdoutSeed']}/{task}").sample(range(len(panel['caseIDs'])), donor.HOLDOUT))
        held_hash = digest([panel['caseIDs'][case] for case in held])
        if held_hash != original['tasks'][task]['heldCaseSha256']:
            raise ValueError('Use the previously reserved holdout identities')
        totals, grades, traces = ({method: Counter() for method in methods},
                                  {method: [0] * donor.HOLDOUT for method in methods},
                                  {method: [] for method in methods})
        for seed in plan['seeds']:
            windows = layout(plan, task, seed, held)
            for method in methods:
                winner, counts, trace = play(plan, matrix, windows, seed, method)
                totals[method].update(counts)
                scores = [matrix[winner][case] == '1' for case in held]
                totals[method].update(holdoutPasses=sum(scores))
                grades[method] = [old + score for old, score in zip(grades[method], scores, strict=True)]
                traces[method].append(trace)
        point = totals, grades
        measured.append(point)
        tasks[task] = {'episodes': len(plan['seeds']), 'heldCaseSha256': held_hash,
                       'arms': {method: dict(totals[method], traceSha256=digest(traces[method])) for method in methods},
                       'comparisons': comparisons([point])}
    totals = {method: Counter() for method in methods}
    for task_totals, _ in measured:
        for method in methods:
            totals[method].update(task_totals[method])
    return {'plan': plan, 'planSha256': digest(plan), 'tasks': tasks, 'totals': totals,
            'pooledComparisons': comparisons(measured), 'providerRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan = prepare()
    seal = digest(plan)
    if args.corpus is None and args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.corpus is None or args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the pinned corpus, current seal, and a fresh report path')
    result = measure(plan, donor.load_corpus(args.corpus.read_bytes()))
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
