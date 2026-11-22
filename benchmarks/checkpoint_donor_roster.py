"""Supply MMLU challengers from a different checkpoint's archived training replies."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import deferred_two_sided_certificate as previous
from benchmarks import independent_mmlu_transfer as dataset
from benchmarks import qualification_precheck_extension as native
from benchmarks import recorded_one_failure_screen_transfer as earlier_archive
from cpo._contract import digest


paired, gepa = previous.paired, native.gepa
COHORT = 'disjoint-transfer-cohort'
SEEDED, DONOR, MIXED = 'seeded', 'donor-ranked', 'half-seeded'
ROSTERS = SEEDED, DONOR, MIXED
REPORT = 'docs/deferred-two-sided-certificate-results-v1.json'
REPORT_SHA256 = 'b50173bfd6964cceb58ae34f8492fc1df00a70f7c25b1bee6ef46530a26de0c4'
ARCHIVES = earlier_archive.ARCHIVES


def align_donors(panels, entries):
    records = {}
    for entry in entries:
        subject, model = entry['subject'], entry['model']
        if (subject, model) in records:
            raise ValueError('Each source checkpoint must be unique within its subject')
        records[subject, model] = entry
    pairs = {}
    for subject, model, matrix in panels:
        record = records[subject, model]
        if record['correctness'] != matrix:
            raise ValueError('The target outcomes must match their original pinned source')
        pairs.setdefault(subject, []).append(record)
    donors = {}
    for subject, pair in pairs.items():
        if len(pair) != 2:
            raise ValueError('A donor must be a second checkpoint on the same ordered cases and templates')
        left, right = pair
        if (left['model'] == right['model'] or not left.get('caseOrderSha256')
                or left['caseOrderSha256'] != right.get('caseOrderSha256')):
            raise ValueError('A donor must be a second checkpoint on the same ordered cases and templates')
        outcomes = left['correctness'], right['correctness']
        if any(len(matrix) != 100 for matrix in outcomes):
            raise ValueError('Both checkpoints require a complete 100-template matrix')
        width = len(outcomes[0][0])
        if not width or any(len(row) != width or set(row) - {'0', '1'} for matrix in outcomes for row in matrix):
            raise ValueError('Both checkpoint matrices must contain exact binary grades on aligned cases')
        for target, donor in ((left, right), (right, left)):
            donors[subject, target['model']] = donor
    return donors


def prepare():
    parent, groups, controls, _, receipts = previous.prepare()
    read = paired.frontier.cost.prior.baseline.read_reference
    earlier = read(REPORT, REPORT_SHA256, parent)['results'][COHORT]
    panels = groups[COHORT]
    enrolled = {(subject, model) for subject, model, _ in panels}
    entries = []
    for name, expected in ARCHIVES.items():
        raw = (paired.reference.ROOT / 'benchmarks/data' / name).read_bytes()
        document = json.loads(raw)
        if (sha256(raw).hexdigest() != expected or document['observedRepoRevision'] != dataset.REVISION
                or document['sourceDataset'] != dataset.DATASET):
            raise ValueError('Use the exact recorded donor matrices from the pinned dataset revision')
        entries.extend(row for row in document['panels'] if (row['subject'], row['model']) in enrolled)
    donors = align_donors(panels, entries)
    sources = (Path(__file__), Path(gepa.__file__), Path(native.__file__))
    plan = {**parent, 'protocol': 'checkpoint-donor-roster-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': REPORT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in sources},
            'cohort': COHORT, 'donorArchiveSha256': ARCHIVES,
            'rosterMethods': ROSTERS,
            'scope': 'Retain the incumbent and existing case splits. Rank the donor checkpoint templates '
                     'using only the target episode training case IDs. Replace the eight challenger slots '
                     'with top donor templates or alternate four top donor offers and the first four seeded candidates. '
                     'Use the same rosters for two-sided CPO and both native GEPA modes. Separately count all '
                     'donor accesses and distinct archived grades; target budgets assume the source archive already exists.'}
    return plan, panels, controls, earlier, receipts[COHORT], donors


def donor_rosters(start, seeded, templates, training, read, subject, seed):
    templates = [name for name in templates if name != start]
    Random(f'{seed}/{subject}/checkpoint-donor-order').shuffle(templates)
    scored = sorted(templates, key=lambda prompt: -sum(read(prompt, case) for case in training))
    retained = seeded[:len(seeded) // 2]
    offers = [name for name in scored if name not in seeded][:len(seeded) - len(retained)]
    if len(offers) != len(retained):
        raise ValueError('The hybrid roster requires enough novel templates and an even width')
    hybrid = tuple(name for pair in zip(offers, retained, strict=True) for name in pair)
    return {SEEDED: tuple(seeded), DONOR: tuple(scored[:len(seeded)]), MIXED: hybrid}


def ceiling(cells, start, roster, roles, gain):
    _, validation, qualification, holdout = roles
    v = sum(cells[start][case] for case in validation)
    q = sum(cells[start][case] for case in qualification)
    possible = (name for name in roster if sum(cells[name][case] for case in validation) > v
                and sum(cells[name][case] for case in qualification) >= q + gain)
    return max(sum(cells[name][case] for case in holdout) for name in (start, *possible))


def measure(panels, plan, controls, earlier, native_reference, donors):
    stats = {label: {arm: Counter() for arm in ROSTERS} for label in controls.values()}
    subjects, traces, donor_inventory, roster_hashes = {}, {}, {}, {}
    low, high, cap = plan['minimumSearchCap'], plan['searchCap'], plan['fullRosterCap']
    for subject, model, matrix in panels:
        cells = {str(i): tuple(map(int, row)) for i, row in enumerate(matrix)}
        native_cells = {name: tuple((grade, None, False) for grade in row) for name, row in cells.items()}
        donor = donors[subject, model]
        source = {str(i): row for i, row in enumerate(donor['correctness'])}
        name = f'{subject}/{model}'
        by_subject = subjects.setdefault(subject, {})
        orders, donor_pairs = [], set()
        logs = {label: {arm: [] for arm in ROSTERS} for label in controls.values()}
        deltas = {}
        reads = 0
        for seed in plan['seeds']:
            start, seeded, roles = paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            training = frozenset(roles[0])
            touched = set()

            def donor_grade(prompt, case):
                if case not in training or prompt == start or (prompt, case) in touched:
                    raise ValueError('Donor lookup left its distinct training-only case bound')
                touched.add((prompt, case))
                return int(source[prompt][case])

            rosters = donor_rosters(start, seeded, tuple(source), roles[0], donor_grade, subject, seed)
            if len(touched) != (len(source) - 1) * len(training):
                raise ValueError('Report every source grade used for ranking')
            reads += len(touched)
            donor_pairs.update(touched)
            orders.append(rosters)
            by_subject.setdefault(gepa.RETAIN, Counter()).update(
                holdoutPasses=sum(cells[start][case] for case in roles[-1]), paidLookups=0,
            )
            for arm, roster in rosters.items():
                if len(set(roster)) != len(seeded) or start in roster:
                    raise ValueError('Every recipient roster must preserve the original slot count')
                for gain, label in controls.items():
                    result, paid = previous.run_trial(previous.EXPECTED, (cells, start, roster, roles, seed, cap, gain))
                    previous.previous.check_deployment(cells, start, roles, result, gain)
                    point, _, path = paired.reference.point(cells, roles[-1], result, paid)
                    oracle = ceiling(cells, start, roster, roles, gain)
                    if point['holdoutPasses'] > oracle:
                        raise ValueError('The observed deployment must fit its gated roster ceiling')
                    stats[label][arm].update(
                        **point, oracleHoldoutPasses=oracle, nominations=int(result.search.finalist is not None),
                        promotions=int(result.promoted), seededOverlap=len(set(roster) & set(seeded)),
                    )
                    logs[label][arm].append(path)
                arguments = native_cells, start, roster, roles, seed
                for mode in native.native_cost.MODES:
                    for rule, paths in gepa.native_paths(arguments, mode, low, high).items():
                        native.record_boundaries(deltas.setdefault((arm, mode, rule), {}), paths, high)
        traces[name] = {label: {arm: digest(path) for arm, path in choices.items()} for label, choices in logs.items()}
        if any(arms[SEEDED] != earlier['panelPathHashes'][name][label][previous.EXPECTED]
               for label, arms in traces[name].items()):
            raise ValueError('Every original seeded CPO callback trace must reproduce')
        donor_inventory[name] = {'model': donor['model'], 'logicalArchiveReads': reads, 'distinctArchiveGrades': len(donor_pairs)}
        roster_hashes[name] = digest(orders)
        for (arm, mode, rule), changes in deltas.items():
            state = Counter()
            for amount in range(low, high + 1):
                state.update(changes.get(amount, {}))
                by_subject.setdefault(f'{arm}:{mode}/{amount}/{rule}', Counter()).update(state)
    settings = {arm: tuple(label for label in next(iter(subjects.values())) if label.startswith(f'{arm}:'))
                for arm in ROSTERS}
    settings_all = tuple(label for labels in settings.values() for label in labels)
    subject_ceiling = gepa.frontier.transfer.fitted.prior.by_subject_ceiling
    anchored = {label: row['cpo']['paidLookups'] for label, row in native_reference['comparisons'].items()}
    anchors = subject_ceiling(subjects, settings[SEEDED], anchored)
    for label, result in anchors.items():
        expected = native_reference['comparisons'][label]['expandedSubjectCeiling']
        actual_settings = {subject: name.removeprefix(f'{SEEDED}:')
                           for subject, name in result['settingsBySubject'].items()}
        if {**result, 'settingsBySubject': actual_settings} != expected:
            raise ValueError('Seeded native settings must reproduce the published costs and subject ceilings')
    budgets = {f'{label}/{arm}': row['paidLookups'] for label, arms in stats.items() for arm, row in arms.items()}
    union = subject_ceiling(subjects, settings_all, budgets)
    comparisons = {}
    for label, arms in stats.items():
        baseline = earlier['totals'][label][previous.EXPECTED]
        if any(arms[SEEDED][key] != value for key, value in baseline.items()
               if key in native.native_cost.METRICS):
            raise ValueError('The original CPO target cost and holdout score must reproduce')
        comparisons[label] = {}
        for arm, row in arms.items():
            budget = row['paidLookups']
            key = f'{label}/{arm}'
            matched = subject_ceiling(subjects, settings[arm], {key: budget})[key]
            strongest = union[key]
            attaining = {subject: rows[strongest['settingsBySubject'][subject]] for subject, rows in subjects.items()}
            if any(sum(point[metric] for point in attaining.values()) != strongest[metric]
                   for metric in native.native_cost.METRICS):
                raise ValueError('The combined GEPA menu must attain its exact subject-tuned ceiling')
            comparisons[label][arm] = {'cpo': row, 'sameRosterGepa': matched, 'allRostersGepa': strongest,
                                       'attainingSubjectPoints': attaining}
    return {'comparisons': comparisons, 'nativeSettings': {arm: len(values) for arm, values in settings.items()},
            'panelPathHashes': traces, 'rosterHashes': roster_hashes, 'donorUsageByTargetPanel': donor_inventory,
            'nativeSubjectTotalsSha256': digest(subjects)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels, controls, earlier, reference, donors = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    result = measure(panels, plan, controls, earlier, reference, donors)
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': result},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
