"""Compare frozen CPO and GEPA policies on unused archived subjects and models."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
from urllib.parse import urlencode

from benchmarks import archive_after_fresh_search as fresh
from benchmarks import archive_complementarity_transfer as archive
from benchmarks import episode_screen_adaptation as screens
from benchmarks import gepa_paid_cap_transfer as gepa
from benchmarks import prompteval_transfer as transfer
from benchmarks.prompteval_paid_witness import meets_gate
from cpo._contract import digest, unique_object


ROOT = Path(__file__).resolve().parents[1]
DATASET = 'PromptEval/PromptEval_MMLU_correctness'
REVISION = '1639d5ea14c362f6964f260ae81bd903af760187'
SUBJECTS = ('college_biology', 'machine_learning', 'nutrition', 'security_studies')
MODELS = ('google_gemma_7b_it', 'tiiuae_falcon_40b')
CPO = ('cpo-seeded-preflight', 'cpo-seeded-fresh-first')
METHODS = ('retain-start', *CPO, *gepa.METHODS)
EXPECTED = [(subject, model) for subject in SUBJECTS for model in MODELS]


def design():
    parent, original, *_ = archive.prepare('mmlu')
    paths = (Path(__file__), Path(fresh.__file__), Path(screens.__file__), Path(gepa.__file__),
             ROOT / 'cpo/lazy_incumbent.py', ROOT / 'cpo/paired_qualification.py',
             ROOT / 'cpo/fixed_pool_cycle.py', ROOT / 'cpo/challenger.py')
    return {
        'protocol': 'cpo-independent-mmlu-transfer-v1',
        'sourceDataset': DATASET, 'sourceRevision': REVISION, 'sourceLicense': 'MIT',
        'subjects': list(SUBJECTS), 'models': list(MODELS), 'templateCount': 100,
        'primary': CPO[0], 'methods': list(METHODS),
        'sourceSha256': {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in paths},
        'archivePlanSha256': digest(parent),
        **{k: parent[k] for k in ('searchCap', 'validationRows', 'gepaVersion', 'gate')},
        'schedule': {k: original[k] for k in ('poolSize', 'trainRows', 'validationRows', 'cycles',
                                              'qualificationRowsPerCycle', 'minimumQualificationGain', 'seeds')},
        'holdout': 'Use the existing seeded 30 percent split per subject, shared by both models.',
        'scope': ('Compare fixed policies on complete archived prompt template matrices. Compare each CPO arm '
                  'against both official paid-cap GEPA modes, with a retain-start reference.'),
    }


def read_json(raw):
    return json.loads(raw, object_pairs_hook=unique_object)


def rows_url(subject, model):
    query = urlencode({'dataset': DATASET, 'config': subject, 'split': model, 'offset': 0, 'length': 100})
    return 'https://datasets-server.huggingface.co/rows?' + query


def get_public(url):
    return subprocess.check_output(['/usr/bin/curl', '--disable', '--silent', '--show-error', '--fail',
                                    '--location', '--proto', '=https', '--proto-redir', '=https',
                                    '--connect-timeout', '10', '--max-time', '30',
                                    '--max-filesize', '2000000', url])


def decode_panel(payload, template_count):
    ordered = sorted(payload['features'], key=lambda feature: feature['feature_idx'])
    columns = [feature['name'] for feature in ordered]
    rows = payload['rows']
    if ([f['feature_idx'] for f in ordered] != list(range(len(columns))) or
            columns != [f'example_{i}' for i in range(len(columns))] or
            len(rows) != template_count or [r['row_idx'] for r in rows] != list(range(template_count)) or
            payload.get('partial') or payload['num_rows_total'] != template_count):
        raise ValueError('Expected complete ordered template rows and sequential example columns')
    result = []
    for row in rows:
        values = row['row']
        if values.keys() != set(columns) or row.get('truncated_cells') or any(
                type(v) is not int or v not in (0, 1) for v in values.values()):
            raise ValueError('Every template and case must have an exact untruncated binary result')
        result.append(''.join(str(values[col]) for col in columns))
    return result, digest(columns)


def check_revision():
    raw = get_public('https://huggingface.co/api/datasets/' + DATASET)
    meta = read_json(raw)
    if meta['sha'] != REVISION or meta['cardData']['license'] != 'mit':
        raise ValueError('The public dataset revision or license changed')


def capture(plan):
    check_revision()
    panels = []
    for subject, model in EXPECTED:
        url = rows_url(subject, model)
        raw = get_public(url)
        matrix, columns = decode_panel(read_json(raw), plan['templateCount'])
        panels.append({'subject': subject, 'model': model, 'correctness': matrix, 'caseOrderSha256': columns,
                       'rowsUrl': url, 'sourceBytes': len(raw), 'viewerResponseSha256': sha256(raw).hexdigest()})
    check_revision()
    corpus = {'sourceDataset': DATASET, 'observedRepoRevision': REVISION, 'license': 'MIT',
              'designSha256BeforeCapture': digest(plan), 'panels': panels}
    check_corpus(corpus, plan)
    return corpus


def check_corpus(corpus, plan):
    panels = corpus['panels']
    if (corpus['designSha256BeforeCapture'] != digest(plan) or corpus['observedRepoRevision'] != REVISION or
            corpus['sourceDataset'] != DATASET or corpus['license'] != 'MIT' or
            [(p['subject'], p['model']) for p in panels] != EXPECTED):
        raise ValueError('The corpus must match the frozen transfer design')
    minimum = plan['schedule']['cycles'] * plan['schedule']['qualificationRowsPerCycle']
    minimum += plan['schedule']['trainRows'] + plan['schedule']['validationRows']
    cases = {}
    for p in panels:
        subject, model, matrix = (p[k] for k in ('subject', 'model', 'correctness'))
        count = len(matrix[0]) if matrix and isinstance(matrix[0], str) else 0
        if (len(matrix) != plan['templateCount'] or count - count * 30 // 100 < minimum or
                any(not isinstance(row, str) or len(row) != count or set(row) - {'0', '1'} for row in matrix) or
                p['rowsUrl'] != rows_url(subject, model) or
                cases.setdefault(subject, (count, p['caseOrderSha256'])) != (count, p['caseOrderSha256'])):
            raise ValueError('Each subject needs complete matrices using the same ordered cases for both models')


def run_panel(panel, plan):
    matrix, subject = panel['correctness'], panel['subject']
    held = transfer.holdout(subject, len(matrix[0]))
    original = plan['schedule']
    totals = {method: Counter() for method in METHODS}
    traces = {method: [] for method in METHODS}
    per_seed = {method: [] for method in METHODS}
    for seed in original['seeds']:
        start, _ = archive.continuous.schedule(len(matrix[0]), len(matrix), held, seed, original)
        retain = {'holdoutPasses': sum(matrix[int(start)][case] == '1' for case in held)}
        comparisons = {'retain-start': (retain, start)}
        comparisons[CPO[0]] = archive.episode(matrix, held, seed, original, plan, 'recency')
        comparisons[CPO[1]] = fresh.run_fresh_first(matrix, held, seed, original, plan, 'seeded')
        for index, method in enumerate(gepa.METHODS):
            _, measured, peak, trace = gepa.reinvest_episode(matrix, held, seed, original, plan, batched=bool(index))
            if peak > plan['searchCap']:
                raise ValueError('The official paid search exceeded its ceiling')
            comparisons[method] = measured, trace
        for method, (measured, trace) in comparisons.items():
            totals[method].update(measured)
            traces[method].append(trace)
            per_seed[method].append(measured['holdoutPasses'])
    methods = {method: dict(total, paidLookups=total['searchPaid'] + total['qualificationPaid'],
                            traceSha256=digest(traces[method]),
                            pairedPassesVsStart=screens.paired_deltas(per_seed[method], per_seed['retain-start']))
               for method, total in totals.items()}
    gates = {method: {ref: meets_gate(methods[method], methods[ref]) for ref in gepa.METHODS} for method in CPO}
    return {'holdoutCaseIDs': held, 'holdoutDecisions': len(held) * len(original['seeds']),
            'methods': methods, 'gates': gates}


def replay(plan, raw):
    corpus = read_json(raw)
    check_corpus(corpus, plan)
    panels = {f"{p['subject']}/{p['model']}": run_panel(p, plan) for p in corpus['panels']}
    return {'plan': plan, 'planSha256': digest(plan), 'corpusSha256': sha256(raw).hexdigest(), 'panels': panels,
            'clearsBothGates': {m: [name for name, row in panels.items() if all(row['gates'][m].values())]
                                for m in CPO}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument('--design', action='store_true')
    operation.add_argument('--capture', action='store_true')
    operation.add_argument('--replay', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan = design()
    seal = digest(plan)
    if args.design and args.execute is None and args.out is None:
        print(json.dumps({'design': plan, 'designSha256': seal}, sort_keys=True, indent=2))
        return
    if args.design or args.execute != seal or args.out is None or args.out.exists():
        parser.error('Capture and replay require the frozen design seal and a fresh output path')
    if args.capture:
        result = capture(plan)
    else:
        if version('gepa') != plan['gepaVersion']:
            raise ValueError('Use the pinned GEPA version')
        result = replay(plan, args.replay.read_bytes())
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
