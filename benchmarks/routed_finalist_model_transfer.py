"""Test the frozen two-miss routing rule on unused archived model splits."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import balanced_finalist_race as race
from benchmarks import four_case_qualification_transfer as capture
from benchmarks import gepa_paid_cap_transfer as gepa
from benchmarks import independent_mmlu_transfer as transfer
from benchmarks.prompteval_transfer import holdout
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'docs/routed-finalist-model-transfer-design-v1.json'
PARENT_SHA256 = '15be9078e23388833f4971a20953924dd69d26b204705de04340a5fe175f5b83'
SUBJECTS = ('abstract_algebra', 'business_ethics', 'college_mathematics', 'conceptual_physics',
            'human_aging', 'jurisprudence', 'management', 'world_religions')
MODELS = ('codellama_codellama_34b_instruct', 'ibm_mistralai_merlinite_7b')
EXPECTED = [(s, m) for s in SUBJECTS for m in MODELS]
CANDIDATE = 'cpo-two-miss'
CPO = {CANDIDATE: 'wide-after-two-misses', 'cpo-seeded': 'seeded', 'cpo-always-wide': 'balanced-six'}
PRIMARY = ('gepa-batched-52', 'gepa-sequential-52')
GEPA = {PRIMARY[0]: (True, 52), PRIMARY[1]: (False, 52),
        'gepa-batched-44': (True, 44), 'gepa-sequential-31': (False, 31)}
METHODS = (*CPO, *GEPA, 'retain-start')


def design():
    raw = (ROOT / 'docs/balanced-finalist-race-results-v1.json').read_bytes()
    prior = transfer.read_json(raw)
    parent, _, _ = race.prepare('mmlu')
    if sha256(raw).hexdigest() != PARENT_SHA256 or prior['mmlu']['planSha256'] != digest(parent):
        raise ValueError('The routing pilot differs from its published receipts')
    prior_subjects = {name.split('/')[0] for phase in prior.values() for name in phase['panels']}
    if prior_subjects.intersection(SUBJECTS):
        raise ValueError('The evaluation subject list overlaps the routing pilot')
    origin = transfer.design()
    return {
        'protocol': 'cpo-routed-finalist-model-transfer-v1', 'subjects': list(SUBJECTS), 'models': list(MODELS),
        **{k: origin[k] for k in ('sourceDataset', 'sourceRevision', 'sourceLicense', 'templateCount', 'holdout')},
        'parentPlanSha256': digest(parent), 'parentReportSha256': PARENT_SHA256, 'schedule': parent['schedule'],
        'searchCap': parent['searchCap'], 'validationRows': parent['validationRows'], 'gepaVersion': parent['gepaVersion'],
        'cpoSettings': CPO, 'gepaSettings': {key: {'batched': b, 'cap': cap} for key, (b, cap) in GEPA.items()},
        'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in (
            'benchmarks/routed_finalist_model_transfer.py', 'benchmarks/balanced_finalist_race.py',
            'benchmarks/four_case_qualification_transfer.py', 'benchmarks/gepa_paid_cap_transfer.py',
            'benchmarks/independent_mmlu_transfer.py', 'cpo/pool.py', 'cpo/paired_qualification.py')},
        'primaryComparison': {'candidate': CANDIDATE, 'controls': list(PRIMARY), 'minimumLookupSavingPercent': 10,
                              'minimumLowerRangePassDifference': 0},
        'bootstrapDraws': 4096, 'bootstrapSeed': 20261123,
        'scope': ('Freeze settings before reading these model outcomes. Subjects have archived evidence from '
                  'other models, and none appeared in the routing pilot. Keep both models and all episodes '
                  'paired within each resampled case and use the minimum gap against the two primary controls.'),
    }


def capture_scores(plan):
    transfer.check_revision()
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(capture.capture_panel, subject, model, plan['templateCount']) for subject, model in EXPECTED]
        panels = [job.result() for job in jobs]
    transfer.check_revision()
    result = {'sourceDataset': transfer.DATASET, 'observedRepoRevision': transfer.REVISION, 'license': 'MIT',
              'designSha256BeforeCapture': digest(plan), 'panels': panels}
    with patch.object(transfer, 'EXPECTED', EXPECTED):
        transfer.check_corpus(result, plan)
    return result


def measure_panel(matrix, held, plan):
    costs, traces, frequencies = ({key: Counter() for key in METHODS}, {key: [] for key in METHODS},
                                  {key: Counter() for key in METHODS})
    original = plan['schedule']
    for seed in original['seeds']:
        start, _ = gepa.continuous.schedule(len(matrix[0]), len(matrix), held, seed, original)
        frequencies['retain-start'][int(start)] += 1
        costs['retain-start']['holdoutPasses'] += sum(matrix[int(start)][case] == '1' for case in held)
        for label, policy in CPO.items():
            count, trace = race.run(matrix, held, seed, plan, policy)
            costs[label].update(count)
            traces[label].append(trace)
            frequencies[label][int(trace[-1]['decision']['selected'])] += 1
        for label, (batched, cap) in GEPA.items():
            winner, count, peak, trace = gepa.reinvest_episode(matrix, held, seed, original,
                                                              {**plan, 'searchCap': cap}, batched=batched)
            if peak > cap:
                raise ValueError('An archived GEPA arm exceeded the declared paid search cap')
            costs[label].update(count)
            traces[label].append(trace)
            frequencies[label][int(winner)] += 1
    cases = {label: [sum(n for prompt, n in freq.items() if matrix[prompt][case] == '1') for case in held]
             for label, freq in frequencies.items()}
    if any(sum(values) != costs[label]['holdoutPasses'] for label, values in cases.items()):
        raise ValueError('Reconstructed case scores differ from the replay totals')
    return ({label: dict(cost, paidLookups=cost['searchPaid'] + cost['qualificationPaid'], traceSha256=digest(traces[label]))
             for label, cost in costs.items()}, cases)


def resample(plan, by_subject):
    controls = tuple(plan['primaryComparison']['controls'])
    rng = Random(plan['bootstrapSeed'])
    samples, joint = {label: [] for label in METHODS if label != CANDIDATE}, []
    for _ in range(plan['bootstrapDraws']):
        totals = Counter()
        for subject in sorted(by_subject):
            vectors = by_subject[subject]
            size = len(vectors[controls[0]])
            draws = rng.choices(range(size), k=size)
            totals.update({label: sum(s[i] for i in draws) for label, s in vectors.items()})
        for label in samples:
            samples[label].append(totals[label])
        joint.append(min(totals[label] for label in controls))
    return {label: capture.interval(values) for label, values in samples.items()}, capture.interval(joint)


def verdict(plan, totals, joint):
    rule = plan['primaryComparison']
    limit, minimum = 100 - rule['minimumLookupSavingPercent'], rule['minimumLowerRangePassDifference']
    if (any(100 * totals[CANDIDATE]['paidLookups'] > limit * totals[label]['paidLookups'] for label in rule['controls'])
            or joint[1] < minimum):
        return 'failed'
    return 'passed' if joint[0] >= minimum else 'inconclusive'


def replay(raw, plan):
    corpus = transfer.read_json(raw)
    with patch.object(transfer, 'EXPECTED', EXPECTED):
        transfer.check_corpus(corpus, plan)
    panels, totals, by_subject = {}, {}, {}
    for row in corpus['panels']:
        subject, model, matrix = (row[key] for key in ('subject', 'model', 'correctness'))
        held = holdout(subject, len(matrix[0]))
        points, cases = measure_panel(matrix, held, plan)
        subjects = by_subject.setdefault(subject, {label: [0] * len(held) for label in METHODS if label != CANDIDATE})
        for label, dest in subjects.items():
            for i, (candidate, control) in enumerate(zip(cases[CANDIDATE], cases[label], strict=True)):
                dest[i] += candidate - control
        for label, point in points.items():
            totals.setdefault(label, Counter()).update({k: point[k] for k in ('holdoutPasses', 'paidLookups')})
        panels[f'{subject}/{model}'] = {'holdoutCaseIDs': held, 'methods': points}
    ranges, joint = resample(plan, by_subject)
    return {'plan': plan, 'planSha256': digest(plan), 'corpusSha256': sha256(raw).hexdigest(), 'panels': panels,
            'totals': totals, 'caseSensitivityRanges': ranges, 'simultaneousPrimaryRange': joint,
            'primaryGate': verdict(plan, totals, joint)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument('--design', action='store_true')
    mode.add_argument('--capture', action='store_true')
    mode.add_argument('--replay', type=Path)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan = design()
    seal = digest(plan)
    manifest = {'design': plan, 'designSha256': seal}
    if args.design and args.execute is None and args.out is None:
        print(json.dumps(manifest, sort_keys=True, indent=2))
        return
    if args.design or args.execute != seal or args.out is None or args.out.exists():
        cli.error('Capture and replay require the sealed design and a fresh output path')
    if transfer.read_json(DESIGN.read_bytes()) != manifest:
        raise ValueError('The checked-in design differs from the sealed plan')
    if args.capture:
        result = capture_scores(plan)
    else:
        if version('gepa') != plan['gepaVersion']:
            raise ValueError('Use the pinned GEPA version')
        result = replay(args.replay.read_bytes(), plan)
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
