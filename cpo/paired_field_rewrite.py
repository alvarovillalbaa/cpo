"""Bound the cached GEPA gates for one field-scored rewrite."""

from math import ulp
import sys

from ._paired_read_order import by_observed_cost, read_charge


def _separates_distinct_totals(size, denominator):
    if sys.implementation.name != 'cpython' or sys.version_info[:2] not in ((3, 11), (3, 12), (3, 13)):
        return False
    # Encoded scores are nonnegative and at most one. Leave room for both
    # sums, their compensation arithmetic, score rounding, and mean rounding.
    roundoff = 16 * size * ulp(4.0 * size)
    return roundoff < 1 / (denominator * size)


def _wins(incumbent, rewrite, cases, scores, observe, denominator, *, charges=None, full_order=None):
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

    pending = missing if charges is None else by_observed_cost(missing, scores, incumbent, rewrite, denominator, charges)
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
    order = cases if full_order is None else full_order
    after = sum(scores[rewrite, case] / denominator for case in order)
    if full_order is not None:
        return after / len(cases) > before / len(cases)
    return after > before


def _validated_field_score(reply, fields, weight):
    matched = reply.matched_fields
    if (type(reply.passed) is not bool or type(matched) is not int or not 0 <= matched <= fields
            or reply.passed != (matched == fields)):
        raise ValueError('The exact-pass flag and matched-field count must agree')
    return weight * reply.passed + matched


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
            score = _validated_field_score(reply, fields, weight)
            if observed_charge is not None:
                charges[key] = read_charge(observed_charge, prompt, rows[case], reply)
            scores[key] = score
        return scores[key]

    if all(observe(incumbent, case) == denominator for case in minibatch):
        return incumbent
    if not _wins(incumbent, rewrite, minibatch, scores, observe, denominator):
        return incumbent
    cached = set(minibatch)
    # Native GEPA builds the rewrite's validation vector from cached replies
    # first, followed by fresh replies, both in validation order.
    rewrite_order = tuple(sorted(rows, key=lambda case: case not in cached))
    priced = charges if observed_charge is not None else None
    return rewrite if _wins(incumbent, rewrite, tuple(rows), scores, observe, denominator,
                            charges=priced, full_order=rewrite_order) else incumbent
