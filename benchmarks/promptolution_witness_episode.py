"""Transfer the published witness episode to recorded GSM8K and SST-5 predictions."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import grounded_witness_episode as portable, pool
from benchmarks.prompteval_narrow_native_admission import native_settings
from benchmarks.prompteval_rotating_witness_case_evidence import ranges
from cpo import Observation, Row
from cpo._contract import digest, unique_object
from cpo.paired_qualification import certify_paired_qualification
from cpo.rotating_witness.episode import WitnessCycle, run_rotating_witness_episode


ROOT = Path(__file__).resolve().parents[1]
CORPUS_SHA = '729bba5141874b28e3b172757d5e009f6e847f2b04050c75359d6273a01c9491'
CAPTURE_DESIGN = '2ad227bd1dce3b5d46053684b49b0c754ac142979b7f65e5c7d76ad0c69d8514'
START = 'unoptimized'
PROGRAMS = ('AdalFlow', 'CAPO', 'DSPy-GEPA', 'OPRO', START, 'unoptimized2', 'unoptimized3')
TASKS = ('gsm8k', 'sst5')
CPO = 'cpo-one-admission'
UNRESTRICTED = 'cpo-three-admissions'
RETAIN = 'retain-start'
CYCLES, TRAIN, VALIDATION, ADMISSION, HOLDOUT = 3, 16, 24, 8, 90
SEEDS = tuple(range(47101, 47709, 19))
CONTROLS = {**native_settings(),
            'gepa-sequential/validation-24/cap-52/one-admission': {'validationRows': 24, 'searchCap': 52},
            'gepa-batched/validation-24/cap-80/one-admission': {'validationRows': 24, 'searchCap': 80},
            **{f'successive-halving/cap-{cap}/one-admission': {'validationRows': VALIDATION, 'searchCap': cap}
               for cap in (8, 16, 32)}}
GEPA = tuple(name for name in CONTROLS if name.startswith('gepa-'))
HALVING = tuple(name for name in CONTROLS if name.startswith('successive-halving/'))
ARMS = (RETAIN, CPO, UNRESTRICTED, *CONTROLS)


def prepare():
    names = ('benchmarks/promptolution_witness_episode.py', 'benchmarks/grounded_witness_episode.py',
             'benchmarks/prompteval_narrow_native_admission.py', 'benchmarks/prompteval_transfer.py',
             'benchmarks/prompteval_rotating_witness_case_evidence.py', 'benchmarks/gepa_disjoint_cases.py',
             'benchmarks/pool.py', 'requirements-benchmark.txt', 'cpo/optimizer.py', 'cpo/_contract.py',
             'cpo/fixed_pool_cycle.py', 'cpo/single_finalist.py', 'cpo/rotating_witness/__init__.py',
             'cpo/rotating_witness/episode.py', 'cpo/paired_qualification.py')
    return {'protocol': 'cpo-promptolution-witness-episode-v1', 'sourceRevision': '6cd48d2431bb5cf796273f4ea10d3119791ec483',
            'model': 'gemma-3-27b-it', 'sourceRepository': 'finitearth/prompt-optimization-framework-comparison',
            'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in names},
            'corpusSha256': CORPUS_SHA, 'sourceCaptureDesignSha256': CAPTURE_DESIGN, 'gepaVersion': '0.1.4',
            'tasks': TASKS, 'programs': PROGRAMS, 'startingProgram': START, 'seeds': SEEDS, 'cycles': CYCLES,
            'candidate': CPO, 'cpoSearchCap': portable.CAPS[CPO], 'controlSettings': CONTROLS,
            'splitSizes': {'trainPerCycle': TRAIN, 'validation': VALIDATION, 'admissionPerCycle': ADMISSION,
                           'holdout': HOLDOUT},
            'holdoutSeed': 'promptolution-heldout-v1', 'draws': 4096, 'resampleSeed': 20261125,
            'scope': 'Offer every archived challenger once. Match admission rules and charge episode-local paid replies.',
            'decisionRule': ('Require a positive case-bootstrap lower endpoint against the strongest affordable '
                             'control for each task and the pool. Reselect that control on every draw.')}


def load_corpus(raw):
    if sha256(raw).hexdigest() != CORPUS_SHA:
        raise ValueError('Use the pinned reduced Promptolution archive')
    source = json.loads(raw, object_pairs_hook=unique_object)
    archive = source['archive']
    if source['designSha256'] != CAPTURE_DESIGN or set(archive) != set(TASKS):
        raise ValueError('The archive differs from its capture design')
    for panel in archive.values():
        ids, vectors = panel['caseIDs'], panel['correctness']
        if (len(ids) != 300 or ids != sorted(set(ids)) or set(vectors) != set(PROGRAMS) or
                any(len(vector) != len(ids) or set(vector) - {'0', '1'} for vector in vectors.values())):
            raise ValueError('Each task needs seven programs on the same 300 aligned cases')
    return archive


def schedule(plan, task, seed, holdout):
    available = sorted(set(range(300)) - set(holdout))
    picked = Random(f'{seed}/{task}/cases').sample(available, VALIDATION + CYCLES * (TRAIN + ADMISSION))
    anchors, extra = picked[:VALIDATION], picked[VALIDATION:]
    roster = Random(f'{seed}/{task}/roster').sample([name for name in plan['programs'] if name != START], 2 * CYCLES)
    return [(tuple(roster[2 * i:2 * i + 2]), anchors, extra[i * (TRAIN + ADMISSION):i * (TRAIN + ADMISSION) + TRAIN],
             extra[i * (TRAIN + ADMISSION) + TRAIN:(i + 1) * (TRAIN + ADMISSION)]) for i in range(CYCLES)]


def play(matrix, layouts, seed, method, holdout):
    def rows(cases):
        return tuple(Row(str(case), 'task') for case in cases)

    training = {case for _, _, train, _ in layouts for case in train}
    validation = {case for _, anchors, _, _ in layouts for case in anchors}
    admission = {case for _, _, _, current in layouts for case in current}
    if (training & validation or admission & (training | validation) or holdout & (training | validation | admission)
            or len(admission) != sum(len(cases) for _, _, _, cases in layouts)):
        raise ValueError('The trial must protect all scheduled admission and holdout cases')
    search_reads, admission_reads = {}, {}
    decisions = []

    def read(prompt, case, *, proof=False):
        allowed = admission if proof else validation | training if method in GEPA else validation
        if case not in allowed or prompt not in matrix:
            raise ValueError('A lookup left its case or prompt scope')
        cache = admission_reads if proof else search_reads
        if (prompt, case) not in cache:
            cache[prompt, case] = matrix[prompt][case] == '1'
        return cache[prompt, case]

    def qualify(prompt, row, _repeat):
        return read(prompt, int(row.id), proof=True)

    selected = START
    if method in (CPO, UNRESTRICTED):
        cycles = [WitnessCycle(candidates, rows(anchors), rows(current), seed + i)
                  for i, (candidates, anchors, _, current) in enumerate(layouts)]
        result = run_rotating_witness_episode(START, cycles, lambda p, row: Observation(read(p, int(row.id)), {}),
                                              qualify=qualify, metric_limit=portable.CAPS[CPO],
                                              max_admissions=1 if method == CPO else CYCLES)
        selected = result.prompt
        decisions = [cycle.qualification.status if cycle.qualification else 'no-nominee' for cycle in result.cycles]
    elif method != RETAIN:
        condition = CONTROLS[method]
        for i, (candidates, anchors, train, current) in enumerate(layouts):
            anchors = anchors[:condition['validationRows']]
            cap = condition['searchCap']
            local = set()
            allowed = set(anchors) | (set(train) if method in GEPA else set())

            def lookup(prompt, case):
                if prompt not in (selected, *candidates) or case not in allowed:
                    raise ValueError('A control left its enrolled roster or training and validation panel')
                local.add((prompt, case))
                if len(local) > cap:
                    raise ValueError('A control exceeded its paid search ceiling')
                return read(prompt, case)

            if method in GEPA:
                nominee = portable.native(selected, candidates, train, anchors, lookup, batched=method.startswith('gepa-batched'),
                                          cap=cap, seed=seed + i)
            else:
                nominee = pool.successive_halving((selected, *candidates), anchors, lookup, cap)
            if nominee == selected:
                decisions.append('no-nominee')
                continue
            proof = certify_paired_qualification(selected, nominee, rows(current), qualify, seed=seed + i)
            selected = proof.prompt
            decisions.append(proof.status)
            break
    counts = {'searchLookups': len(search_reads), 'admissionLookups': len(admission_reads),
              'paidLookups': len(search_reads) + len(admission_reads), 'admissions': sum(s != 'no-nominee' for s in decisions),
              'promotions': decisions.count('promoted'), 'occupiedCycles': len(decisions)}
    return selected, counts, {'selected': selected, 'decisions': decisions, 'search': list(search_reads.items()),
                               'admission': list(admission_reads.items())}


def strongest(allowed, scores, costs):
    return min(allowed, key=lambda method: (-scores[method], costs[method], method))


def compare(plan, panels, methods):
    scores = Counter()
    costs = Counter()
    for totals, vectors in panels:
        scores.update({method: sum(vector) for method, vector in vectors.items()})
        costs.update({method: stat['paidLookups'] for method, stat in totals.items()})
    eligible = [method for method in methods if costs[method] <= costs[CPO]]
    if not eligible:
        return None
    winner = strongest(eligible, scores, costs)
    rng, differences, selections = Random(plan['resampleSeed']), [], Counter()
    for _ in range(plan['draws']):
        sampled = Counter()
        for _, vectors in panels:
            indices = rng.choices(range(HOLDOUT), k=HOLDOUT)
            sampled.update({method: sum(vectors[method][index] for index in indices) for method in (CPO, *eligible)})
        selected = strongest(eligible, sampled, costs)
        selections[selected] += 1
        differences.append(sampled[CPO] - sampled[selected])
    paired = ranges(differences, len(panels) * HOLDOUT * len(SEEDS))
    return {'control': winner, 'passDelta': scores[CPO] - scores[winner], 'paidLookupDelta': costs[CPO] - costs[winner],
            'affordableControls': eligible, 'controlSelectionsInPairedDraws': dict(selections), **paired,
            'positiveLowerEndpoint': paired['interval95PercentagePoints'][0] > 0}


def execute(plan, archive):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Load the hash-pinned GEPA 0.1.4 package')
    results, measurements = {}, []
    families = {'nativeGEPA': GEPA, 'allControlsAndRetain': (RETAIN, *GEPA, *HALVING)}
    for task in TASKS:
        panel = archive[task]
        held = sorted(Random(f"{plan['holdoutSeed']}/{task}").sample(range(len(panel['caseIDs'])), HOLDOUT))
        excluded = set(held)
        totals, evidence = {method: Counter() for method in ARMS}, {method: [0] * HOLDOUT for method in ARMS}
        traces = {method: [] for method in ARMS}
        for seed in SEEDS:
            layouts = schedule(plan, task, seed, held)
            for method in ARMS:
                winner, counts, trace = play(panel['correctness'], layouts, seed, method, excluded)
                totals[method].update(counts)
                decisions = [panel['correctness'][winner][case] == '1' for case in held]
                totals[method]['holdoutPasses'] += sum(decisions)
                evidence[method] = [old + passed for old, passed in zip(evidence[method], decisions, strict=True)]
                traces[method].append(trace)
        measurements.append((totals, evidence))
        results[task] = {'heldCaseSha256': digest([panel['caseIDs'][case] for case in held]),
                         'decisions': HOLDOUT * len(SEEDS), 'arms': {m: dict(v, traceSha256=digest(traces[m]))
                                                                    for m, v in totals.items()},
                         'comparisons': {name: compare(plan, [(totals, evidence)], methods)
                                         for name, methods in families.items()}}
    aggregate = {method: sum((totals[method] for totals, _ in measurements), Counter()) for method in ARMS}
    pooled = {name: compare(plan, measurements, methods) for name, methods in families.items()}
    qualified = all(entry['allControlsAndRetain']['positiveLowerEndpoint']
                    for entry in [pooled, *(task['comparisons'] for task in results.values())])
    return {'plan': plan, 'planSha256': digest(plan), 'tasks': results, 'totals': aggregate, 'pooledComparisons': pooled,
            'qualified': qualified, 'newProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan = prepare()
    seal = digest(plan)
    if args.corpus is None and args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.corpus is None or args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the pinned corpus, current seal, and a fresh report path')
    report = execute(plan, load_corpus(args.corpus.read_bytes()))
    with args.out.open('x') as file:
        json.dump(report, file, sort_keys=True, indent=2)
        file.write('\n')


if __name__ == '__main__':
    main()
