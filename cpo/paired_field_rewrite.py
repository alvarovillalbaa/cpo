"""Bound the cached GEPA gates for one field-scored rewrite."""

from math import ulp
import sys


def _separates_distinct_totals(size, denominator):
    if sys.implementation.name != 'cpython' or sys.version_info[:2] not in ((3, 11), (3, 12), (3, 13)):
        return False
    # Encoded scores are nonnegative and at most one. Leave room for both
    # sums, their compensation arithmetic, score rounding, and mean rounding.
    roundoff = 16 * size * ulp(4.0 * size)
    return roundoff < 1 / (denominator * size)


def select_paired_field_rewrite(incumbent, rewrite, validation, minibatch_ids, evaluate):
    """Certify the strict minibatch and full-validation gates on uniform fields.

    Scores match the fixed-rewrite GEPA 0.1.4 adapter. A decision involving a
    possible integer tie uses its native float comparison in the native order.
    This is nomination only. The caller can run independent admission.
    """
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
    scores = {}

    def observe(prompt, case):
        key = prompt, case
        if key not in scores:
            reply = evaluate(prompt, rows[case])
            matched = reply.matched_fields
            if (type(reply.passed) is not bool or type(matched) is not int or not 0 <= matched <= fields
                    or reply.passed != (matched == fields)):
                raise ValueError('The exact-pass flag and matched-field count must agree')
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

        bounded = _separates_distinct_totals(len(cases), denominator)
        for prompt, case, sign in missing:
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
