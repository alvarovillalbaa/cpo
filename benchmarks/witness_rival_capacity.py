"""Locate the limits of rival selection after a reserved independent proof."""

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from benchmarks import witness_proof_split as split
from cpo._contract import digest


ROOT, REPLAY, RANKING, retry = split.ROOT, split.REPLAY, split.RANKING, split.retry
REFERENCE = 'docs/witness-proof-split-results-v1.json'
REFERENCE_SHA256 = '5d80ec72d78dedb2160f2cd9153e072b286eb860ef9eee95d15ab499eb619f1f'
LIMITS = ('same-realized-spend', 'remaining-cap')


@dataclass(frozen=True)
class Rival:
    prompt: str
    gain: int
    status: str
    lookups: int


def prepare():
    parent, _, data = split.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('Use the published reserved proof replay')
    plan = {'protocol': 'witness-rival-capacity-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': REFERENCE_SHA256,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'limits': LIMITS,
            'fallbackValidationCap': parent['fallbackValidationCap'],
            'jointProofCap': parent['jointProofCap'],
            'scope': 'Keep the reserved-futility first proof and all search lookups fixed. On actual second '
                     'attempts, price exact independent qualification for each already-read rival. Compare '
                     'the best holdout score obtainable with a permitted rival or the start. Use the full '
                     'roster only to measure whether search reached any held-out improvement.'}
    return plan, reference, data


def summarize_rivals(rivals, unseen_gain, spent, remaining):
    if not 0 <= spent <= remaining:
        raise ValueError('The observed rival must fit the remaining proof allowance')
    positive = [rival for rival in rivals if rival.gain > 0]
    certifiable = [rival for rival in positive if rival.status == 'promoted']
    within_cap = [rival for rival in certifiable if rival.lookups <= remaining]
    if within_cap:
        cause = 'paid-improvement-fits'
    elif certifiable:
        cause = 'paid-improvement-exceeds-cap'
    elif positive:
        cause = 'paid-improvement-fails-proof'
    elif unseen_gain:
        cause = 'improving-rivals-unread'
    else:
        cause = 'no-improving-enrolled-rival'
    keep = Rival('', 0, 'retained', 0)
    chosen = {label: max((keep, *(rival for rival in within_cap if rival.lookups <= cap)),
                         key=lambda rival: (rival.gain, -rival.lookups))
              for label, cap in zip(LIMITS, (spent, remaining), strict=True)}
    return cause, chosen


def assess(matrix, held, start, layouts, plan, nomination, observed):
    nominee = nomination.original
    roster = {prompt: index for index, layout in enumerate(layouts) for prompt in layout['alternatives']}
    cycle = roster[nominee]
    current = layouts[cycle]['qualify']
    reserve_size = plan['maximumExtensionRows']
    reserve = [case for earlier in layouts[:cycle] for case in earlier['qualify']][:reserve_size]
    retired = set(current) | set(reserve)
    paid = {prompt for prompt, _ in nomination.grades}
    ranked = retry.ranked_rival(layouts, nominee, nomination.grades)
    minimum = plan['minimumQualificationGain']
    starting_score = sum(matrix[int(start)][case] == '1' for case in held)
    first_spend = observed.lookups - observed.retry_lookups
    remaining = split.CAP - first_spend
    options, unseen_gain = [], False

    for prompt, enrolled in roster.items():
        if prompt == nominee:
            continue
        gain = sum(matrix[int(prompt)][case] == '1' for case in held) - starting_score
        if prompt not in paid:
            unseen_gain |= gain > 0
            continue
        index = retry.retry_panel(layouts, enrolled, retired)
        if index is None:
            raise ValueError('A switched episode requires an independent backup panel')
        backup = layouts[index]['qualify']
        if len(backup) != len(current):
            raise ValueError('Changing the rival would change the first-proof reservation')
        spare = [case for layout in layouts[:index] for case in layout['qualify'] if case not in retired][:reserve_size]
        allowed = set(backup) | set(spare)

        def grade(key, case):
            if case not in allowed or case in retired:
                raise ValueError('The proof left its independent allotted panel')
            return matrix[int(key)][case] == '1'

        proof = retry.scalar_proof(start, prompt, backup, spare, grade, nomination.grades, minimum,
                                   2 * (len(backup) + len(spare)))
        if proof.status not in ('promoted', 'rejected'):
            raise ValueError('The complete rival proof failed to settle')
        entry = Rival(prompt, gain, proof.status, len(proof.observations))
        options.append(entry)

    fixed = next(option for option in options if option.prompt == ranked)
    status = fixed.status if fixed.lookups <= remaining else 'undecided'
    deployed = fixed.prompt if status == 'promoted' else start
    if (status, deployed, min(fixed.lookups, remaining)) != (observed.status, observed.prompt, observed.retry_lookups):
        raise ValueError('A complete proof prefix failed to reproduce the published bounded retry')
    cause, chosen = summarize_rivals(options, unseen_gain, observed.retry_lookups, remaining)
    return cause, chosen, first_spend, starting_score, options


