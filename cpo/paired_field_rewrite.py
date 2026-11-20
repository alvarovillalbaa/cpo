"""Bound the cached GEPA gates for one field-scored rewrite."""

from collections import deque
from math import ulp
import sys


def _separates_distinct_totals(size, denominator):
    if sys.implementation.name != 'cpython' or sys.version_info[:2] not in ((3, 11), (3, 12), (3, 13)):
        return False
    # Encoded scores are nonnegative and at most one. Leave room for both
    # sums, their compensation arithmetic, score rounding, and mean rounding.
    roundoff = 16 * size * ulp(4.0 * size)
    return roundoff < 1 / (denominator * size)


def _by_observed_cost(missing, scores, incumbent, rewrite, denominator, charges):
    pending = {prompt: deque((index, item) for index, item in enumerate(missing) if item[0] == prompt)
               for prompt in (incumbent, rewrite)}
    while pending[incumbent] and pending[rewrite]:
        old = [denominator - score for (prompt, _), score in scores.items() if prompt == incumbent]
        new = [score for (prompt, _), score in scores.items() if prompt == rewrite]
        old_weight, new_weight = len(old), len(new)
        if all(charge is not None for charge in charges.values()):
            old_cost, new_cost = (sum(fee for (owner, _), fee in charges.items() if owner == prompt)
                                  for prompt in (incumbent, rewrite))
            if old_cost and new_cost:
                old_weight, new_weight = old_cost, new_cost

        # Compare the observed gain per unit without floating-point rounding.
        old_lift, new_lift = sum(old) * new_weight, sum(new) * old_weight
        if old_lift == new_lift:
            prompt = min(pending, key=lambda choice: pending[choice][0][0])
        else:
            prompt = rewrite if new_lift > old_lift else incumbent
        yield pending[prompt].popleft()[1]
    for queue in pending.values():
        yield from (item for _, item in queue)


def select_paired_field_rewrite(incumbent, rewrite, validation, minibatch_ids, evaluate, *, observed_charge=None):
    """Certify the strict minibatch and full-validation gates on uniform fields.

    Scores match the fixed-rewrite GEPA 0.1.4 adapter. A decision involving a
    possible integer tie uses its native float comparison in the native order.
    This is nomination only. The caller can run independent admission.

    Pass an optional `observed_charge(prompt, row, observation)` returning a
    nonnegative integer in a consistent unit, or None when unavailable. It
    runs after each actual evaluation and ranks remaining full-validation reads
    by observed gain per charge. Missing or zero cumulative charges use the
    observed gain per read. Omitting the callback uses row-paired order.
    """
    if observed_charge is not None and not callable(observed_charge):
        raise ValueError('Observed charge must be a callback')
    validation, minibatch = tuple(validation), tuple(minibatch_ids)
    rows = {row.id: row for row in validation}
    if (not validation or len(rows) != len(validation) or not minibatch
            or len(set(minibatch)) != len(minibatch) or not set(minibatch) <= rows.keys()):
        raise ValueError('The minibatch must be a nonempty subset of distinct validation rows')
    fields = validation[0].fields
    if type(fields) is not int or fields <= 0 or any(
            type(row.fields) is not int or row.fields != fields for row in validation):
        raise ValueError('Paired field scoring requires a uniform positive field count')
    if incumbent == rewrite:
        return incumbent

    weight = 1 << (len(validation) * fields).bit_length()
    denominator = weight + fields
    scores, charges = {}, {}

    def observe(prompt, case):
        key = prompt, case
        if key not in scores:
            reply = evaluate(prompt, rows[case])
            matched = reply.matched_fields
            if (type(reply.passed) is not bool or type(matched) is not int or not 0 <= matched <= fields
                    or reply.passed != (matched == fields)):
                raise ValueError('The exact-pass flag and matched-field count must agree')
            if observed_charge is not None:
                fee = observed_charge(prompt, rows[case], reply)
                if fee is not None and (type(fee) is not int or fee < 0):
                    raise ValueError('Observed charges must be nonnegative integers or None')
                charges[key] = fee
            scores[key] = weight * reply.passed + matched
        return scores[key]

    def wins(cases, rewrite_order=None):
        lower = upper = 0
        missing = []
        for case in cases:
            for prompt, sign in ((incumbent, -1), (rewrite, 1)):
                value = scores.get((prompt, case))
                if value is None:
                    missing.append((prompt, case, sign))
                    lower += min(0, sign * denominator)
                    upper += max(0, sign * denominator)
                else:
                    lower += sign * value
                    upper += sign * value

        pending = missing
        if rewrite_order is not None and observed_charge is not None:
            pending = _by_observed_cost(missing, scores, incumbent, rewrite, denominator, charges)
        bounded = _separates_distinct_totals(len(cases), denominator)
        for prompt, case, sign in pending:
            if bounded and lower > 0:
                return True
            if bounded and upper < 0:
                return False
            score = sign * observe(prompt, case)
            lower += score - min(0, sign * denominator)
            upper += score - max(0, sign * denominator)

        before = sum(scores[incumbent, case] / denominator for case in cases)
        order = cases if rewrite_order is None else rewrite_order
        after = sum(scores[rewrite, case] / denominator for case in order)
        if rewrite_order is not None:
            return after / len(cases) > before / len(cases)
        return after > before

    if all(observe(incumbent, case) == denominator for case in minibatch):
        return incumbent
    if not wins(minibatch):
        return incumbent
    cached = set(minibatch)
    # Native GEPA builds the rewrite's validation vector from cached replies
    # first, followed by fresh replies, both in validation order.
    rewrite_order = tuple(sorted(rows, key=lambda case: case not in cached))
    return rewrite if wins(tuple(rows), rewrite_order) else incumbent
