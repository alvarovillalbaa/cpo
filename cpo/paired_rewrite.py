"""Select supplied rewrites with paired bounds on binary correctness."""

from functools import partial

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
    return select_same_parent_rewrites(incumbent, ((rewrite, minibatch_ids),), validation, evaluate,
                                       observed_charge=observed_charge)


def select_same_parent_rewrites(incumbent, proposals, validation, evaluate, *, observed_charge=None):
    """Select among ordered (rewrite, minibatch IDs) proposals from one parent.

    Each minibatch compares its proposal to the original incumbent. The
    full binary validation gate selects the best passing proposal in order,
    keeping the earlier prompt on a tie. All gates share one reply cache.
    """
    if observed_charge is not None and not callable(observed_charge):
        raise ValueError('Observed charge must be a callback')
    validation = tuple(validation)
    by_id = {row.id: row for row in validation}
    proposals = tuple((prompt, tuple(batch)) for prompt, batch in proposals)
    prompts = {prompt for prompt, _ in proposals}
    if not proposals or len(prompts) != len(proposals) or (len(prompts) > 1 and incumbent in prompts):
        raise ValueError('The same-parent search requires distinct supplied rewrites')
    if not validation or len(by_id) != len(validation) or any(
            not batch or len(set(batch)) != len(batch) or not set(batch) <= by_id.keys() for _, batch in proposals):
        raise ValueError('The minibatch must be a nonempty subset of distinct validation rows')
    if prompts == {incumbent}:
        return incumbent

    # The two gain gates use one family. The evaluator receives original rows.
    rows = {row.id: Row(row.id, 'validation') for row in validation}
    full = tuple(rows.values())
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

    def order_missing(leader, rewrite, missing):
        scores = {key: int(reply.passed) for key, reply in observations.items() if key[0] in (leader, rewrite)}
        pending = [(prompt, row.id, row) for prompt, row in missing]
        for prompt, case, row in by_observed_cost(pending, scores, leader, rewrite, 1, charges):
            yield prompt, row
            scores[prompt, case] = int(observations[prompt, case].passed)

    leader = incumbent
    for rewrite, batch in proposals:
        minibatch = tuple(rows[case] for case in batch)
        if (all(observe(incumbent, row).passed for row in minibatch)
                or not certify_opening_validation(incumbent, rewrite, minibatch, observations, observe)):
            continue
        order = partial(order_missing, leader, rewrite) if observed_charge is not None else None
        if certify_opening_validation(leader, rewrite, full, observations, observe, order_missing=order):
            leader = rewrite
    return leader
