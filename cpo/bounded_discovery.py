"""Screen a fixed prompt pool with a bounded search for incumbent misses."""

from collections import Counter

from .challenger import certify_challenger
from .single_finalist import FinalistResult


def select_with_bounded_discovery(incumbent, candidates, validation, evaluate, *, metric_limit,
                                  discovery_limit=2, shared_prefix=1, audit=None):
    """Screen each prompt once, rotating only among cheaply discovered misses.

    The discovery limit caps extra incumbent reads during screening. A
    finalist can still use the reserved full incumbent panel and its exact
    certificate. Supply an optional Counter to accumulate screening counts.
    """
    rows, candidates = tuple(validation), tuple(candidates)
    row_count = len(rows)
    if not rows or len({row.id for row in rows}) != row_count:
        raise ValueError('The validation panel must be nonempty and have distinct cases')
    if incumbent in candidates or len(set(candidates)) != len(candidates):
        raise ValueError('The challenger pool must be distinct from the incumbent')
    if type(metric_limit) is not int or metric_limit < row_count:
        raise ValueError('The evaluation cap must fund the incumbent')
    if type(discovery_limit) is not int or discovery_limit < 0 or type(shared_prefix) is not int or shared_prefix < 1:
        raise ValueError('Use a nonnegative discovery limit and a positive shared prefix')
    finalist_reserve = row_count - 1
    slots = max(0, metric_limit - row_count - finalist_reserve)
    if not candidates or not slots:
        return FinalistResult(incumbent, None, 0)

    remaining = iter(rows)
    misses, baseline = [], {}
    spent = 0

    def observe(prompt, row):
        nonlocal spent
        reply = evaluate(prompt, row)
        if type(reply.passed) is not bool:
            raise ValueError('Validation requires exact boolean outcomes')
        spent += 1
        return reply

    def incumbent_read(row):
        baseline[row.id] = observe(incumbent, row).passed
        if not baseline[row.id]:
            misses.append(row)

    for row in remaining:
        incumbent_read(row)
        if misses:
            break
    if not misses:
        return FinalistResult(incumbent, None, spent)

    if audit is None:
        audit = Counter()
    before_discovery = len(baseline)
    audit['cyclesWithMisses'] += 1
    for index, prompt in enumerate(candidates[:slots]):
        desired = max(0, index - shared_prefix + 1)
        while desired >= len(misses) and len(baseline) - before_discovery < discovery_limit:
            row = next(remaining, None)
            if row is None:
                break
            incumbent_read(row)
        witness = misses[desired % len(misses)]
        audit['gainProbes'] += 1
        if witness != misses[0]:
            audit['probesOnOtherMisses'] += 1
        if observe(prompt, witness).passed:
            audit['extraIncumbentScreenReads'] += len(baseline) - before_discovery
            for row in remaining:
                incumbent_read(row)
            order = sorted(rows, key=lambda row: baseline[row.id])
            result = certify_challenger(order, baseline, lambda row: observe(prompt, row),
                                        metric_limit=metric_limit - spent, observed={witness.id: True})
            audit['certificate.' + result.status] += 1
            return FinalistResult(prompt if result.status == 'promote' else incumbent, prompt, spent)
    audit['extraIncumbentScreenReads'] += len(baseline) - before_discovery
    audit['noNominee'] += 1
    return FinalistResult(incumbent, None, spent)
