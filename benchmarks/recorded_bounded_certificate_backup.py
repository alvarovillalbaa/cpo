"""Open one bounded backup after the first archived certificate fails training."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_math_roster_ceiling as prior
from cpo._contract import digest


core, math, transfer = prior.core, prior.math, prior.transfer
REFERENCE = 'docs/recorded-math-roster-ceiling-results-v1.json'
REFERENCE_SHA256 = '3ef29da2119943a89126c1089b983dfe9702267f8ec7e0a16256803be201f783'
LIMITS = {'four-read-backup': 4, 'eight-read-backup': 8}


def observed_trial(args, arm):
    """Record the paid validation prefix before applying any independent proof."""
    ledger = {}
    original_certificates, original_select = core.certificates, math.select

    def certificates(incumbent, candidates, rows, training, observe, paid, cap):
        result = next(original_certificates(incumbent, candidates, rows, training, observe, paid, cap), None)
        ledger.update(paid)
        if result is not None:
            yield result

    def select(incumbent, candidates, rows, observe, paid, **kwargs):
        result = original_select(incumbent, candidates, rows, observe, paid, **kwargs)
        ledger.update(paid)
        return result

    if arm == core.FIRST:
        with patch.object(core, 'certificates', certificates):
            result = core.trial(*args, arm)
    else:
        with patch.object(math, 'select', select):
            result = prior.prior.run_trial(*args, ())[:3]
    return result, ledger


def attribute(menu, start, deployed, rows, ledger, limits):
    """Price favorable unread validation replies for a better admissible nominee."""
    current = max(menu[deployed][0], 0)
    best = max(gain for gain, _ in menu.values()) - current
    if not best:
        return Counter(), Counter()
    target = 1 + sum(ledger[start, str(case)].passed for case in rows)
    choices = []
    for candidate, (gain, _) in menu.items():
        if gain <= current:
            continue
        observed = [ledger[candidate, str(case)].passed for case in rows if (candidate, str(case)) in ledger]
        missing = max(0, target - sum(observed))
        category = 'unprobed' if not observed else 'partial' if missing else 'certified'
        choices.append((gain - current, missing, category))
    _, _, category = min((row for row in choices if row[0] == best), key=lambda row: (row[1], row[2] == 'unprobed'))
    return (Counter({category + 'Trials': 1, category + 'Passes': best}),
            Counter({str(limit): max((gain for gain, missing, _ in choices if missing <= limit), default=0)
                     for limit in limits}))


def backup_certificate(incumbent, later, rows, training, observe, ledger, *, cap, extra):
    base = {row.id: ledger[incumbent, row.id].passed for row in rows}
    target = sum(base.values()) + 1
    protected = {row.id for row in rows if row.critical and base[row.id]}
    deadline = len(ledger) + extra
    row_ids = set(base)
    hits, reads = Counter(), Counter()
    for (_, case), reply in ledger.items():
        if case in row_ids:
            hits[case] += reply.passed
            reads[case] += 1
    for prompt in later:
        if any((prompt, row.id) in ledger for row in rows):
            raise ValueError('The backup race expects an unopened later candidate')
        missing = set(protected)
        passed = 0
        reserve = sum((name, row.id) not in ledger for name in (incumbent, prompt) for row in training)
        available = min(deadline, cap - reserve)
        order = sorted(rows, key=lambda row: (row.id not in protected,
                                              Fraction(hits[row.id] + 1, reads[row.id] + 2)))
        for offset, row in enumerate(order):
            if max(target - passed, len(missing)) > min(available - len(ledger), len(rows) - offset):
                break
            grade = observe(prompt, row).passed
            if type(grade) is not bool:
                raise ValueError('Backup certification requires exact boolean grades')
            hits[row.id] += grade
            reads[row.id] += 1
            passed += grade
            if row.id in missing:
                if not grade:
                    break
                missing.remove(row.id)
            if passed >= target and not missing:
                return prompt, offset + 1
    return None


def run_trial(cells, start, roster, cohorts, seed, cap, limit):
    original, train = core.certificates, core.backup.select_with_training
    audit, training_cost = Counter(), Counter()

    def certificates(incumbent, candidates, rows, training, observe, ledger, cap):
        result = next(original(incumbent, candidates, rows, training, observe, ledger, cap), None)
        if result is None:
            return

        def supported(prompt):
            return train(incumbent, prompt, (), rows, training, observe, ledger, cap=cap, seed=seed,
                         mode=core.backup.PRECHECKED[core.backup.PRECHECK], audit=training_cost) == prompt

        first, _ = result
        if supported(first):
            yield result
            return
        audit['primaryTrainingVeto'] += 1
        before = len(ledger)
        alternate = backup_certificate(incumbent, candidates[candidates.index(first) + 1:], rows, training,
                                       observe, ledger, cap=cap, extra=limit)
        audit.update(extraValidationLookups=len(ledger) - before, backupCertificates=int(alternate is not None))
        if alternate is not None and supported(alternate[0]):
            audit['backupNominations'] += 1
            yield alternate

    with (patch.object(core, 'certificates', certificates), patch.object(core.prior, 'can_defer', lambda *_: False),
          patch.object(core.backup, 'select_with_training', lambda _, first, *args, **kwargs: first)):
        point, trace, grades = core.trial(cells, start, roster, cohorts, seed, cap, core.FIRST)
    if (point['searchLookups'] > cap or point['qualificationLookups'] > 2 * len(cohorts[2])
            or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']
            or audit['extraValidationLookups'] > limit):
        raise ValueError('Backup validation and independent qualification must fit their respective limits')
    return {**point, **audit, **training_cost}, trace, grades


def prepare():
    inherited, data, baseline, _ = prior.prepare()
    report = transfer.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, inherited)
    source_plan, _, controls, _ = prior.parent.prepare()
    plan = {**{key: source_plan[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                                 'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-bounded-certificate-backup-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': REFERENCE_SHA256, 'validationReadLimits': LIMITS,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Audit how much of the earlier roster ceiling was visible in paid validation, '
                     'including the subset where the first nominee fails training. '
                     'After a strict training veto, buy up to four or eight validation replies to certify '
                     'one previously unopened later candidate. Require its strict training gain and keep '
                     'one independent qualification attempt. Preserve the original roster and GEPA frontier.'}
    return plan, data, controls, baseline, report['results']


def measure(plan, cells, settings, group, width, controls, baseline, mode):
    original = core.trial

    def trial(*args):
        return run_trial(*args[:-1], LIMITS[mode])

    def existing(*args):
        return prior.parent.run_trial(*args[:-1]) if args[-1] == prior.parent.ORDERED else original(*args)

    anchors = {**controls, 'totals': {**controls['totals'],
                                     prior.parent.ORDERED: baseline['anchors'][prior.parent.ORDERED]}}
    with (patch.object(transfer, 'PRIMARY', mode),
          patch.object(transfer, 'METHODS', (mode, core.FIRST, prior.parent.ORDERED)),
          patch.object(core, 'trial', existing), patch.object(transfer.parity.shortlist, 'trial', trial)):
        result = transfer.measure(plan, cells, settings, group, width, anchors)
    if (any(point != baseline['totals'][label] for label, point in result['totals'].items() if label != mode)
            or any(value[core.FIRST] != baseline['comparisons'][key][core.FIRST]
                   for key, value in result['comparisons'].items())):
        raise ValueError('The original first certificate and GEPA costs must reproduce')
    return {'totals': result['anchors'][mode],
            'comparisons': {key: value[mode] for key, value in result['comparisons'].items()}}


def audit(plan, cells, settings, group, width, reference):
    result = {arm: (Counter(), Counter()) for arm in prior.ANCHORS}
    after_veto = Counter({str(limit): 0 for limit in range(9)})
    for start, roster, cohorts, seed in transfer.trials(cells, settings, group, width):
        args = cells, start, roster, cohorts, seed, plan['searchCap']
        _, _, menus = prior.offers(cells, start, roster, cohorts, plan['searchCap'])
        for arm, gate in zip(prior.ANCHORS, (prior.TRAINED, prior.VALIDATED), strict=True):
            (_, trace, _), ledger = observed_trial(args, arm)
            distribution, ceiling = attribute(menus[gate], start, trace[3], cohorts[1], ledger, range(9))
            result[arm][0].update(distribution)
            result[arm][1].update(ceiling)
            nominee = trace[2]
            if arm == core.FIRST and nominee != start:
                training = cohorts[0][:len(cohorts[0]) // 2]
                if sum(cells[nominee][case][0] - cells[start][case][0] for case in training) <= 0:
                    eligible = {start, *roster[roster.index(nominee) + 1:]}
                    later = {prompt: offer for prompt, offer in menus[gate].items() if prompt in eligible}
                    _, veto_ceiling = attribute(later, start, start, cohorts[1], ledger, range(9))
                    after_veto.update(veto_ceiling)
    summaries = {}
    for arm, (distribution, ceiling) in result.items():
        expected = reference['gateMatchedHeadroom'][arm]['passesFromBetterNominees']
        if sum(value for key, value in distribution.items() if key.endswith('Passes')) != expected or ceiling['8'] != expected:
            raise ValueError('Paid validation attribution must account for all nomination headroom')
        summaries[arm] = {'bestAlternativeByPaidStatus': distribution, 'optimisticExtraPassesByReadLimit': ceiling}
    summaries[core.FIRST]['optimisticExtraPassesAfterTrainingVeto'] = after_veto
    return summaries


def replay(plan, data, controls, baseline, reference):
    results = {}
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        results[dataset] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                name = f'{group}/{width}'
                results[dataset][name] = {'evidence': audit(plan, cells, settings, group, width, reference[dataset][name]),
                                          **{mode: measure(plan, cells, settings, group, width, controls[dataset][name],
                                                          baseline[dataset][name], mode) for mode in LIMITS}}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
