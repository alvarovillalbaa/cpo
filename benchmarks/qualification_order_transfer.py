"""Freeze and replay expected-cost CPO on unused BBH and LMentry model splits."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from importlib.metadata import version
from io import BytesIO
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from benchmarks import cross_benchmark_prompt_race as cross
from benchmarks import family_qualification_order as family
from benchmarks import gepa_paid_cap_transfer as gepa
from benchmarks import late_miss_transfer as inventory
from benchmarks import routed_score_allocation as route
from benchmarks import tie_extension_cross_benchmark as archive
from benchmarks import witness_validation_cost_frontier as frontier
from benchmarks.case_difficulty_allocation import checked_file
from benchmarks.independent_mmlu_transfer import read_json
from benchmarks.prompteval_transfer import holdout
from cpo._contract import digest
from cpo.expected_qualification import certify_expected_qualification


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'docs/qualification-order-transfer-design-v1.json'
SNAPSHOT = ROOT / 'benchmarks/data/qualification-order-transfer-v1.json'
PARENT_REPORT = '01d306b01cebddfeb5373b4a79fe2c234808dc3d424af800fda25f63b0442ffb'
DOWNLOAD = ('https://www.dropbox.com/scl/fo/y9dd8zbteyf0xrjxdtm3e/h/raw%20open-source%20model%20responses'
            '%20with%20gold%20and%20auto%20validation%20values.zip?dl=1&rlkey=okp52gleuibw72fhe62egr6lp')
MODELS = ('airoboros-13b', 'nous-hermes-13b')
TASKS = {
    'BBH': ('disambiguation_qa', 'formal_fallacies', 'geometric_shapes', 'hyperbaton',
            'logical_deduction_five_objects', 'logical_deduction_seven_objects', 'logical_deduction_three_objects',
            'movie_recommendation', 'navigate', 'penguins_in_a_table', 'ruin_names',
            'salient_translation_error_detection', 'snarks', 'sports_understanding'),
    'LMentry': ('all_words_from_category', 'any_words_from_category', 'first_alphabetically', 'homophones',
                'less_letters', 'more_letters', 'rhyming_word', 'word_before', 'word_not_containing'),
}
PRIMARY = 'expected-order'
CONTROL = 'original-cpo'
LIMIT = 80_000_000


def fetch_range(start, end):
    length = end - start + 1
    raw = subprocess.check_output([
        '/usr/bin/curl', '--disable', '--silent', '--show-error', '--fail', '--location',
        '--proto', '=https', '--proto-redir', '=https', '--connect-timeout', '10', '--max-time', '50',
        '--max-filesize', str(length), '--range', f'{start}-{end}', f'{DOWNLOAD}&range_start={start}',
    ])
    if len(raw) != length:
        raise ValueError('The public archive did not return the exact byte range')
    return raw


def directory():
    raw = fetch_range(archive.DIRECTORY_OFFSET, archive.ZIP_SIZE - 1)
    if sha256(raw).hexdigest() != archive.DIRECTORY_SHA256:
        raise ValueError('The pinned ZIP directory changed')
    with ZipFile(BytesIO(raw)) as source:
        return raw, source.infolist()


def targets():
    return [(cross.identity(benchmark, task), benchmark, task, model)
            for benchmark, tasks in TASKS.items() for task in tasks for model in MODELS]


def freeze():
    paths = sorted(path for path in SNAPSHOT.parent.glob('*.json') if path != SNAPSHOT)
    seen = {pair for path in paths for pair in inventory.local_pairs(read_json(path.read_bytes()))}
    if not paths or any(model in MODELS for _, model in seen):
        raise ValueError('Both transfer model splits must be absent from the local correctness snapshots')
    _, entries = directory()
    offsets = sorted({entry.header_offset for entry in entries} | {0})
    successors = dict(zip(offsets, offsets[1:], strict=False))
    members = []
    for subject, benchmark, task, model in targets():
        item = cross.member_name(entries, benchmark, task, model)
        start = item.header_offset + archive.DIRECTORY_OFFSET
        end = successors[item.header_offset] + archive.DIRECTORY_OFFSET - 1
        if not 0 <= start <= end < archive.DIRECTORY_OFFSET or end - start + 1 > 4_000_000:
            raise ValueError('A selected archive member exceeds its sealed range')
        members.append({'subject': subject, 'benchmark': benchmark, 'task': task, 'model': model,
                        'path': item.filename, 'start': start, 'end': end,
                        'size': item.file_size, 'crc32': f'{item.CRC:08x}'})
    return design(members, {
        'jsonFiles': len(paths), 'namedPanelPairs': len(seen), 'priorSubjects': sorted({subject for subject, _ in seen}),
        'overlap': 0,
    })


def design(members, previous):
    old, cohorts, *_ = frontier.prepare()
    published = checked_file('docs/witness-validation-cost-frontier-results-v1.json', PARENT_REPORT)
    if digest(old) != published['designSha256']:
        raise ValueError('The development comparison differs from the published design')
    identities = [tuple(member[k] for k in ('subject', 'benchmark', 'task', 'model')) for member in members]
    if (identities != targets() or previous['overlap'] != 0
            or sum(member['end'] - member['start'] + 1 for member in members) > LIMIT):
        raise ValueError('The endpoint scope differs from the declared roster or byte allowance')
    _, settings, _ = cohorts['llama-mistral']
    paths = ('benchmarks/qualification_order_transfer.py', 'benchmarks/witness_validation_cost_frontier.py',
             'benchmarks/family_qualification_order.py', 'benchmarks/gepa_paid_cap_transfer.py',
             'benchmarks/tie_extension_cross_benchmark.py', 'benchmarks/cross_benchmark_prompt_race.py',
             'cpo/expected_qualification.py')
    return {
        **{k: settings[k] for k in ('schedule', 'searchCap', 'validationRows', 'gepaVersion')},
        'protocol': 'cpo-qualification-order-transfer-v1', 'developmentReportSha256': PARENT_REPORT,
        'developmentDesignSha256': digest(old), 'priorInventory': previous, 'members': members,
        'sourceRepository': archive.SOURCE, 'sourceDirectorySha256': archive.DIRECTORY_SHA256,
        'sourceZipBytes': archive.ZIP_SIZE, 'sourceLicense': 'CDLA-Permissive-2.0',
        'candidate': PRIMARY, 'gepaCaps': list(frontier.CAPS), 'gepaQualification': ['ordinary', 'expected-order'],
        'bootstrapDraws': 4096, 'bootstrapSeed': 20261130,
        'primaryGate': ('At the realized CPO lookup budget, require a nonnegative lower paired case bound and '
                        'a strictly positive observed pass difference against the best affordable fixed GEPA '
                        'mode, cap, qualification order or retaining the start. Keep both models paired.'),
        'subgroups': ['all', 'BBH', 'LMentry', 'unseen-tasks'],
        'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in paths},
    }


def capture(plan):
    directory_bytes, _ = directory()
    with TemporaryDirectory(prefix='cpo-qualification-member-ranges-') as scratch:
        path = Path(scratch) / 'members.zip'

        def read_member(member):
            return fetch_range(member['start'], member['end'])

        with path.open('wb') as stream, ThreadPoolExecutor(max_workers=4) as pool:
            stream.seek(archive.DIRECTORY_OFFSET)
            stream.write(directory_bytes)
            for member, data in zip(plan['members'], pool.map(read_member, plan['members']), strict=True):
                stream.seek(member['start'])
                stream.write(data)
        panels = []
        with ZipFile(path) as stored:
            for item in plan['members']:
                info = stored.getinfo(item['path'])
                if info.file_size != item['size'] or f'{info.CRC:08x}' != item['crc32']:
                    raise ValueError('The selected ZIP member differs from the sealed manifest')
                raw = stored.read(info)
                panels.append({**cross.reduce_member(raw, item['subject']),
                               **{k: item[k] for k in ('subject', 'benchmark', 'task', 'model')},
                               'sourceMember': item['path'], 'sourceCRC32': item['crc32'],
                               'sourceSha256': sha256(raw).hexdigest()})
    snapshot = {'designSha256BeforeCapture': digest(plan), 'sourceDirectorySha256': archive.DIRECTORY_SHA256,
                'license': plan['sourceLicense'], 'panels': panels}
    check_snapshot(plan, snapshot)
    return snapshot


def check_snapshot(plan, snapshot):
    if (snapshot['designSha256BeforeCapture'] != digest(plan)
            or snapshot['sourceDirectorySha256'] != plan['sourceDirectorySha256']
            or snapshot['license'] != plan['sourceLicense']
            or len(snapshot['panels']) != len(plan['members'])):
        raise ValueError('The reduced archive does not match the frozen design')
    layouts = {}
    for panel, member in zip(snapshot['panels'], plan['members'], strict=True):
        cases, templates, scores = (panel[k] for k in ('caseIDs', 'templateIDs', 'correctness'))
        if (any(panel[k] != member[k] for k in ('subject', 'benchmark', 'task', 'model'))
                or panel['sourceMember'] != member['path'] or panel['sourceCRC32'] != member['crc32']
                or len(panel['sourceSha256']) != 64
                or len(cases) < 98 or len(set(cases)) != len(cases)
                or len(templates) != 100 or len({tuple(item) for item in templates}) != 100
                or len(scores) != 100 or any(len(row) != len(cases) or set(row) - {'0', '1'} for row in scores)
                or layouts.setdefault(panel['subject'], (cases, templates)) != (cases, templates)):
            raise ValueError('Each model pair must share aligned cases and templates with complete binary outcomes')


def paired_gepa(matrix, held, seed, plan, *, batched):
    """Replay one search path and independently account for both exact proof orders."""
    nominate, archive_proof = gepa.archive.nominate, gepa.archive.qualify_archived
    optimize, fresh_proof = gepa.optimize_by_paid_reads, gepa.certify_paired_qualification
    paid, validation = [], {}

    def begin(*args):
        paid.append({})
        validation.clear()
        return nominate(*args)

    def qualify_archive(incumbent, challenger, cases, evaluate):
        def observe(prompt, case):
            outcome = evaluate(prompt, case)
            paid[-1][prompt, case] = outcome
            return outcome

        return archive_proof(incumbent, challenger, cases, observe)

    def search(incumbent, alternatives, train, cases, evaluate, spent, **kwargs):
        allowed = set(cases)

        def observe(prompt, case):
            reply = evaluate(prompt, case)
            if case in allowed:
                validation.setdefault(prompt, {})[case] = reply
            return reply

        return optimize(incumbent, alternatives, train, cases, observe, spent, **kwargs)

    def qualify(incumbent, challenger, rows, evaluate, **kwargs):
        original = fresh_proof(incumbent, challenger, rows, evaluate, **kwargs)
        counts = tuple((sum(values.values()), len(values)) for values in
                       (validation.get(incumbent, {}), validation.get(challenger, {})))

        def evaluate_ordered(prompt, row, repeat):
            if repeat != 0:
                raise ValueError('The archive supplies one reply per prompt and case')
            outcome = matrix[int(prompt)][int(row.id)] == '1'
            paid[-1][prompt, int(row.id)] = outcome
            return outcome

        alternate = certify_expected_qualification(incumbent, challenger, rows, evaluate_ordered,
                                                    validation_counts=counts, **kwargs)
        if (original.status, original.prompt) != (alternate.status, alternate.prompt):
            raise ValueError('Changing qualification order changed GEPA deployment')
        return original

    with (patch.object(gepa.archive, 'nominate', begin), patch.object(gepa.archive, 'qualify_archived', qualify_archive),
          patch.object(gepa, 'optimize_by_paid_reads', search), patch.object(gepa, 'certify_paired_qualification', qualify)):
        final, used, peak, trace = gepa.reinvest_episode(matrix, held, seed, plan['schedule'], plan, batched=batched)
    if peak > plan['searchCap'] or len(trace) != len(paid):
        raise ValueError('The replay exceeded its ceiling or lost an accounting cycle')
    alternative = [{**step, 'qualificationSha256': digest([(p, case, outcome) for (p, case), outcome in replies.items()])}
                   for step, replies in zip(trace, paid, strict=True)]
    return int(final), used, trace, sum(map(len, paid)), alternative


def point(total, trace, qualification):
    return {'holdoutPasses': total['holdoutPasses'], 'paidLookups': total['searchPaid'] + qualification,
            'traceSha256': digest(trace)}


def measure(panel, plan):
    subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
    held = holdout(subject, len(matrix[0]))
    schedule = plan['schedule']
    starts = route.ties.costs.retained_prompts(matrix, held, schedule)
    episodes = tuple(zip(schedule['seeds'], map(str, starts), strict=True))
    points, vectors = {}, {}

    def cases(finals):
        return tuple(frontier.uncertainty.case_totals(matrix, held, finals).values())

    cpo = {policy: (Counter(), [], []) for policy in (CONTROL, PRIMARY)}
    for seed, start in episodes:
        used, trace = family.run(matrix, held, seed, plan, start, 'strict', ordered=False)
        ordered, receipts = family.run(matrix, held, seed, plan, start, 'strict', ordered=True)
        if family.decisions(trace, 'strict') != family.decisions(receipts, 'strict') or any(
                used[key] != ordered[key] for key in ('searchPaid', 'searchLogical', 'holdoutPasses')):
            raise ValueError('The candidate changed the deployed or search path')
        for policy, counts, journal in ((CONTROL, used, trace), (PRIMARY, ordered, receipts)):
            total, history, finals = cpo[policy]
            total.update(counts)
            history.append(journal)
            finals.append(int(journal[-1]['decision']['selected']))
    for policy, (total, history, finals) in cpo.items():
        points[policy] = point(total, history, total['qualificationPaid'])
        vectors[policy] = cases(finals)

    for mode in frontier.MODES:
        for cap in plan['gepaCaps']:
            settings = {**plan, 'searchCap': cap}
            label = f'{mode}/{cap}'
            qualified_label = f'{label}/expected-order'
            total, history, alternate_history, finals, alternate_cost = Counter(), [], [], [], 0
            batched = mode.startswith('gepa-batched')
            for seed, _ in episodes:
                final, used, trace, other_cost, alternate = paired_gepa(matrix, held, seed, settings, batched=batched)
                total.update(used)
                finals.append(final)
                history.append(trace)
                alternate_history.append(alternate)
                alternate_cost += other_cost
            points[label] = point(total, history, total['qualificationPaid'])
            points[qualified_label] = point(total, alternate_history, alternate_cost)
            vectors[label] = vectors[qualified_label] = cases(finals)
            if cap == plan['searchCap']:
                # Check the shared-path accounting against independently
                # running the earlier adapter under both qualification orders.
                for ordered, name in ((False, label), (True, qualified_label)):
                    check_total, check_history = Counter(), []
                    for seed, start in episodes:
                        used, trace = family.run(matrix, held, seed, settings, start, label, ordered=ordered)
                        check_total.update(used)
                        check_history.append(trace)
                    if points[name] != point(check_total, check_history, check_total['qualificationPaid']):
                        raise ValueError(f'The two accounting paths disagree on {subject}/{model}/{name}')

    vectors[frontier.RETAIN] = cases(starts)
    points[frontier.RETAIN] = {'holdoutPasses': sum(vectors[frontier.RETAIN]), 'paidLookups': 0}
    if any(sum(vectors[label]) != result['holdoutPasses'] for label, result in points.items()):
        raise ValueError('Case counts do not reproduce the recorded deployment scores')
    return points, held, vectors


def replay(plan, snapshot, file_hash):
    check_snapshot(plan, snapshot)
    panels, holdouts, subjects = {}, {}, {}
    for panel in snapshot['panels']:
        subject, model = panel['subject'], panel['model']
        points, held, scores = measure(panel, plan)
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('The paired model panels must share all holdout rows')
        panels[f'{subject}/{model}'] = points
        accum = subjects.setdefault(subject, {label: [0] * len(held) for label in points})
        for label, values in scores.items():
            for index, value in enumerate(values):
                accum[label][index] += value

    ordinary = tuple(label for group in frontier.GEPA.values() for label in group)
    ordered = tuple(f'{label}/expected-order' for label in ordinary)
    groups = {'either-order': (*ordinary, *ordered), 'ordinary': ordinary, 'expected-order': ordered}
    unseen = set(subjects) - set(plan['priorInventory']['priorSubjects'])
    cohorts = {'all': set(subjects), 'unseen-tasks': unseen,
               **{bench: {s for s in subjects if s.startswith(f'{bench.lower()}-')} for bench in TASKS}}
    report = {}
    for name, enrolled in cohorts.items():
        totals = {label: Counter() for label in next(iter(panels.values()))}
        for panel in snapshot['panels']:
            subject, model = panel['subject'], panel['model']
            if subject in enrolled:
                for label, score in panels[f'{subject}/{model}'].items():
                    totals[label].update({k: score[k] for k in ('holdoutPasses', 'paidLookups')})
        sensitivity = frontier.compare(totals, {s: subjects[s] for s in sorted(enrolled)}, policies=(CONTROL, PRIMARY),
                                       draws=plan['bootstrapDraws'], seed=plan['bootstrapSeed'], groups=groups)
        result = sensitivity[PRIMARY]['either-order']
        low, high = result['pairedRange95']
        gate = 'passed' if result['holdoutPassDifference'] > 0 and low >= 0 else 'failed' if high < 0 else 'inconclusive'
        report[name] = {'subjects': sorted(enrolled), 'holdoutCases': sum(len(holdouts[s]) for s in enrolled),
                        'totals': totals, 'comparisons': sensitivity, 'gate': gate}
    return {'designSha256': digest(plan), 'snapshotSha256': file_hash, 'panels': panels,
            'cohorts': report, 'primaryGate': report['all']['gate']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', action='store_true')
    mode.add_argument('--capture', action='store_true')
    mode.add_argument('--replay', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.freeze == bool(args.execute):
        parser.error('Supply a fresh path and the published seal for capture or replay')
    if args.freeze:
        plan = freeze()
        result = {'design': plan, 'designSha256': digest(plan)}
    else:
        stored = read_json(DESIGN.read_bytes())
        plan = design(stored['design']['members'], stored['design']['priorInventory'])
        if digest(plan) != stored['designSha256'] or digest(stored['design']) != args.execute or digest(plan) != args.execute:
            parser.error('The supplied seal must match the frozen design and current sources')
        if args.capture:
            result = capture(plan)
        else:
            if version('gepa') != plan['gepaVersion']:
                parser.error('Use pinned GEPA 0.1.4')
            raw = args.replay.read_bytes()
            result = replay(plan, read_json(raw), sha256(raw).hexdigest())
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
