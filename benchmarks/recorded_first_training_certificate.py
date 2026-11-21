"""Spend less validation before choosing a training-corroborated challenger."""

import argparse
from collections import Counter
from contextlib import ExitStack
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_paid_qualification_order as parent, recorded_training_veto_backup_ceiling as ceiling
from cpo import Row
from cpo._contract import digest


math, prior, backup = parent.math, parent.prior, parent.backup
REFERENCE = 'docs/recorded-paid-qualification-order-results-v1.json'
REFERENCE_SHA256 = 'a7e0d401c77b4951bc381922b2ae48218f459a856d4d095d7c369fbcac76d677'
CEILING = 'docs/recorded-training-veto-backup-ceiling-results-v1.json'
CEILING_SHA256 = '4adbbde4f5e6d258c76ff9c689fad6917fde4315acd7afa370c0eb58cd31f9b8'
FIRST = 'first-certificate'
TRAIN_FIRST = 'first-certificate-with-training-first'
SECOND = 'second-certificate-after-training-veto'
POLICIES = (FIRST, TRAIN_FIRST, SECOND)
ARMS = (*parent.ARMS, *POLICIES)


def certificates(incumbent, roster, rows, training, observe, ledger, cap):
    """Yield the next strict validation gain in roster order, with training funded."""
    if not rows or not training or not roster or len(rows) > cap:
        return
    hits, reads = Counter(), Counter()

    def read(prompt, row):
        value = observe(prompt, row).passed
        if type(value) is not bool:
            raise ValueError('Search requires exact boolean grades')
        hits[row.id] += value
        reads[row.id] += 1
        return value

    base = {row.id: read(incumbent, row) for row in rows}
    target = sum(base.values()) + 1
    if target > len(rows):
        return
    protected = {row.id for row in rows if row.critical and base[row.id]}
    for prompt in roster:
        training_reserve = sum((name, row.id) not in ledger for name in (incumbent, prompt) for row in training)
        if len(ledger) + len(rows) + training_reserve > cap:
            continue
        order = sorted(rows, key=lambda row: (row.id not in protected, Fraction(hits[row.id] + 1, reads[row.id] + 2)))
        passed = 0
        for offset, row in enumerate(order, 1):
            correct = read(prompt, row)
            passed += correct
            if (row.id in protected and not correct) or passed + len(rows) - offset < target:
                break
            if offset >= len(protected) and passed >= target:
                yield prompt, offset
                break


