"""Locate the remaining MMLU gap and price alternative one-admission decisions."""

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_cached_gepa_evidence as paired
from cpo._contract import digest


ROOT, REPLAY = paired.ROOT, paired.replay.REPLAY
RECEIPT = 'docs/witness-cached-gepa-evidence-results-v1.json'
RECEIPT_SHA256 = '83d5af833cc34a83598744ed94799ca04896fdfb4c0c73e9d38ea778884f6b39'
MENUS = ('retention', 'paid-paired-win', 'already-read', 'whole-roster')


@dataclass(frozen=True)
class Decision:
    prompt: str
    status: str
    paid: int
    proof: int
    grades: dict


def prepare():
    previous, _, data = paired.prepare()
    raw = (ROOT / RECEIPT).read_bytes()
    receipt = json.loads(raw)
    if sha256(raw).hexdigest() != RECEIPT_SHA256 or receipt['planSha256'] != digest(previous):
        raise ValueError('Use the published paired comparison and native traces')
    source = Path(__file__).resolve()
    plan = {'protocol': 'witness-mmlu-gap-v1', 'parentPlanSha256': digest(previous),
            'pairedReceiptSha256': RECEIPT_SHA256, 'sourceSha256': sha256(source.read_bytes()).hexdigest(),
            'cohorts': {phase: previous['cohorts'][phase] for phase in paired.replay.PHASES},
            'fixedControls': {phase: receipt['cohorts'][phase]['observedBestAffordableNative']
                              for phase in paired.replay.PHASES},
            'pooledHindsightControls': receipt['cohorts']['mmlu-pooled']['hindsightNativeAllocation']['nativeArmsBySubject'],
            'menus': MENUS, 'fallbackValidationCap': previous['fallbackValidationCap'],
            'bound': 'Freeze each episode’s complete paid search. Replay at most one exact admission on the '
                     'challenger’s enrolled panel and permit it only within that episode’s original proof spend. '
                     'Choose among feasible deployments using holdout in hindsight.'}
    return plan, receipt, data


def cpo_route(matrix, held, start, layouts, active, policy, cap):
    original = paired.replay.original
    prompt, paid, _, grades, proof = original.play(matrix, held, start, layouts, active, policy, original.witness)
    if proof:
        return Decision(prompt, 'witness-promoted' if prompt != start else 'witness-rejected', paid, proof, grades)

    trial = paired.CachedLookaheadHalving(metric_limit=cap, paid=grades)
    prompt, proof = paired.replay.capped.transfer_trial(matrix, held, start, layouts, active, policy, trial)
    status = ('fallback-promoted' if prompt != start else 'fallback-rejected' if proof else
              'fallback-capped' if trial.exhausted else 'no-nominee')
    if trial.exhausted and proof:
        raise ValueError('An unfinished fallback cannot begin admission')
    return Decision(prompt, status, paid + trial.evaluations + proof, proof, trial.observations)


def paired_win(graded, incumbent, challenger):
    return any(prompt == challenger and passed and graded.get((incumbent, case)) is False
               for (prompt, case), passed in graded.items())


def price_options(decision, start, layouts, plan, policy, evaluate, score):
    """Price complete independent proofs, then use holdout only to rank feasible choices."""
    incumbent = score(start)
    realized = score(decision.prompt)
    best = dict.fromkeys(MENUS, max(incumbent, realized))
    if decision.proof == 0:
        return {menu: value - realized for menu, value in best.items()}

    paid_prompts = {prompt for prompt, _ in decision.grades}
    bank = []
    for layout in layouts:
        current = layout['qualify']
        for prompt in layout['alternatives']:
            selected, _, receipt = REPLAY.qualify(start, prompt, current, bank.copy(), set(), evaluate, plan=plan,
                                                  seed=layout['seed'], recycle=policy == 'recycle-unread')
            if selected != prompt or receipt['qualificationLookups'] > decision.proof:
                continue
            quality = score(prompt)
            best['whole-roster'] = max(best['whole-roster'], quality)
            if prompt in paid_prompts:
                best['already-read'] = max(best['already-read'], quality)
            if paired_win(decision.grades, start, prompt):
                best['paid-paired-win'] = max(best['paid-paired-win'], quality)
        bank.extend(current)
    return {menu: value - realized for menu, value in best.items()}


def attribute(target, start, decision):
    if target == decision.prompt:
        return 'same-deployment'
    if target == start:
        return 'native-kept-start'
    if decision.prompt != start:
        return 'different-promotions'
    return f'native-promoted-after-{decision.status}'


