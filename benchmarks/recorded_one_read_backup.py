"""Buy at most one validation reply after a training veto and no paid backup."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_validation_race_order as race
from cpo._contract import digest


parent, prior, math = race.parent, race.prior, race.math
backup = parent.backup
REFERENCE = 'docs/recorded-validation-race-order-results-v1.json'
REFERENCE_SHA256 = '024dc1ce8f9130980e511e49a9f13e4e987741468e87dd23f3992b5706191013'
CANDIDATE = 'one-read-backup-after-training-veto'
ARMS = (CANDIDATE, *parent.ARMS)


def probe_options(incumbent, first, roster, rows, training, ledger, cap):
    """Rank unopened cells that could finish a strict validation certificate."""
    if first == incumbent:
        return []
    base = {row.id: ledger[incumbent, row.id].passed for row in rows}
    score = sum(base.values())
    critical = {row.id for row in rows if row.critical and base[row.id]}
    seen, passes = Counter(), Counter()
    for (name, case), reply in ledger.items():
        if case in base and name in roster:
            seen[case] += 1
            passes[case] += reply.passed
    options = []
    for index, prompt in enumerate(roster):
        if prompt == first:
            continue
        evidence = {row.id: ledger[prompt, row.id].passed for row in rows if (prompt, row.id) in ledger}
        confirmed = sum(evidence.values())
        if not evidence or confirmed < score or any(evidence.get(case) is False for case in critical):
            continue
        missing_critical = critical - evidence.keys()
        if len(missing_critical) > 1 or (not missing_critical and confirmed > score):
            continue
        # Reserve both complete training checks against the same search cap before allowing a probe.
        reserved = sum((name, row.id) not in ledger for row in training for name in (incumbent, first, prompt))
        if len(ledger) + reserved + 1 > cap:
            continue
        for offset, row in enumerate(rows):
            if row.id not in evidence and (not missing_critical or row.id in missing_critical):
                chance = Fraction(passes[row.id] + 1, seen[row.id] + 2)
                options.append((-confirmed, -chance, index, offset, prompt, row))
    return [(prompt, row) for *_, prompt, row in sorted(options)]


def run_candidate(cells, start, roster, cohorts, seed, cap):
    original_select, original_defer = backup.select_with_training, prior.can_defer
    stats = Counter()
    offered = []

    def defer(incumbent, first, candidates, validation, training, ledger, cap):
        return (original_defer(incumbent, first, candidates, validation, training, ledger, cap)
                and not probe_options(incumbent, first, candidates, validation, training, ledger, cap))

    def select(incumbent, first, candidates, validation, training, observe, ledger, *, cap, seed, mode, audit):
        existing = (backup.strongest_backup(incumbent, first, candidates, validation, ledger, partial=True)
                    if first != incumbent else None)
        options = (probe_options(incumbent, first, candidates, validation, training, ledger, cap)
                   if existing is None else [])
        passed = original_select(incumbent, first, candidates, validation, training, observe, ledger,
                                 cap=cap, seed=seed, mode=mode, audit=audit)
        if passed != incumbent or not options:
            return passed
        if stats['validationProbes']:
            raise ValueError('A training veto may buy at most one validation reply')
        stats['validationProbes'] += 1
        offered.extend((prompt, int(row.id)) for prompt, row in options)
        prompt, row = options[0]
        if not observe(prompt, row).passed:
            return incumbent
        if backup.strongest_backup(incumbent, first, (prompt,), validation, ledger, partial=True) != prompt:
            raise ValueError('The paid pass must prove a strict critical-safe validation gain')
        stats['newValidationCertificates'] += 1
        result = original_select(incumbent, prompt, (), validation, training, observe, ledger,
                                 cap=cap, seed=seed, mode=mode, audit=audit)
        stats['probeBackupsEnteringQualification'] += int(result == prompt)
        return result

    with (patch.object(prior, 'can_defer', defer), patch.object(backup, 'select_with_training', select)):
        point, trace, values = parent.run_trial(cells, start, roster, cohorts, seed, cap, prior.CANDIDATE, parent.EXPECTED)
    stats['probeBackupPromotions'] += int(bool(offered) and trace[3] != start)
    return {**point, **stats}, trace, values, offered


def hindsight_gain(cells, start, cohorts, options):
    """Score the best offered certificate in hindsight, without charging its alternate proof."""
    train, _, qualify, held = cohorts
    training = train[:len(train) // 2]
    better = {prompt for prompt, case in options if cells[prompt][case][0]
              and all(sum(cells[prompt][c][0] - cells[start][c][0] for c in panel) > 0
                      for panel in (training, qualify))}
    return max((sum(cells[name][c][0] - cells[start][c][0] for c in held) for name in better), default=0)


def prepare():
    previous, data, _ = race.prepare()
    raw = (backup.ROOT / REFERENCE).read_bytes()
    old = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or old['planSha256'] != digest(previous):
        raise ValueError('Use the exact published seeded race and its matched GEPA alternatives')
    plan = {**{key: previous[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                             'gepaVersion', 'bootstrapSeed', 'bootstrapDraws',
                                             'minimumLookupSavingPercent')},
            'protocol': 'recorded-one-read-backup-v1', 'parentPlanSha256': digest(previous),
            'parentReportSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'arms': ARMS,
            'scope': 'Keep the seeded exact race and every paid backup. After a training veto, buy at most one '
                     'missing reply when a pass would certify a funded backup. Rank by paid passes, case pass rate, '
                     'then roster and case order. The backup still needs the original strict training and independent '
                     'qualification gains. Score the best offered backup in hindsight as an optimistic diagnostic.'}
    return plan, data, old['results']


def measure(cells, settings, group, width, plan, reference):
    size = len(next(iter(cells.values())))
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    totals, traces = {arm: Counter() for arm in ARMS}, {arm: [] for arm in ARMS}
    vectors, changes = {arm: [0] * size for arm in ARMS}, Counter()
    for seed in settings['seeds']:
        cohorts = math.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            available = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(available, len(available))[:width]
            args = (cells, start, roster, cohorts, seed, plan['searchCap'])
            point, trace, grades, offered = run_candidate(*args)
            outcomes = {arm: parent.run_trial(*args, arm, parent.EXPECTED) for arm in parent.ARMS}
            base, baseline, _ = outcomes[prior.CANDIDATE]
            if (not offered and trace[3] != baseline[3]) or (offered and baseline[3] != start):
                raise ValueError('A rescue may change deployment only after the seeded policy keeps the start')
            delta = point['holdoutPasses'] - base['holdoutPasses']
            changes.update(changedDeployments=int(trace[3] != baseline[3]), grossGain=max(delta, 0),
                           grossLoss=max(-delta, 0), additionalLookups=point['paidLookups'] - base['paidLookups'],
                           hindsightOfferedGain=max(0, hindsight_gain(cells, start, cohorts, offered)))
            for arm, (count, log, values) in {**outcomes, CANDIDATE: (point, trace, grades)}.items():
                totals[arm].update(count)
                traces[arm].append(log)
                for case, value in zip(cohorts[-1], values, strict=True):
                    vectors[arm][case] += value
    points = {arm: {**count, 'traceSha256': digest(traces[arm])} for arm, count in totals.items()}
    if any(points[arm] != reference['totals'][arm] for arm in parent.ARMS):
        raise ValueError('The sealed seeded control traces must reproduce')
    scores = {**vectors, **{name: vectors[arm] for name, arm in prior.CONTROLS.items()}}
    costs = {**totals, **{name: totals[arm] for name, arm in prior.CONTROLS.items()}}
    ranges = math.paired_ranges(scores, CANDIDATE, (*math.GEPA, prior.CANDIDATE), plan)
    return {'totals': points, 'trials': len(traces[CANDIDATE]), 'changes': changes,
            'comparison': math.comparison(CANDIDATE, costs, ranges, plan)}


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
