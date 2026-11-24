"""Attribute the fixed CPO policy's language gap on the same cycle incumbents."""

import argparse
from collections import Counter
from functools import cache, partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import reinvested_halving_language_transfer as parent
from cpo import reinvested_shared_validation_cycle as halving
from cpo._contract import digest
from cpo.quoted_shared_validation_cycle import run_quoted_shared_validation_cycle
from cpo.two_sided_certificate_cycle import _run


COHORTS = parent.continuous.COHORTS
RECEIPTS = dict(zip(COHORTS, (
    '49f38d1dcf358b314ed60c0d8c93379f76a15fffbe26904129894db331a38c44',
    '9d2520c30cf66ee6cf05b8727e774d2e5226d88305f2a8d71f3ddd7f1146c46d',
    '2be2e4cd5dc7ef762d5a1d0a73fae40b5f1ca5f83cf1d6ef8ba48ae4b2a1c811',
    '9f1174a4b294aeaad95ab5cc334bf9ece5ea05aab8246d41e50a6ded7802e2e0',
    '2381d3809bb0f18d868828799416cbbb6a867a29aa19057e54dbfc9d3d1ff7a4',
    '6758a0cca526900fa36bd8ef151423e9fc84e23ff2f2da736ac27ce4902cfcd0',
    '77324786b59cb5ee4d386647c5e5238d652c5180bef84652aa33b2856966549b',
), strict=True))


def prepare(cohort):
    base, panels, _, _, priors, gepa, simple = parent.prepare(cohort)
    lock = RECEIPTS[cohort]
    receipt = json.loads(parent.transfer.read_locked(f'docs/reinvested-halving-language-transfer-{cohort.lower()}-v1.json',
                                                     lock))
    if receipt['planSha256'] != digest(base):
        raise ValueError('Attribution requires the exact prior transfer plan')
    root = parent.transfer.ROOT
    files = (Path(__file__).resolve(), root / 'cpo/quoted_shared_validation_cycle.py')
    sources = {str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest() for file in files}
    plan = {**base, 'protocol': 'reinvested-halving-gap-attribution-v1', 'transferReceiptSha256': lock,
            'sourceSha256': {**base['sourceSha256'], **sources},
            'scope': 'Replace one more leading CPO cycle with the archived task-tuned simple setting at a time. '
                     'For each replacement, run both policies from the same incumbent, then complete every '
                     'remaining cycle with CPO. Classify the simple action by paid CPO shortlist membership '
                     'and examine the full-panel validation margin separately. The exact score and price '
                     'changes telescope from the original CPO rollout to the original simple rollout. '
                     'Replay those same simple settings through quoted shared validation and check exact '
                     'nomination and qualification parity on every cycle before crediting any savings. '
                     'Reprice the earlier native GEPA bounds at the resulting paid budget.'}
    return plan, panels, priors, receipt['results'], gepa, simple['settingsTotals'][parent.RETAIN]['holdoutPasses']


def channel(start, roster, simple, cpo, survivors):
    if simple == cpo:
        return 'same-deployment'
    if simple == start:
        return 'simple-retained'
    if simple not in roster:
        return 'outside-cpo-roster'
    if len(survivors) != 6:
        raise ValueError('A viable simple challenger needs all six CPO rounds at the frozen cap')
    for depth, active in enumerate(survivors[:-1], 1):
        if simple not in active:
            return f'dropped-at-row-{depth}'
    if simple not in survivors[-1]:
        return 'lost-final-rank'
    return 'no-validation-gain'