def measure_phase(plan, phase, data):
    inputs, panels, expected, settings, base_cap = data
    schedule, policy = inputs['schedule'], inputs['qualificationBank']
    active = {**schedule, 'evaluationLookupLimit': base_cap}
    statuses, comparison, ceilings = defaultdict(Counter), defaultdict(lambda: defaultdict(Counter)), Counter()
    totals, by_subject, traces = Counter(), defaultdict(Counter), {}
    fixed = plan['fixedControls'][phase]
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        key = f'{subject}/{model}'
        controls = {'fixed': fixed, 'hindsight': plan['pooledHindsightControls'][subject]}
        native_totals, native_traces = defaultdict(Counter), defaultdict(list)
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        panel_trace = []

        def grade(prompt, case):
            return matrix[int(prompt)][case] == '1'

        def score(prompt):
            return sum(grade(prompt, case) for case in held)

        for seed in schedule['seeds']:
            start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
            decision = cpo_route(matrix, held, start, layouts, active, policy, plan['fallbackValidationCap'])
            observed, initial = score(decision.prompt), score(start)
            totals.update(episodes=1, holdoutPasses=observed, paidLookups=decision.paid, proofLookups=decision.proof)
            statuses[decision.status].update(episodes=1, gainOverStart=observed - initial,
                                             positiveGain=max(0, observed - initial), lostPasses=max(0, initial - observed),
                                             paidLookups=decision.paid, proofLookups=decision.proof)
            upper = price_options(decision, start, layouts, active, policy, grade, score)
            ceilings.update(upper)
            by_subject[subject].update(holdoutDecisions=len(held), candidatePasses=observed, **upper)
            selections = {}
            for arm in dict.fromkeys(controls.values()):
                if arm == paired.replay.START:
                    final, paid, trace = start, 0, None
                else:
                    config = settings[arm]
                    own = {**schedule, 'evaluationLookupLimit': config['searchCap']}
                    final, costs, trace = paired.replay.native.capped_episode(
                        matrix, held, start, layouts, own, arm, policy, config['validationRows'])
                    paid = costs['paidLookups']
                selections[arm] = final, paid
                native_totals[arm].update(holdoutPasses=score(final), paidLookups=paid)
                native_traces[arm].append((seed, final, trace))
            for kind, arm in controls.items():
                final, paid = selections[arm]
                delta = score(final) - observed
                fact = comparison[kind][attribute(final, start, decision)]
                fact.update(episodes=1, nativeNetPasses=delta, nativeWins=max(0, delta), cpoWins=max(0, -delta),
                            nativeNomineeAlreadyRead=int(final != start and any(p == final for p, _ in decision.grades)),
                            nativeNomineePaidPairedWin=int(final != start and paired_win(decision.grades, start, final)))
                by_subject[subject].update({f'{kind}Passes': score(final), f'{kind}PaidLookups': paid})
            panel_trace.append((seed, start, decision.prompt, decision.status, decision.paid, decision.proof, selections, upper))
        for arm, measured in native_totals.items():
            recorded = expected[key][arm]
            if any(measured[field] != recorded[field] for field in measured) or (
                    'traceSha256' in recorded and digest(native_traces[arm]) != recorded['traceSha256']):
                raise ValueError(f'The matched native archive differs for {key}/{arm}')
        traces[key] = digest(panel_trace)
    macro = {field: str(sum(Fraction(item[field], item['holdoutDecisions']) for item in by_subject.values())
                        / len(by_subject)) for field in ('candidatePasses', 'fixedPasses', 'hindsightPasses', *MENUS)}
    return {'totals': totals, 'status': statuses, 'comparison': comparison, 'extraPassCeilings': ceilings,
            'macroRatesAndCeilingGains': macro, 'subjects': by_subject, 'panelTraceSha256': traces}


def execute(plan, receipt, data):
    if version('gepa') != '0.1.4':
        raise ValueError('Use the pinned native GEPA version')
    optimizer = import_module('gepa.optimize_anything')
    original = optimizer.optimize_anything

    def disjoint(*args, dataset, valset, **settings):
        train, validation = [paired.replay.native.transfer.CaseRows({**row, 'id': row['case']} for row in rows)
                             for rows in (dataset, valset)]
        if train.by_id.keys() & validation.by_id.keys():
            raise ValueError('Native training and validation identities overlap')
        return original(*args, dataset=train, valset=validation, **settings)

    with patch.object(optimizer, 'optimize_anything', disjoint):
        phases = {phase: measure_phase(plan, phase, data[phase]) for phase in paired.replay.PHASES}
    for phase, report in phases.items():
        prior = receipt['cohorts'][phase]['totals'][paired.replay.CANDIDATE]
        if any(report['totals'][key] != prior[key] for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError(f'The published CPO score or cost differs in {phase}')
    pooled = {subject: record for phase in phases.values() for subject, record in phase['subjects'].items()}
    hindsight_cost = sum(item['hindsightPaidLookups'] for item in pooled.values())
    hindsight_accuracy = str(sum(Fraction(item['hindsightPasses'], item['holdoutDecisions']) for item in pooled.values())
                             / len(pooled))
    reference = receipt['cohorts']['mmlu-pooled']['hindsightNativeAllocation']
    if (hindsight_cost, hindsight_accuracy) != (reference['paidLookups'], reference['macroAccuracy']):
        raise ValueError('The pooled retrospective GEPA allocation failed to reproduce')
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'phases': phases}


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
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    result = execute(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