def trial(cells, start, roster, cohorts, seed, cap, arm):
    if arm in parent.ARMS:
        return parent.run_trial(cells, start, roster, cohorts, seed, cap, arm, parent.EXPECTED)
    original_training = backup.select_with_training
    training = tuple(Row(str(case), 'training') for case in cohorts[0][:len(cohorts[0]) // 2])
    audit, counted = Counter(), Counter()

    def choose(incumbent, candidates, rows, observe, ledger, *, method, cap):
        limit = 2 if arm == SECOND else 1
        ordered = certificates(incumbent, candidates, rows, training, observe, ledger, cap)
        for attempt in range(1, limit + 1):
            result = next(ordered, None)
            if result is None:
                break
            prompt, read = result
            counted.update(validationCertificates=1, partialCertificates=int(read < len(rows)))
            if arm == FIRST:
                return prompt, False
            supported = original_training(incumbent, prompt, (), rows, training, observe, ledger, cap=cap,
                                          seed=seed, mode=backup.PRECHECKED[backup.PRECHECK], audit=audit)
            if supported != incumbent:
                counted['secondCertificateNomination'] += int(attempt == 2)
                return supported, False
        return incumbent, False

    with ExitStack() as patches:
        patches.enter_context(patch.object(math, 'select', choose))
        if arm != FIRST:
            # These two schedules have already done the training check inside the paid race.
            patches.enter_context(patch.object(backup, 'select_with_training', lambda _inc, first, *_, **_kw: first))
            patches.enter_context(patch.object(prior, 'can_defer', lambda *_: False))
        point, trace, grades = parent.run_trial(cells, start, roster, cohorts, seed, cap,
                                              prior.CANDIDATE, parent.EXPECTED)
    counted['secondCertificatePromotion'] += int(counted['secondCertificateNomination'] > 0 and trace[3] != start)
    return {**point, **audit, **counted}, trace, grades


def prepare():
    preceding, data, _ = parent.prepare()
    raw = (backup.ROOT / REFERENCE).read_bytes()
    audit = (backup.ROOT / CEILING).read_bytes()
    old = json.loads(raw)
    previous, _, _ = ceiling.prepare()
    if (sha256(raw).hexdigest() != REFERENCE_SHA256 or old['planSha256'] != digest(preceding)
            or sha256(audit).hexdigest() != CEILING_SHA256 or json.loads(audit)['planSha256'] != digest(previous)):
        raise ValueError('Use the published matched controls and backup ceiling')
    plan = {**{key: preceding[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                              'gepaVersion', 'bootstrapSeed', 'bootstrapDraws',
                                              'minimumLookupSavingPercent')},
            'protocol': 'recorded-first-training-certificate-v1', 'parentPlanSha256': digest(preceding),
            'parentReceiptSha256': REFERENCE_SHA256, 'backupCeilingReceiptSha256': CEILING_SHA256,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'arms': ARMS,
            'scope': 'Pay for the incumbent validation panel. Race the seeded roster until an observed strict '
                     'validation gain preserves every protected pass. Compare one certificate with the existing '
                     'proof order, training first with one certificate, and training first with one additional '
                     'certificate after a training veto. Keep the original strict training and independent '
                     'qualification gains and lookups under the same search cap.'}
    return plan, data, old['results']


def measure(cells, settings, group, width, plan, reference):
    size = len(next(iter(cells.values())))
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    totals, journals = {arm: Counter() for arm in ARMS}, {arm: [] for arm in ARMS}
    vectors, changes = {arm: [0] * size for arm in ARMS}, {arm: Counter() for arm in POLICIES}
    for seed in settings['seeds']:
        cohorts = math.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            eligible = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(eligible, len(eligible))[:width]
            outcomes = {arm: trial(cells, start, roster, cohorts, seed, plan['searchCap'], arm) for arm in ARMS}
            baseline, log, _ = outcomes[prior.CANDIDATE]
            if outcomes[FIRST][1][3] != outcomes[TRAIN_FIRST][1][3]:
                raise ValueError('Changing proof order for the same certificate must preserve deployment')
            for arm, (point, trace, grades) in outcomes.items():
                totals[arm].update(point)
                journals[arm].append(trace)
                for case, grade in zip(cohorts[-1], grades, strict=True):
                    vectors[arm][case] += grade
                if arm in POLICIES:
                    delta = point['holdoutPasses'] - baseline['holdoutPasses']
                    changes[arm].update(changedDeployments=int(trace[3] != log[3]),
                                        grossGain=max(0, delta), grossLoss=max(0, -delta))
    points = {arm: {**point, 'traceSha256': digest(journals[arm])} for arm, point in totals.items()}
    if any(points[arm] != reference['totals'][parent.EXPECTED][arm] for arm in parent.ARMS):
        raise ValueError('The seeded CPO and native GEPA reference traces did not reproduce')
    matched = {**totals, **{name: totals[arm] for name, arm in prior.CONTROLS.items()}}
    scores = {**vectors, **{name: vectors[arm] for name, arm in prior.CONTROLS.items()}}
    comparator = (*math.GEPA, prior.CANDIDATE)
    return {'totals': points, 'trialCount': len(journals[FIRST]), 'deploymentChanges': changes,
            'comparisons': {arm: math.comparison(arm, matched, math.paired_ranges(scores, arm, comparator, plan), plan)
                            for arm in POLICIES}}


def replay(plan, data, reference):
    results = {}
    for name, settings in plan['datasets'].items():
        cells = math.load_cells(name, data[name]['record'])
        results[name] = {f'{group}/{width}': measure(cells, settings, group, width, plan,
                                                     reference[name][f'{group}/{width}'])
                         for group in plan['incumbentGroups'] for width in plan['challengerCounts']}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, data, reference)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
