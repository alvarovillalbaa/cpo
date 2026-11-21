"""Stop an exact four-anchor race once the winning identity is settled."""

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import witness_funded_anchor_challenge as prior, witness_matched_anchors as matched
from cpo._contract import digest


ROOT, RANKING, retry, FULL = prior.ROOT, prior.RANKING, prior.retry, prior.FULL
reference_runner = matched.previous
REFERENCE = 'docs/witness-funded-anchor-challenge-results-v1.json'
REFERENCE_SHA256 = '74614fd60cc0be43dcb7fc125e247898c6b07e5b51b64f070d8951cda09acb41'
BOUNDS = 'four-anchor-score-bounds'
METHODS = (retry.BASE, FULL, matched.BEST, BOUNDS)


@dataclass(frozen=True)
class Race:
    prompt: str
    reads: int
    settled: bool
    incomplete_winner: bool


def prepare():
    parent, matched_reference, native, data = prior.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('Use the published matched race and funded challenge evidence')
    plan = {key: parent[key] for key in ('fallbackValidationCap', 'pairedCaseDraws', 'resamplingSeed', 'proofCap', 'anchors')}
    plan.update(protocol='witness-anchor-bounds-v1', parentPlanSha256=digest(parent),
                parentReceiptSha256=REFERENCE_SHA256, sourceSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                methods=METHODS, primary=BOUNDS,
                rule='Use the same four seeded anchors, proposal order for ties, exact incumbent score, and cap. '
                'Track possible score intervals, read a candidate with the highest projected score among those '
                'still in contention, and order that candidate’s reads by paid case pass rate. Stop when no '
                'other candidate can beat the known leader. At cap, keep the highest proved score.',
                gate='Require a positive paired lower endpoint against the original expected-read first proof '
                'under the seeded total cost on every cohort. Replay the earlier four-anchor best-score control.')
    return plan, matched_reference, native, data


def race(candidates, anchors, evaluate, cap):
    """Return the earliest provable leader and whether its identity is exact."""
    width = len(anchors)
    if not candidates or len(set(candidates)) != len(candidates) or not width or len(set(anchors)) != width:
        raise ValueError('Use distinct candidates and anchor cases')
    if type(cap) is not int or cap < 0:
        raise ValueError('Use a nonnegative lookup cap')
    if cap < width:
        return Race(candidates[0], 0, False, True)

    pending = [list(anchors) for _ in candidates]
    lower = [0] * len(candidates)
    pass_counts, read_counts = [0] * width, [0] * width
    indices = {case: i for i, case in enumerate(anchors)}
    spent = 0

    def read(prompt, case):
        nonlocal spent
        result = evaluate(candidates[prompt], case)
        if type(result) is not bool:
            raise ValueError('A four-anchor race requires exact boolean grades')
        row = indices[case]
        pending[prompt].remove(case)
        pass_counts[row] += result
        read_counts[row] += 1
        lower[prompt] += result
        spent += 1

    for case in anchors:
        read(0, case)
    while True:
        leader = max(range(len(candidates)), key=lambda i: (lower[i], -i))
        best = lower[leader], -leader
        rivals = [i for i, unread in enumerate(pending) if i != leader and (lower[i] + len(unread), -i) > best]
        if not rivals or spent == cap:
            return Race(candidates[leader], spent, not rivals, bool(pending[leader]))
        active = [*rivals, leader] if pending[leader] else rivals
        rates = {case: (pass_counts[row] + 1) / (read_counts[row] + 2) for case, row in indices.items()}
        selected = max(active, key=lambda i: (lower[i] + sum(rates[case] for case in pending[i]), -i))
        pick = max if selected == leader else min
        read(selected, pick(pending[selected], key=rates.__getitem__))


def nominate(matrix, held, start, layouts, active, policy, cap, method, activity):
    if method == matched.BEST:
        return matched.nominate(matrix, held, start, layouts, active, policy, cap, method, activity)

    def screen(incumbent, layout, observe, limits):
        anchors = list(layout['validation'])
        Random(layout['seed']).shuffle(anchors)
        receipt = race((incumbent, *layout['alternatives']), anchors[:matched.WIDTH], observe,
                       limits['evaluationLookupLimit'])
        activity.update(anchorCycles=1, anchorLookups=receipt.reads, anchorNominees=int(receipt.prompt != incumbent),
                        settledWinners=int(receipt.settled), cappedSearches=int(not receipt.settled),
                        settledWithUnreadWinnerGrades=int(receipt.settled and receipt.incomplete_winner))
        return receipt.prompt

    with patch.object(reference_runner.WITNESS, 'witness', screen):
        return RANKING.search_to_nomination(matrix, held, start, layouts, active, policy, cap)


def measure(plan, phase, data, reference, native):
    original_ranges = RANKING.paired_bands.paired_ranges
    versus_best = {}

    def paired(groups, method, active):
        compared = original_ranges(groups, method, active)
        if method == BOUNDS:
            with patch.object(RANKING.paired_bands, 'BASELINE', matched.BEST):
                versus_best.update(original_ranges(groups, method, active)['subjectsAndCases'])
        return compared

    with (patch.multiple(reference_runner, PREFIX=matched.BEST, CACHE=BOUNDS, METHODS=METHODS, nominate=nominate),
          patch.object(RANKING.paired_bands, 'paired_ranges', paired)):
        report = reference_runner.measure(plan, data[phase], reference, native)
    if (report['totals'][matched.BEST] != reference['totals'][matched.BEST]
            or report['activity'][matched.BEST] != reference['activity'][matched.BEST]
            or report['pairedVsOriginal'][matched.BEST] != reference['pairedVsOriginal'][matched.BEST]):
        raise ValueError('The published four-anchor best-score control changed')
    return {**report, 'pairedVsFourAnchorBest': versus_best}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, reference, native, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    cohorts = {phase: measure(plan, phase, data, reference['cohorts'][phase], native['cohorts'][phase])
               for phase in RANKING.PHASES}
    report = {'plan': plan, 'planSha256': seal, 'newProviderRequests': 0, 'cohorts': cohorts,
              'qualifies': all(row['qualifies'] for row in cohorts.values())}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
