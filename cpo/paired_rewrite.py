"""Select a supplied rewrite with paired bounds on binary correctness."""

from .opening_validation import certify_opening_validation
from .optimizer import Row


def select_paired_rewrite(incumbent, rewrite, validation, minibatch_ids, evaluate):
    """Require strict gain on the supplied minibatch and on all validation.

    The two gates share a paid-reply cache. This selector compares binary
    totals. Independent admission can enforce task-specific safety criteria.
    """
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
    observations = {}

    def observe(prompt, row):
        key = prompt, row.id
        if key not in observations:
            reply = evaluate(prompt, by_id[row.id])
            if type(reply.passed) is not bool:
                raise ValueError('Paired rewrite selection requires binary pass results')
            observations[key] = reply
        return observations[key]

    if all(observe(incumbent, row).passed for row in minibatch):
        return incumbent
    if not certify_opening_validation(incumbent, rewrite, minibatch, observations, observe):
        return incumbent
    if certify_opening_validation(incumbent, rewrite, tuple(rows.values()), observations, observe):
        return rewrite
    return incumbent
