"""Freeze a qualification rule before extracting new BBH and LMentry outcomes."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path, PurePosixPath
from random import Random
from unittest.mock import patch
from zipfile import ZipFile

from benchmarks import four_case_qualification_transfer as four
from benchmarks import gepa_paid_cap_transfer as gepa
from benchmarks import qualification_role_transfer as role
from benchmarks.independent_mmlu_transfer import read_json
from benchmarks.prompteval_transfer import holdout
from cpo import Row
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'docs/tie-extension-cross-benchmark-design-v1.json'
SOURCE = 'https://github.com/SLAB-NLP/Multi-Prompt-LLM-Evaluation#raw-model-responses'
ZIP_SIZE = 201185029
DIRECTORY_OFFSET = 201103234
DIRECTORY_SHA256 = '80223a5932a20eac284d1641753401de5207651bf278e2742e621fdddece673e'
SOURCE_ETAG = '1712686494526539d'
PARENT_SHA256 = '8869663ddeb6c9e2331c927c9fb4bdc54d8266f356cb67dc1fb44c34c4ba25b7'
MODELS = ('falcon-7b-instruct', 'mpt-7b-instruct')
TASKS = {'BBH': ('movie_recommendation', 'ruin_names', 'salient_translation_error_detection', 'snarks'),
         'LMentry': ('homophones', 'word_before')}
GROUPS = ('default', 'rephrase', 'cot', 'gradual')
GEPA = {f'gepa-{mode}-{policy}': (mode == 'batched', policy == 'ties')
        for mode in ('batched', 'sequential') for policy in ('eight', 'ties')}
CANDIDATE = 'cpo-ties'
METHODS = (CANDIDATE, 'cpo-eight', *GEPA, 'retain-start')


def design():
    parent, schedule, _, _ = role.prepare('transfer')
    raw = (ROOT / 'docs/qualification-role-transfer-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != PARENT_SHA256 or read_json(raw)['transfer']['planSha256'] != digest(parent):
        raise ValueError('The tie-extension source experiment must match the published receipts')
    return {
        'protocol': 'cpo-tie-extension-cross-benchmark-v1', 'tasks': {name: list(tasks) for name, tasks in TASKS.items()},
        'models': list(MODELS), 'sourceDataset': SOURCE, 'sourceDirectorySha256': DIRECTORY_SHA256,
        'sourceDirectoryOffset': DIRECTORY_OFFSET, 'sourceZipSize': ZIP_SIZE, 'sourceETag': SOURCE_ETAG,
        'license': 'CDLA-Permissive-2.0', 'parentReportSha256': PARENT_SHA256, 'parentPlanSha256': digest(parent),
        'schedule': schedule, 'validationRows': parent['validationRows'], 'searchCap': parent['searchCap'],
        'gepaVersion': parent['gepaVersion'], 'methods': list(METHODS), 'templateCount': 100,
        'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in (
            'benchmarks/tie_extension_cross_benchmark.py', 'benchmarks/qualification_role_transfer.py',
            'benchmarks/gepa_paid_cap_transfer.py', 'benchmarks/archive_complementarity_transfer.py',
            'cpo/paired_qualification.py')},
        'primaryComparison': {'candidate': CANDIDATE, 'controls': list(GEPA), 'minimumLookupSavingPercent': 10,
                              'minimumLowerRangePassDifference': 0},
        'bootstrapDraws': 4096, 'bootstrapSeed': 20261122,
        'scope': ('Read only sealed recorded outcome panels. Both GEPA modes run their original eight-case '
                  'qualification and the same four-case tie extension. Keep both model panels and all '
                  'episodes paired within each resampled case; use the minimum gap against the controls.'),
    }


def expected_panels():
    return [(f'{benchmark.lower()}-{task}', benchmark, task, model) for benchmark, tasks in TASKS.items()
            for task in tasks for model in MODELS]


def capture(source, plan):
    with source.open('rb') as stream:
        stream.seek(DIRECTORY_OFFSET)
        directory = stream.read(ZIP_SIZE - DIRECTORY_OFFSET + 1)
    if len(directory) != ZIP_SIZE - DIRECTORY_OFFSET or sha256(directory).hexdigest() != DIRECTORY_SHA256:
        raise ValueError('The response ZIP directory differs from the frozen source')
    panels = []
    with ZipFile(source) as archive:
        for subject, benchmark, task, model in expected_panels():
            prefix = 'big_bench_hard' if benchmark == 'BBH' else 'lmentry'
            suffix = (benchmark, task, f'{prefix}_{task}_{model}_temp0.3_mt10_0.json')
            matches = [item for item in archive.infolist() if PurePosixPath(item.filename).parts[-3:] == suffix]
            if len(matches) != 1 or matches[0].file_size > 32_000_000:
                raise ValueError(f'Expected one bounded response member for {subject}/{model}')
            member = matches[0]
            raw = archive.read(member)
            samples = read_json(raw)['samples']
            case_ids = sorted(samples, key=int)
            first = samples[case_ids[0]]
            keys = [(group, key) for group in GROUPS for key in first[group]]
            keys.sort(key=lambda key: (key[0] != 'default', digest((subject, *key))))
            keys = keys[:plan['templateCount']]
            vectors = []
            for group, key in keys:
                values = [samples[case][group][key]['auto_validation'] for case in case_ids]
                if any(type(v) not in (bool, int) or v not in (0, 1) for v in values):
                    raise ValueError('The archived grader must provide complete binary outcomes')
                vectors.append(''.join('1' if v else '0' for v in values))
            panels.append({'subject': subject, 'benchmark': benchmark, 'task': task, 'model': model,
                           'caseIDs': case_ids, 'templateIDs': [list(key) for key in keys], 'correctness': vectors,
                           'sourceMember': member.filename, 'sourceMemberSha256': sha256(raw).hexdigest(),
                           'sourceMemberCRC32': f'{member.CRC:08x}'})
    corpus = {'designSha256BeforeExtraction': digest(plan), 'sourceDirectorySha256': DIRECTORY_SHA256,
              'sourceDataset': SOURCE, 'license': plan['license'], 'panels': panels}
    check_corpus(corpus, plan)
    return corpus


def check_corpus(corpus, plan):
    if (corpus['designSha256BeforeExtraction'] != digest(plan) or corpus['sourceDirectorySha256'] != DIRECTORY_SHA256
            or corpus['sourceDataset'] != SOURCE or corpus['license'] != plan['license'] or
            [tuple(p[key] for key in ('subject', 'benchmark', 'task', 'model')) for p in corpus['panels']]
            != expected_panels()):
        raise ValueError('The corpus must match the frozen source and panel list')
    layouts = {}
    for panel in corpus['panels']:
        cases, keys, scores = [panel[key] for key in ('caseIDs', 'templateIDs', 'correctness')]
        count = len(cases)
        if (count - count * 30 // 100 < 68 or len(set(cases)) != count
                or len(keys) != plan['templateCount'] or len({tuple(key) for key in keys}) != len(keys)
                or len(scores) != len(keys) or any(not isinstance(row, str) or len(row) != count
                                                   or set(row) - {'0', '1'} for row in scores)
                or layouts.setdefault(panel['subject'], (cases, keys)) != (cases, keys)):
            raise ValueError('The two models must share ordered cases and templates with complete binary outcomes')


def gepa_ties(matrix, held, seed, plan, *, batched):
    def fresh(incumbent, challenger, rows, qualify, *, minimum_gain, seed):
        if minimum_gain != 1:
            raise ValueError('Tie extension expects the original strict gain')
        return role.qualify_ties(incumbent, challenger, rows, qualify, seed=seed)[0]

    def retry(incumbent, challenger, cohort, qualify):
        rows = [Row(str(case), 'task') for case in cohort]
        result, _ = role.qualify_ties(incumbent, challenger, rows, lambda p, row, _: qualify(p, int(row.id)))
        observed = [(row.prompt, int(row.row_id), row.passed) for row in result.observations]
        return result.status == 'promoted', sum(p == challenger for p, _, _ in observed), observed

    with (patch.object(gepa, 'certify_paired_qualification', fresh), patch.object(gepa.archive, 'qualify_archived', retry)):
        return gepa.reinvest_episode(matrix, held, seed, plan['schedule'], plan, batched=batched)


def measure_panel(matrix, held, plan):
    scores = {name: Counter() for name in METHODS}
    traces = {name: [] for name in METHODS}
    frequency = {name: Counter() for name in METHODS}
    original = plan['schedule']
    for seed in original['seeds']:
        start, _ = gepa.continuous.schedule(len(matrix[0]), len(matrix), held, seed, original)
        frequency['retain-start'][int(start)] += 1
        scores['retain-start']['holdoutPasses'] += sum(matrix[int(start)][case] == '1' for case in held)
        for policy, label in (('eight', 'cpo-eight'), ('extend-ties', CANDIDATE)):
            costs, trace = role.run(matrix, held, seed, original, plan, policy)
            scores[label].update(costs)
            traces[label].append(trace)
            frequency[label][int(trace[-1]['decision']['selected'])] += 1
        for label, (batched, ties) in GEPA.items():
            if ties:
                final, costs, peak, trace = gepa_ties(matrix, held, seed, plan, batched=batched)
            else:
                final, costs, peak, trace = gepa.reinvest_episode(matrix, held, seed, original, plan, batched=batched)
            if peak > plan['searchCap']:
                raise ValueError('An archived GEPA arm exceeded the original paid search cap')
            scores[label].update(costs)
            traces[label].append(trace)
            frequency[label][int(final)] += 1
    cases_by_method = {label: [sum(freq for p, freq in frequency[label].items() if matrix[p][case] == '1')
                               for case in held] for label in METHODS}
    if any(sum(points) != scores[label]['holdoutPasses'] for label, points in cases_by_method.items()):
        raise ValueError('Holdout case counts differ from the optimizer receipts')
    return ({label: dict(cost, paidLookups=cost['searchPaid'] + cost['qualificationPaid'],
                        traceSha256=digest(traces[label])) for label, cost in scores.items()}, cases_by_method)


def resample(plan, case_deltas):
    rng = Random(plan['bootstrapSeed'])
    controls = tuple(plan['primaryComparison']['controls'])
    labels = [label for label in METHODS if label != CANDIDATE]
    samples, worst = {label: [] for label in labels}, []
    for _ in range(plan['bootstrapDraws']):
        totals = Counter()
        for subject in sorted(case_deltas):
            vectors = case_deltas[subject]
            size = len(vectors[labels[0]])
            sampled = rng.choices(range(size), k=size)
            totals.update({label: sum(vectors[label][i] for i in sampled) for label in labels})
        for label in labels:
            samples[label].append(totals[label])
        worst.append(min(totals[control] for control in controls))
    return {label: four.interval(values) for label, values in samples.items()}, four.interval(worst)


def verdict(plan, totals, joint):
    rule = plan['primaryComparison']
    limit = 100 - rule['minimumLookupSavingPercent']
    minimum = rule['minimumLowerRangePassDifference']
    if (any(100 * totals[CANDIDATE]['paidLookups'] > limit * totals[label]['paidLookups'] for label in rule['controls'])
            or joint[1] < minimum):
        return 'failed'
    return 'passed' if joint[0] >= minimum else 'inconclusive'


def replay(raw, plan):
    corpus = read_json(raw)
    check_corpus(corpus, plan)
    panels, totals, case_deltas = {}, {}, {}
    for row in corpus['panels']:
        subject, model, matrix = (row[key] for key in ('subject', 'model', 'correctness'))
        held = holdout(subject, len(matrix[0]))
        points, scores = measure_panel(matrix, held, plan)
        accum = case_deltas.setdefault(subject, {label: [0] * len(held) for label in METHODS if label != CANDIDATE})
        for label, dest in accum.items():
            for i, (candidate, control) in enumerate(zip(scores[CANDIDATE], scores[label], strict=True)):
                dest[i] += candidate - control
        for label, point in points.items():
            totals.setdefault(label, Counter()).update({k: point[k] for k in ('holdoutPasses', 'paidLookups')})
        panels[f'{subject}/{model}'] = {'holdoutCaseIDs': [row['caseIDs'][case] for case in held], 'methods': points}
    ranges, joint = resample(plan, case_deltas)
    return {'plan': plan, 'planSha256': digest(plan), 'corpusSha256': sha256(raw).hexdigest(), 'panels': panels,
            'totals': totals, 'caseSensitivityRanges': ranges, 'simultaneousPrimaryRange': joint,
            'primaryGate': verdict(plan, totals, joint)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument('--design', action='store_true')
    mode.add_argument('--capture', type=Path)
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
    if read_json(DESIGN.read_bytes()) != manifest:
        raise ValueError('The checked-in design differs from the sealed plan')
    if args.capture is not None:
        result = capture(args.capture, plan)
    else:
        if version('gepa') != plan['gepaVersion']:
            raise ValueError('Use the pinned GEPA version')
        result = replay(args.replay.read_bytes(), plan)
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
