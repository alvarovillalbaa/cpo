"""Transfer frozen CPO selectors to additional archived model and task pairs."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import paired_repair_race as race
from benchmarks import recorded_first_certificate_transfer as layouts
from benchmarks import shared_validation_split_safe_transfer as native
from benchmarks.validation_repair_anchor import attaining_trial, repair_screen, verify_witness
from cpo._contract import digest
from cpo.certified_shared_validation_cycle import run_certified_shared_validation_cycle
from cpo.two_sided_certificate_cycle import _run


ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = 'docs/paired-repair-race-results-v1.json'
DISCOVERY_SHA = '3f4cfc4f2bc4ff98adabafbbb87ee67f7d7ddb2c0b94c5424b9c6008a599e4ed'
ARCHIVES = {
    'bounded-discovery-transfer/outcomes.jsonl': '8bd4101384fcf6543b466dcaf60a326df215f2c1f0ed3aa50185191c249a935f',
    'four-case-qualification-transfer-v1.json': '39c89ec670a976edc917a10345278d4b7354f358d29a9bd1c8238af2e6ad42ad',
    'tie-extension-cross-benchmark-v1.json': '8a820a2254fac09d1550af8ddcfc35775938f10f2fa2e1f0c7c72c58dc256103',
}
COHORTS = ('bounded-MMLU', 'four-case-MMLU', 'bounded-BBH', 'bounded-LMentry', 'tie-BBH', 'tie-LMentry')
SIZES = dict(zip(COHORTS, (8, 12, 12, 12, 8, 4), strict=True))
RUNNERS = {
    'certified-wide': run_certified_shared_validation_cycle,
    'incumbent-first': partial(_run, screen=race.previous.incumbent_first_screen),
    'single-repair': partial(_run, screen=partial(repair_screen, repairs=1)),
    'preserve-one': partial(_run, screen=partial(race.paired_repair_screen, miss_limit=1)),
}
RETAIN = native.gepa.RETAIN


def read_locked(name, expected):
    raw = (ROOT / name).read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError(f'Archive digest differs for {name}')
    return raw


def identity(subject, model):
    return subject, model.casefold().replace('-', '_').removeprefix('google_')


def enroll(discovery):
    previous = {identity(*name.split('/')) for cohort in discovery['results'].values() for name in cohort['traceHashes']}
    seen, axis = set(), {}
    groups = {name: [] for name in COHORTS}
    for archive, sha in ARCHIVES.items():
        raw = read_locked(f'benchmarks/data/{archive}', sha)
        if archive.endswith('.jsonl'):
            _, *rows = map(json.loads, raw.splitlines())
            prefix = 'bounded'
        else:
            rows = json.loads(raw)['panels']
            prefix = 'four-case' if archive.startswith('four-case') else 'tie'
        for row in rows:
            subject, model, matrix = (row[key] for key in ('subject', 'model', 'correctness'))
            panel = identity(subject, model)
            if panel in seen or panel in previous:
                raise ValueError(f'Transfer panel overlaps a scored panel {panel}')
            seen.add(panel)
            family = row.get('benchmark') or {'bbh': 'BBH', 'lmentry': 'LMentry'}.get(subject.split('-')[0], 'MMLU')
            cohort = f'{prefix}-{family}'
            width = len(matrix[0])
            cases = row.get('caseIDs') or row.get('caseOrderSha256') or row.get('sourceProvenance', {}).get('caseIDsSha256')
            templates = row.get('templateIDs') or row.get('sourceProvenance', {}).get('templateIDsSha256')
            signature = (width, cases, templates)
            if (len(matrix) != 100 or any(len(scores) != width or set(scores) - {'0', '1'} for scores in matrix)
                    or axis.setdefault((cohort, subject), signature) != signature):
                raise ValueError('Panels need complete binary scores and consistent ordered axes')
            groups[cohort].append((subject, model, matrix))
    for name, panels in groups.items():
        if len(panels) != SIZES[name] or set(Counter(subject for subject, *_ in panels).values()) != {2}:
            raise ValueError('Every frozen phase needs both checkpoints for every task')
    return groups


def prepare():
    discovery = json.loads(read_locked(DISCOVERY, DISCOVERY_SHA))
    parent = discovery['plan']
    if digest(parent) != discovery['planSha256']:
        raise ValueError('The paired race plan and seal must agree')
    groups = enroll(discovery)
    sources = (Path(__file__), Path(race.__file__), Path(race.previous.__file__), Path(layouts.__file__),
               Path(native.__file__), Path(native.gepa.__file__), Path(native.native.__file__),
               ROOT / 'cpo/certified_shared_validation_cycle.py', ROOT / 'benchmarks/validation_repair_anchor.py')
    plan = {**{key: parent[key] for key in ('caseCounts', 'challengers', 'seeds', 'fullRosterCap', 'minimumGains',
                                          'bootstrapSeed', 'bootstrapDraws', 'gepaVersion', 'searchCap', 'pinnedWheel')},
            'protocol': 'shared-validation-archive-transfer-v1', 'discoveryReceiptSha256': DISCOVERY_SHA,
            'discoveryPlanSha256': discovery['planSha256'], 'archiveSha256': ARCHIVES,
            'sourceSha256': {str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest() for path in sources},
            'cohorts': {name: [(subject, model) for subject, model, _ in panels] for name, panels in groups.items()},
            'cpoPolicies': tuple(RUNNERS), 'gepaWidths': native.WIDTHS, 'gepaModes': native.native.native_cost.MODES,
            'primaryByCohort': {name: 'preserve-one' if name.endswith('MMLU') else 'certified-wide' for name in groups},
            'gate': 'At one independent gain the frozen primary must beat the best affordable common GEPA setting '
                    'or retain-start at a positive paired lower endpoint and exceed the subject-tuned GEPA point. '
                    'The common GEPA setting and the subject schedule are fixed during case resampling.',
            'scope': 'Enroll archived task-checkpoint pairs absent from the preceding shared-panel comparison. '
                     'Freeze the original one-cycle case sampler, 30 percent holdout, candidate roster, settings '
                     'and margins. Sweep both official GEPA modes, both validation widths, all six proof rules '
                     'and every funded integer search cap. Exact scores and costs are selected at realized budgets.'}
    return plan, groups


def case_cells(matrix):
    grades = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
    return grades, {prompt: tuple((grade, None, False) for grade in row) for prompt, row in grades.items()}


def sweep_trial(arguments, high, changes):
    for mode in native.native.native_cost.MODES:
        for group, width in native.WIDTHS.items():
            paths = native.gepa.native_paths(native.validation_width(arguments, width), mode, width, high)
            for rule, points in paths.items():
                native.native.record_boundaries(changes.setdefault((group, mode, rule), {}), points, high)


def tally_native(subject, changes, high):
    for (group, mode, rule), deltas in changes.items():
        point = Counter()
        for cap in range(native.WIDTHS[group], high + 1):
            point.update(deltas.get(cap, {}))
            subject.setdefault(f'{group}:{mode}/{cap}/{rule}', Counter()).update(point)


def compare_attainers(panels, plan, vectors, schedules, expected, primary):
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    measured = {name: {} for name in schedules}
    for subject, _, matrix in panels:
        _, packed = case_cells(matrix)
        rows = vectors[subject]
        for seed in plan['seeds']:
            start, roster, roles = layouts.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
            for name, setting in schedules.items():
                _, grades, cost = attaining_trial(setting[subject], (packed, start, roster, roles, seed))
                measured[name].setdefault(subject, Counter()).update(holdoutPasses=sum(grades), paidLookups=cost)
                add(rows.setdefault(name, [0] * len(grades)), grades)
    if measured != expected:
        raise ValueError('Every native attainer must reconcile to the measured subject costs and scores')
    paired = native.frozen.paired_effects.paired_effect
    return {name: paired(vectors, primary, name, plan) for name in schedules}


def measure(panels, plan):
    labels = {gain: f'gain-{gain}' for gain in plan['minimumGains']}
    totals = {label: {policy: Counter() for policy in RUNNERS} for label in labels.values()}
    native_totals, vectors, fingerprints = {}, {}, {}
    run = native.paired.cycle.execute_path
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    high = plan['searchCap']
    with native.split_safe_cache():
        for subject, model, matrix in panels:
            cells, packed = case_cells(matrix)
            subject_points = native_totals.setdefault(subject, {})
            traces = {label: {policy: [] for policy in RUNNERS} for label in labels.values()}
            changes = {}
            for seed in plan['seeds']:
                start, roster, roles = layouts.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
                subject_points.setdefault(RETAIN, Counter()).update(holdoutPasses=sum(cells[start][case] for case in roles[-1]), paidLookups=0)
                for gain, label in labels.items():
                    for policy, runner in RUNNERS.items():
                        result, paid = run(runner, cells, start, roster, roles, seed, plan['fullRosterCap'], gain)
                        point, grades, fingerprint = native.paired.reference.point(cells, roles[-1], result, paid)
                        traces[label][policy].append(fingerprint)
                        totals[label][policy].update(**point, nominees=int(result.search.finalist is not None),
                                                     promotions=int(result.promoted))
                        if policy != 'certified-wide':
                            verify_witness(cells, start, roles, result, paid, gain)
                        if gain == 1:
                            scores = vectors.setdefault(subject, {})
                            add(scores.setdefault(policy, [0] * len(grades)), grades)
                sweep_trial((packed, start, roster, roles, seed), high, changes)
            tally_native(subject_points, changes, high)
            fingerprints[f'{subject}/{model}'] = {label: {policy: digest(trace) for policy, trace in methods.items()}
                                                   for label, methods in traces.items()}

    settings = tuple(label for label in next(iter(native_totals.values())) if label != RETAIN)
    native_common = {label: Counter() for label in (*settings, RETAIN)}
    for points in native_totals.values():
        for label, point in points.items():
            native_common[label].update(point)
    budgets = {f'{margin}/{policy}': point['paidLookups'] for margin, methods in totals.items()
               for policy, point in methods.items()}
    ceiling = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling(native_totals, settings, budgets)
    common_schedules, subject_schedules = {}, {}
    for margin, methods in totals.items():
        for policy, point in methods.items():
            key = f'{margin}/{policy}'
            common_schedules[key] = native.gepa.best_fixed(native_common, settings, budgets[key])
            subject_schedules[key] = ceiling[key]
    primary = plan['primaryByCohort'][plan['cohort']]
    target = f'gain-1/{primary}'
    best_common = common_schedules[target]['setting']
    schedules = {'common-gepa': dict.fromkeys(native_totals, best_common),
                 'subject-tuned-gepa': ceiling[target]['settingsBySubject']}
    expected = {arm: {subject: native_totals[subject][setting] for subject, setting in schedule.items()}
                for arm, schedule in schedules.items()}
    paired = compare_attainers(panels, plan, vectors, schedules, expected, primary)
    passed = (paired['common-gepa']['pairedRange95'][0] > 0 and paired['subject-tuned-gepa']['holdoutPassDifference'] > 0)
    return {'cpo': totals, 'bestCommonGepa': common_schedules, 'subjectTunedGepa': subject_schedules,
            'primaryPairedAgainstGepa': paired, 'primaryGatePassed': passed, 'gepaSettings': len(settings),
            'nativeSubjectTotalsSha256': digest(native_totals), 'panelPathHashes': fingerprints}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    parent, panels = prepare()
    plan = {**parent, 'cohort': args.cohort}
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path and the pinned GEPA version')
    results = measure(panels[args.cohort], plan)
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