def episode(cells, plan, start, stages, simple_setting, proof):
    run = parent.native.paired.cycle.execute_path
    cap, width = plan['halvingCap'], plan['halvingWidth']
    held = stages[0][2][-1]
    shortlist = halving._shortlist
    old_finish = parent.joint.ORIGINAL_FINISH
    if simple_setting != parent.RETAIN:
        mode, bound, limit = simple_setting.split('/')
        simple_width, simple_cap = int(bound), int(limit)
        simple = partial(_run, screen=partial(parent.controls.screen, mode=mode, width=simple_width))
        quoted = partial(run_quoted_shared_validation_cycle, schedule=mode)

    @cache
    def cpo_step(index, base):
        local_seed, roster, roles = stages[index]
        kept = []

        def record(*args):
            active = shortlist(*args)
            kept.append(active)
            return active

        with (patch.object(halving, '_shortlist', record),
              patch.object(parent.joint.two_sided_certificate_cycle, '_finish_with_partner_evidence', proof)):
            result, charges = run(halving.run_reinvested_shared_validation_cycle, cells, base, roster[:width], roles,
                                  local_seed, cap, 1)
        parent.continuous.routing.verify_qualification(cells, base, roles, result, charges, 1)
        return result, charges, kept

    def simple_step(index, base):
        if simple_setting == parent.RETAIN:
            return base, 0, 0
        local_seed, roster, roles = stages[index]
        with patch.object(parent.joint.two_sided_certificate_cycle, '_finish_with_partner_evidence', old_finish):
            args = cells, base, roster[:simple_width], roles, local_seed, simple_cap, 1
            result, charges = run(simple, *args)
            certified, kept = run(quoted, *args)
        if (certified.search.finalist != result.search.finalist or certified.qualification != result.qualification
                or not kept.keys() <= charges.keys()):
            raise ValueError('A quoted simple schedule must preserve the original decision and charge only original replies')
        parent.continuous.routing.verify_qualification(cells, base, roles, result, charges, 1)
        return result.prompt, len(charges), len(charges) - len(kept)

    def suffix(first, base):
        trace = []
        for index in range(first, len(stages)):
            result, charges, _ = cpo_step(index, base)
            trace.append((base, result.prompt, result.search.finalist, list(charges.items())))
            base = result.prompt
        return sum(cells[base][case] for case in held), sum(len(row[-1]) for row in trace), trace

    old_score, old_cost, trace = suffix(0, start)
    base, paid, saved = start, 0, 0
    before, before_cost = old_score, old_cost
    result_rows = []
    for index, (_, roster, roles) in enumerate(stages):
        choice, charge, spared = simple_step(index, base)
        decision, _, survivors = cpo_step(index, base)
        after, suffix_cost, _ = suffix(index + 1, choice)
        paid += charge
        saved += spared
        hybrid_cost = paid + suffix_cost
        reason = channel(base, roster[:width], choice, decision.prompt, survivors)
        if reason == 'no-validation-gain' and decision.search.finalist is not None:
            raise ValueError('The last surviving simple candidate is either the same nominee or no nominee')
        case_score = sum(cells[choice][case] - cells[base][case] for case in roles[1])
        rejected = decision.search.finalist is not None and not decision.promoted
        delta = after - before
        result_rows.append((reason, {'switches': 1, 'holdoutPassDifference': delta,
                                    'gainedPasses': max(delta, 0), 'lostPasses': max(-delta, 0),
                                    'paidLookupDifference': hybrid_cost - before_cost,
                                    'simpleHasStrictFullValidationGain': int(case_score > 0),
                                    'cpoNominationRejected': int(rejected)}))
        before, before_cost = after, hybrid_cost
        base = choice
    cpo_step.cache_clear()
    original = {'holdoutPasses': old_score, 'paidLookups': old_cost}
    control = {'holdoutPasses': before, 'paidLookups': paid}
    return original, control, saved, trace, result_rows, [cells[base][case] for case in held]


def measure(plan, panels, priors, reference, gepa, retention):
    proof = partial(parent.finish_joint_order, priors=priors)
    schedule = reference['simpleAtCandidateBudget']['subject-tuned-simple']
    by_reason, by_stage, by_subject = {}, {}, {}
    vectors = {}
    add = parent.native.paired.frontier.transfer.fitted.prior.add_vector
    cpo, simple = Counter(), Counter()
    saved = 0
    for subject, model, matrix in panels:
        cells, _ = parent.transfer.case_cells(matrix)
        traces = []
        for seed in plan['seeds']:
            start, stages = parent.continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
            old, control, spared, transcript, changes, grades = episode(
                cells, plan, start, stages, schedule['settingsBySubject'][subject], proof,
            )
            add(vectors.setdefault(subject, {}).setdefault('quoted-simple', [0] * len(grades)), grades)
            cpo.update(old)
            simple.update(control)
            saved += spared
            traces.extend(transcript)
            for index, (reason, point) in enumerate(changes, 1):
                by_reason.setdefault(reason, Counter()).update(point)
                by_stage.setdefault(index, {}).setdefault(reason, Counter()).update(point)
                by_subject.setdefault(subject, {}).setdefault(reason, Counter()).update(point)
        if digest(traces) != reference['trajectoryHashes'][f'{subject}/{model}'][parent.CANDIDATE]:
            raise ValueError('The original CPO paid trajectory must reproduce before attribution')
    for name, observed, expected in (('CPO', cpo, reference['policies'][parent.CANDIDATE]), ('simple', simple, schedule)):
        if observed != {key: expected[key] for key in parent.METRICS}:
            raise ValueError(f'The original {name} score and cost must reproduce before attribution')
    for metric, source in (('holdoutPassDifference', 'holdoutPasses'), ('paidLookupDifference', 'paidLookups')):
        if sum(point[metric] for point in by_reason.values()) != simple[source] - cpo[source]:
            raise ValueError('Every difference must reconcile across the three same-incumbent replacements')
    quoted = {**simple, 'paidLookups': simple['paidLookups'] - saved}
    bounds, attainers = parent.compare_native(plan, panels, gepa, quoted['paidLookups'], retention, vectors)
    effect = parent.native.frozen.paired_effects.paired_effect
    return {'cpo': cpo, 'simple': simple, 'quotedSimple': quoted, 'lookupsSaved': saved,
            'nativeBoundsAtQuotedBudget': bounds, 'replayedNativeAnchors': attainers,
            'pairedAgainstNativeAttainers': {name: effect(vectors, 'quoted-simple', name, plan) for name in attainers},
            'byChannel': by_reason, 'byCycle': by_stage, 'bySubject': by_subject}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.cohort)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': measure(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
