"""Select a supplied rewrite with paired bounds on binary correctness."""

from ._paired_read_order import by_observed_cost, read_charge
from .opening_validation import certify_opening_validation
from .optimizer import Row


def select_paired_rewrite(incumbent, rewrite, validation, minibatch_ids, evaluate, *, observed_charge=None):
    """Require strict gain on the supplied minibatch and on all validation.

    The two gates share a paid-reply cache. This selector compares binary
    totals. Independent admission can enforce task-specific safety criteria.

    Pass `observed_charge(prompt, row, observation)` to prioritize remaining
    full-validation reads by observed gain per charge. Return a nonnegative
    integer in a consistent unit, or None if unavailable. Missing or zero
    cumulative charges use observed gain per read. The callback runs after
    each actual evaluation. Omitting it uses row-paired order.
    """
    if observed_charge is not None and not callable(observed_charge):
        raise ValueError('Observed charge must be a callback')
    validation = tuple(validation)
    by_id = {row.id: row for row in validation}
    minibatch_ids = tuple(minibatch_ids)
    if (not validation or len(by_id) != len(validation) or not minibatch_ids
            or len(set(minibatch_ids)) != len(minibatch_ids) or not set(minibatch_ids) <= by_id.keys()):
        raise ValueError('The minibatch must be a nonempty subset of distinct validation rows')
    if incumbent == rewrite:
        return incumbent

    # The two gain gates use one family. The evaluator receives original rows.
    rows = {row.id: Row(row.id, 'validation') for row in validation}
    minibatch = tuple(rows[case] for case in minibatch_ids)
    observations, charges = {}, {}

    def observe(prompt, row):
        key = prompt, row.id
        if key not in observations:
            reply = evaluate(prompt, by_id[row.id])
            if type(reply.passed) is not bool:
                raise ValueError('Paired rewrite selection requires binary pass results')
            if observed_charge is not None:
                charges[key] = read_charge(observed_charge, prompt, by_id[row.id], reply)
            observations[key] = reply
        return observations[key]

    if all(observe(incumbent, row).passed for row in minibatch):
        return incumbent
    if not certify_opening_validation(incumbent, rewrite, minibatch, observations, observe):
        return incumbent
    def order_missing(missing):
        scores = {key: int(reply.passed) for key, reply in observations.items()}
        pending = [(prompt, row.id, row) for prompt, row in missing]
        for prompt, case, row in by_observed_cost(pending, scores, incumbent, rewrite, 1, charges):
            yield prompt, row
            scores[prompt, case] = int(observations[prompt, case].passed)

    order = order_missing if observed_charge is not None else None
    if certify_opening_validation(incumbent, rewrite, tuple(rows.values()), observations, observe, order_missing=order):
        return rewrite
    return incumbent