def measure(plan, data, reference):
    inputs, panels, _, _, cap = data
    schedule, policy = inputs['schedule'], inputs['qualificationBank']
    active = {**schedule, 'evaluationLookupLimit': cap}
    totals = Counter()
    controls = {method: Counter() for method in split.METHODS}
    reasons, traces, by_subject = Counter(), {}, {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        panel_trace, audit_trace = [], []
        subject_counts = by_subject.setdefault(subject, Counter())
        for seed in schedule['seeds']:
            start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
            nomination = RANKING.search_to_nomination(matrix, held, start, layouts, active, policy,
                                                     plan['fallbackValidationCap'])
            prior = split.outcomes(matrix, held, start, layouts, active, policy, nomination)
            for method, decision in prior.items():
                score = sum(matrix[int(decision.prompt)][case] == '1' for case in held)
                controls[method].update(holdoutPasses=score, paidLookups=nomination.paid_search + decision.lookups,
                                        proofLookups=decision.lookups, proofCapped=int(decision.status == 'undecided'),
                                        promotions=int(decision.prompt != start), retries=int(decision.retry),
                                        retryLookups=decision.retry_lookups,
                                        retryPromotions=int(decision.retry and decision.prompt != start))
            panel_trace.append((seed, tuple((item.prompt, item.lookups, item.status, item.retry) for item in prior.values())))
            observed = prior[split.FUTILITY]
            cost = nomination.paid_search + observed.lookups
            score = sum(matrix[int(observed.prompt)][case] == '1' for case in held)
            point = Counter(episodes=1)
            if observed.retry:
                cause, best, first_spend, starting_score, options = assess(matrix, held, start, layouts, active,
                                                                          nomination, observed)
                reasons[cause] += 1
                audit_trace.append((seed, cause, first_spend, [(x.prompt, x.gain, x.status, x.lookups) for x in options]))
                point.update(secondAttempts=1, positiveObservedPromotions=int(score > starting_score),
                             retentionOnlyAddedPasses=max(0, starting_score - score),
                             affordableRankChanges=int(best[LIMITS[0]].gain > max(0, score - starting_score)))
                for label, choice in best.items():
                    point.update({f'{label}HoldoutPasses': starting_score + choice.gain,
                                  f'{label}PaidLookups': nomination.paid_search + first_spend + choice.lookups})
            else:
                for label in LIMITS:
                    point.update({f'{label}HoldoutPasses': score, f'{label}PaidLookups': cost})
            subject_counts.update(point)
            totals.update(point)
        key = f'{subject}/{model}'
        if digest(panel_trace) != reference['panelTraceSha256'][key]:
            raise ValueError(f'The reserved proof trace changed on {key}')
        traces[key] = digest(audit_trace)
    if controls != reference['totals'] or sum(reasons.values()) != totals['secondAttempts']:
        raise ValueError('The original controls or audit episode partition changed')
    return {'totals': totals, 'controls': controls, 'reasons': reasons, 'bySubject': by_subject,
            'panelAuditSha256': traces}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, reference, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    report = {'plan': plan, 'planSha256': seal, 'newProviderRequests': 0, 'cohorts': {
        phase: measure(plan, data[phase], reference['cohorts'][phase]) for phase in RANKING.PHASES}}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
