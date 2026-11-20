"""Select an exactly scored prompt with declared critical coverage."""

from .coverage_confirmation import confirm_covered_gain
from .pool import PoolResult


def select_covered_pool(candidates, validation, evaluate, *, metric_limit, critical_strata):
    """Race a fixed pool in caller order and preserve the incumbent's critical passes.

    The first prompt is the incumbent. Supply exactly one hashable stratum
    label per critical validation row, keyed by row ID. A challenger needs a
    strict exact-score gain and one passing row in each represented stratum.
    The evaluator returns an Observation, with each callback counted as one
    lookup. The budget must cover a full confirmation before one starts.
    """
    candidates, validation = tuple(candidates), tuple(validation)
    if not candidates or len(set(candidates)) != len(candidates):
        raise ValueError('Pool requires distinct candidates and an incumbent')
    rows = {row.id: row for row in validation}
    if not rows or len(rows) != len(validation):
        raise ValueError('Validation requires distinct, nonempty rows')
    if type(metric_limit) is not int or metric_limit < len(rows):
        raise ValueError('The budget must cover the incumbent')
    critical = {row.id for row in validation if row.critical}
    strata = dict(critical_strata)
    if strata.keys() != critical:
        raise ValueError('Supply a stratum for each critical validation row only')
    for group in strata.values():
        hash(group)

    evaluations = 0

    def observe(prompt, row_id):
        nonlocal evaluations
        passed = evaluate(prompt, rows[row_id]).passed
        if type(passed) is not bool:
            raise ValueError('Pool observations require an exact boolean outcome')
        evaluations += 1
        return passed

    incumbent, *challengers = candidates
    baseline = {row_id: observe(incumbent, row_id) for row_id in rows}
    protected = {row_id for row_id in critical if baseline[row_id]}
    winner, score = incumbent, sum(baseline.values())
    for prompt in challengers:
        if score == len(rows) or evaluations + len(rows) > metric_limit:
            break
        measured = confirm_covered_gain(
            baseline, score, protected, strata, {}, lambda row_id: observe(prompt, row_id),
        )
        if measured is not None:
            winner, score = prompt, measured
    return PoolResult(winner, score, evaluations)
