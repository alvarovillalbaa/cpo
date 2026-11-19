"""Test four-case CPO qualification on unused archived subjects and model splits."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import independent_mmlu_transfer as transfer
from benchmarks import qualification_repeat_sensitivity as previous
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
SUBJECTS = ('college_chemistry', 'college_medicine', 'human_sexuality', 'medical_genetics', 'professional_law', 'virology')
MODELS = ('google_flan_t5_xl', 'meta_llama_llama_3_70b_instruct')
EXPECTED = [(subject, model) for subject in SUBJECTS for model in MODELS]
REFERENCE_SHA256 = 'b90014840d8dcad8e23a91ebb852082fbfe6a5e5c1c5ffd9461aefa7263e083a'
DESIGN = ROOT / 'docs/four-case-qualification-transfer-design-v1.json'
PAGE_SIZE = 25
CANDIDATE = 'cpo-four-52'
PRIMARY = ('gepa-batched-eight-52', 'gepa-sequential-eight-52')
METHODS = {
    CANDIDATE: ('cpo', 52, 'four-cases'),
    'cpo-eight-52': ('cpo', 52, 'eight-cases'),
    'gepa-batched-four-52': ('batched', 52, 'four-cases'),
    PRIMARY[0]: ('batched', 52, 'eight-cases'),
    PRIMARY[1]: ('sequential', 52, 'eight-cases'),
    'gepa-batched-eight-44': ('batched', 44, 'eight-cases'),
}


def design():
    report = (ROOT / 'docs/qualification-repeat-sensitivity-results-v1.json').read_bytes()
    if sha256(report).hexdigest() != REFERENCE_SHA256:
        raise ValueError('The retrospective source results differ from the pinned report')
    pilot = transfer.read_json(report)
    for phase, recorded in pilot.items():
        if digest(previous.prepare(phase)[0]) != recorded['planSha256']:
            raise ValueError('A retrospective source plan differs from replay')
    base = transfer.design()
    return {
        'protocol': 'cpo-four-case-qualification-transfer-v1', 'subjects': list(SUBJECTS), 'models': list(MODELS),
        **{key: base[key] for key in ('sourceDataset', 'sourceRevision', 'sourceLicense', 'templateCount',
                                     'validationRows', 'schedule', 'holdout', 'gepaVersion')},
        'priorReportSha256': REFERENCE_SHA256,
        'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in (
            'benchmarks/four_case_qualification_transfer.py', 'benchmarks/qualification_repeat_sensitivity.py',
            'benchmarks/independent_mmlu_transfer.py', 'benchmarks/archive_complementarity_transfer.py',
            'benchmarks/gepa_paid_cap_transfer.py', 'cpo/paired_qualification.py')},
        'settings': {label: {'optimizer': mode, 'cap': cap, 'qualification': schedule}
                     for label, (mode, cap, schedule) in METHODS.items()},
        'primaryComparison': {'candidate': CANDIDATE, 'controls': list(PRIMARY), 'minimumLookupSavingPercent': 10,
                              'minimumLowerRangePassDifference': 0},
        'bootstrapDraws': 4096, 'bootstrapSeed': 20261121,
        'scope': ('Freeze settings before reading the selected subject and model outcomes. Resample cases within '
                  'each subject and keep both models and all episodes together. The primary statistic is the '
                  'smaller candidate pass difference against the two original GEPA modes on each draw.'),
    }


def capture_panel(subject, model, count):
    url = transfer.rows_url(subject, model)
    pages, records = [], []
    for offset in range(0, count, PAGE_SIZE):
        page_url = url.removesuffix('offset=0&length=100') + f'offset={offset}&length={PAGE_SIZE}'
        raw = transfer.get_public(page_url)
        payload = transfer.read_json(raw)
        if (payload['partial'] or payload['num_rows_total'] != count or
                [row['row_idx'] for row in payload['rows']] != list(range(offset, min(offset + PAGE_SIZE, count)))):
            raise ValueError('The capture requires full contiguous score pages')
        pages.append(payload)
        records.append({'url': page_url, 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw)})
    first = pages[0]
    if any(page['features'] != first['features'] for page in pages[1:]):
        raise ValueError('Outcome columns differ between pages')
    matrix, columns = transfer.decode_panel({**first, 'rows': [row for page in pages for row in page['rows']]}, count)
    return {'subject': subject, 'model': model, 'correctness': matrix, 'caseOrderSha256': columns,
            'rowsUrl': url, 'sourcePages': records}


def capture(plan):
    transfer.check_revision()
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(capture_panel, subject, model, plan['templateCount']) for subject, model in EXPECTED]
        panels = [job.result() for job in jobs]
    transfer.check_revision()
    corpus = {'sourceDataset': transfer.DATASET, 'observedRepoRevision': transfer.REVISION, 'license': 'MIT',
              'designSha256BeforeCapture': digest(plan), 'panels': panels}
    with patch.object(transfer, 'EXPECTED', EXPECTED):
        transfer.check_corpus(corpus, plan)
    return corpus


def episode(matrix, held, seed, plan):
    original = plan['schedule']
    width = len(matrix[0])
    start, layouts = archive.continuous.schedule(width, len(matrix), held, seed, original)
    qualification = {case for cycle in layouts for case in cycle['qualify']}
    other = set(held) | {case for cycle in layouts for role in ('train', 'validation') for case in cycle[role]}
    if qualification & other or len(qualification) != 8 * len(layouts):
        raise ValueError('Qualification panels must remain disjoint from search, holdout and each other')
    result = {'retain-start': (start, Counter(holdoutPasses=sum(matrix[int(start)][case] == '1' for case in held)), [])}
    for label, (mode, cap, schedule) in METHODS.items():
        branch = [{**cycle, 'qualify': previous.qualification_slots(cycle['qualify'], width, schedule)} for cycle in layouts]
        settings = {'validationRows': plan['validationRows'], 'searchCap': cap}
        with patch.object(archive.continuous, 'schedule', return_value=(start, branch)):
            if mode == 'cpo':
                counts, trace = archive.episode(matrix, held, seed, original, settings, 'recency')
                final = trace[-1]['decision']['selected']
            else:
                final, counts, peak, trace = transfer.gepa.reinvest_episode(
                    matrix, held, seed, original, settings, batched=mode == 'batched')
                if peak > cap:
                    raise ValueError('GEPA exceeded its declared paid cap')
        result[label] = final, counts, trace
    return result


def interval(samples):
    ordered = sorted(samples)
    return [ordered[(len(samples) - 1) * q // 1000] for q in (25, 975)]


def resample(plan, cases_by_subject):
    names = sorted(cases_by_subject)
    labels = (*METHODS, 'retain-start')
    vectors = {subject: {label: tuple(row[label] for row in cases_by_subject[subject].values()) for label in labels}
               for subject in names}
    draws = {label: [] for label in labels if label != CANDIDATE}
    worst = []
    rng = Random(plan['bootstrapSeed'])
    for _ in range(plan['bootstrapDraws']):
        sampled = Counter()
        for subject in names:
            values = vectors[subject]
            count = len(values[CANDIDATE])
            indexes = rng.choices(range(count), k=count)
            sampled.update({label: sum(scores[i] for i in indexes) for label, scores in values.items()})
        for label, differences in draws.items():
            differences.append(sampled[CANDIDATE] - sampled[label])
        worst.append(min(draws[label][-1] for label in PRIMARY))
    return {label: interval(values) for label, values in draws.items()}, interval(worst)


def classify(plan, totals, range_):
    rule = plan['primaryComparison']
    candidate_cost = totals[CANDIDATE]['paidLookups']
    threshold = rule['minimumLowerRangePassDifference']
    if any(100 * candidate_cost > (100 - rule['minimumLookupSavingPercent']) * totals[label]['paidLookups']
           for label in PRIMARY) or range_[1] < threshold:
        return 'failed'
    return 'passed' if range_[0] >= threshold else 'inconclusive'


def replay(plan, raw):
    corpus = transfer.read_json(raw)
    with patch.object(transfer, 'EXPECTED', EXPECTED):
        transfer.check_corpus(corpus, plan)
    panels, cases_by_subject, totals = {}, {}, {}
    for panel in corpus['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        held = transfer.transfer.holdout(subject, len(matrix[0]))
        cases = cases_by_subject.setdefault(subject, {case: Counter() for case in held})
        if tuple(cases) != tuple(held):
            raise ValueError('Both models must share ordered holdout cases')
        costs, traces, final_frequencies = {}, {}, {}
        for seed in plan['schedule']['seeds']:
            for label, (final, counts, trace) in episode(matrix, held, seed, plan).items():
                costs.setdefault(label, Counter()).update(counts)
                traces.setdefault(label, []).append(trace)
                final_frequencies.setdefault(label, Counter()).update([int(final)])
        points = {}
        for label, counts in costs.items():
            scores = {case: sum(freq for prompt, freq in final_frequencies[label].items() if matrix[prompt][case] == '1')
                      for case in held}
            if sum(scores.values()) != counts['holdoutPasses']:
                raise ValueError('Reconstructed case scores differ from optimizer totals')
            for case, passes in scores.items():
                cases[case][label] += passes
            point = dict(counts, paidLookups=counts['searchPaid'] + counts['qualificationPaid'],
                         traceSha256=digest(traces[label]))
            totals.setdefault(label, Counter()).update({key: point[key] for key in ('holdoutPasses', 'paidLookups')})
            points[label] = point
        panels[f'{subject}/{model}'] = {'holdoutCaseIDs': held, 'methods': points}
    ranges, simultaneous = resample(plan, cases_by_subject)
    return {'plan': plan, 'planSha256': digest(plan), 'corpusSha256': sha256(raw).hexdigest(), 'totals': totals,
            'panels': panels, 'caseSensitivityRanges': ranges, 'simultaneousPrimaryRange': simultaneous,
            'primaryGate': classify(plan, totals, simultaneous)}


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
    if args.design and args.execute is None and args.out is None:
        print(json.dumps({'design': plan, 'designSha256': seal}, sort_keys=True, indent=2))
        return
    if args.design or args.execute != seal or args.out is None or args.out.exists():
        cli.error('Capture and replay require the sealed design and a fresh output path')
    if transfer.read_json(DESIGN.read_bytes()) != {'design': plan, 'designSha256': seal}:
        raise ValueError('The checked-in design differs from this execution plan')
    if args.capture:
        result = capture(plan)
    else:
        if version('gepa') != plan['gepaVersion']:
            raise ValueError('Use the pinned GEPA version')
        result = replay(plan, args.replay.read_bytes())
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
