"""Bound recovery after a training veto on the recorded AIME and ARC search paths."""

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_one_read_backup as prior
from cpo._contract import digest


math, parent = prior.math, prior.parent
REFERENCE = 'docs/recorded-one-read-backup-results-v1.json'
REFERENCE_SHA256 = 'a71f8567b5f21051d675aa2be45950b4ec474ca9ae4b6c1187ed1cddfa700986'
LIMITS = (1, 2, 3, 'full')


@dataclass(frozen=True)
class Offer:
    gain: int
    validation: int
    training: int
    qualification: int
    primary_veto: int

    @property
    def total(self):
        return self.validation + self.training + self.qualification + self.primary_veto


def gain(cells, start, candidate, rows):
    return sum(cells[candidate][case][0] - cells[start][case][0] for case in rows)


def proof_floor(start, candidate, rows, paid, *, promote):
    """Count the minimum unread replies needed to certify a known scalar outcome."""
    lower, upper = -len(rows), len(rows)
    for case in rows:
        for prompt in (start, candidate):
            if (prompt, case) not in paid:
                continue
            if paid[prompt, case] == (prompt == candidate):
                lower += 1
            else:
                upper -= 1
    return max(0, 1 - lower if promote else upper)


def offers(cells, start, first, roster, cohorts, paid_search, paid_proof, *, cap):
    train, validation, proof, held = cohorts
    train = train[:len(train) // 2]
    if gain(cells, start, first, train) > 0:
        return []
    old_score = sum(paid_search[start, case] for case in validation)
    # A new incumbent pass helps the veto, and a new incumbent miss helps the backup.
    # No unread training reply can lower both proof costs.
    veto = proof_floor(start, first, train, paid_search, promote=False)
    eligible = []
    for prompt in roster:
        if prompt == first or any(gain(cells, start, prompt, rows) <= 0 for rows in (validation, train, proof)):
            continue
        validation_reads = old_score + 1 - sum(paid_search.get((prompt, case), False) for case in validation)
        if validation_reads <= 0:
            raise ValueError('A fully paid backup belongs to the existing policy')
        training_reads = proof_floor(start, prompt, train, paid_search, promote=True)
        if len(paid_search) + veto + validation_reads + training_reads > cap:
            continue
        improved = gain(cells, start, prompt, held)
        if improved > 0:
            qualification_reads = proof_floor(start, prompt, proof, paid_proof, promote=True)
            eligible.append(Offer(improved, validation_reads, training_reads, qualification_reads, veto))
    return eligible


def decision_with_paid_replies(cells, start, roster, cohorts, seed, cap):
    original_select, original_qualify = math.select, parent.qualify_with_prefix
    first, backup, ledger = start, None, {}
    settled = {}

    def select(incumbent, candidates, rows, observe, paid, **settings):
        nonlocal first, backup, ledger
        first, tied = original_select(incumbent, candidates, rows, observe, paid, **settings)
        ledger = paid
        if first != incumbent:
            if any(row.critical for row in rows):
                raise ValueError('The archived validation panel must be scalar and noncritical')
            backup = prior.backup.strongest_backup(incumbent, first, candidates, rows, paid, partial=True)
        return first, tied

    def qualify(*args, **kwargs):
        decision = original_qualify(*args, **kwargs)
        for reply in decision.observations:
            if reply.repeat != 0:
                raise ValueError('The archived qualification panel uses one reply per case')
            settled[reply.prompt, int(reply.row_id)] = reply.passed
        return decision

    with (patch.object(math, 'select', select), patch.object(parent, 'qualify_with_prefix', qualify)):
        point, trace, _ = parent.run_trial(cells, start, roster, cohorts, seed, cap,
                                          prior.prior.CANDIDATE, parent.EXPECTED)
    if first == start or backup is not None or trace[3] != start:
        return point, trace, False, []
    # The precheck is charged even when qualification never reaches its certificate.
    for case in cohorts[2][:point['precheckLookups']]:
        key = start, case
        settled.setdefault(key, bool(cells[start][case][0]))
    paid = {(prompt, int(case)): observation.passed for (prompt, case), observation in ledger.items()}
    if len(paid) != point['searchLookups'] or len(settled) != point['qualificationLookups']:
        raise ValueError('The bound must keep every paid search and qualification reply')
    training = cohorts[0][:len(cohorts[0]) // 2]
    vetoed = gain(cells, start, first, training) <= 0
    return point, trace, vetoed, offers(cells, start, first, roster, cohorts, paid, settled, cap=cap)


def prepare():
    previous, data, _ = prior.prepare()
    raw = (prior.backup.ROOT / REFERENCE).read_bytes()
    old = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or old['planSha256'] != digest(previous):
        raise ValueError('Use the exact published one-read backup result and seeded control')
    plan = {**{key: previous[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                             'gepaVersion', 'minimumLookupSavingPercent')},
            'protocol': 'recorded-training-veto-backup-ceiling-v1', 'parentPlanSha256': digest(previous),
            'parentReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'additionalValidationReadLimits': LIMITS,
            'scope': 'Keep each seeded deployment and paid reply. After retention without a paid backup, require '
                     'a real primary training veto and exact validation, training, and qualification gains for an '
                     'alternate. Price each proof at its shortest possible paid completion and select the most '
                     'helpful affordable alternate in hindsight. The bound omits the cost of choosing replies.'}
    return plan, data, old['results']


def measure(cells, settings, group, width, plan, reference):
    size = len(next(iter(cells.values())))
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    columns = ('helpedTrials', 'extraPasses', 'addedValidationReads', 'addedTrainingReads',
               'addedQualificationReads', 'addedPrimaryVetoReads', 'addedPaidLookups')
    receipts = {str(limit): Counter(dict.fromkeys(columns, 0)) for limit in LIMITS}
    baseline, counts, logs = Counter(), Counter(), []
    for seed in settings['seeds']:
        cohorts = math.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            available = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(available, len(available))[:width]
            measured, trace, vetoed, eligible = decision_with_paid_replies(cells, start, roster, cohorts, seed,
                                                                         plan['searchCap'])
            baseline.update(measured)
            logs.append(trace)
            counts.update(trials=1, retainedWithTrainingVetoAndNoPaidBackup=int(vetoed),
                          anyHelpfulBackup=int(bool(eligible)))
            for limit in LIMITS:
                cap = len(cohorts[1]) if limit == 'full' else limit
                best = max((row for row in eligible if row.validation <= cap),
                           key=lambda row: (row.gain, -row.total), default=None)
                if best is not None:
                    receipts[str(limit)].update(helpedTrials=1, extraPasses=best.gain, addedValidationReads=best.validation,
                                                addedTrainingReads=best.training, addedQualificationReads=best.qualification,
                                                addedPrimaryVetoReads=best.primary_veto, addedPaidLookups=best.total)
    seeded = {**baseline, 'traceSha256': digest(logs)}
    if seeded != reference['totals'][prior.prior.CANDIDATE] or counts['trials'] != reference['trials']:
        raise ValueError('The seeded CPO control must reproduce before bounding an alternate')
    controls = {arm: {key: reference['totals'][arm][key] for key in ('holdoutPasses', 'paidLookups')}
                for arm in prior.prior.CONTROLS.values()}
    cheapest = min(point['paidLookups'] for point in controls.values())
    paid_cap = (100 - plan['minimumLookupSavingPercent']) * cheapest // 100
    floors = {limit: {**values, 'ceilingHoldoutPasses': baseline['holdoutPasses'] + values['extraPasses'],
                      'paidLookupsAtCeiling': baseline['paidLookups'] + values['addedPaidLookups']}
              for limit, values in receipts.items()}
    return {'counts': counts, 'baseline': seeded, 'controls': controls, 'paidLookupGateCap': paid_cap,
            'remainingLookupsAtGateBeforeBackup': paid_cap - baseline['paidLookups'], 'ceilings': floors}


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
