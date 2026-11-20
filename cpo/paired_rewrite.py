"""Select supplied rewrites with paired bounds on binary correctness."""

from functools import partial

from ._paired_read_order import by_observed_cost, read_charge
from .opening_validation import certify_opening_validation
from .optimizer import Row


class _BinaryReplies:
    def __init__(self, validation, evaluate, observed_charge):
        if observed_charge is not None and not callable(observed_charge):
            raise ValueError('Observed charge must be a callback')
        validation = tuple(validation)
        self.by_id = {row.id: row for row in validation}
        if not validation or len(self.by_id) != len(validation):
            raise ValueError('Binary rewrite selection requires distinct validation rows')
        # Binary gain gates use one family. The evaluator receives original rows.
        self.rows = {row.id: Row(row.id, 'validation') for row in validation}
        self.full = tuple(self.rows.values())
        self.evaluate = evaluate
        self.observed_charge = observed_charge
        self.observations, self.charges = {}, {}

    def batch(self, ids):
        ids = tuple(ids)
        if not ids or len(set(ids)) != len(ids) or not set(ids) <= self.rows.keys():
            raise ValueError('The minibatch must be a nonempty subset of distinct validation rows')
        return tuple(self.rows[case] for case in ids)

    def observe(self, prompt, row):
        key = prompt, row.id
        if key not in self.observations:
            original = self.by_id[row.id]
            reply = self.evaluate(prompt, original)
            if type(reply.passed) is not bool:
                raise ValueError('Paired rewrite selection requires binary pass results')
            if self.observed_charge is not None:
                self.charges[key] = read_charge(self.observed_charge, prompt, original, reply)
            self.observations[key] = reply
        return self.observations[key]

    def improves_batch(self, parent, rewrite, batch):
        return certify_opening_validation(parent, rewrite, batch, self.observations, self.observe)

    def _order_missing(self, leader, rewrite, missing):
        scores = {key: int(reply.passed) for key, reply in self.observations.items() if key[0] in (leader, rewrite)}
        pending = [(prompt, row.id, row) for prompt, row in missing]
        for prompt, case, row in by_observed_cost(pending, scores, leader, rewrite, 1, self.charges):
            yield prompt, row
            scores[prompt, case] = int(self.observations[prompt, case].passed)

    def improves_full(self, leader, rewrite):
        order = partial(self._order_missing, leader, rewrite) if self.observed_charge is not None else None
        return certify_opening_validation(leader, rewrite, self.full, self.observations, self.observe,
                                          order_missing=order)

    def perfect(self, prompt):
        if any(owner == prompt and not reply.passed for (owner, _), reply in self.observations.items()):
            return False
        return all(self.observe(prompt, row).passed for row in self.full)


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
    replies = _BinaryReplies(validation, evaluate, observed_charge)
    proposals = tuple((prompt, replies.batch(batch)) for prompt, batch in proposals)
    prompts = {prompt for prompt, _ in proposals}
    if not proposals or len(prompts) != len(proposals) or (len(prompts) > 1 and incumbent in prompts):
        raise ValueError('The same-parent search requires distinct supplied rewrites')
    if prompts == {incumbent}:
        return incumbent

    leader = incumbent
    for rewrite, batch in proposals:
        if (all(replies.observe(incumbent, row).passed for row in batch)
                or not replies.improves_batch(incumbent, rewrite, batch)):
            continue
        if replies.improves_full(leader, rewrite):
            leader = rewrite
    return leader


def select_sequential_rewrites(incumbent, validation, evaluate, schedule, propose, *, rounds, observed_charge=None):
    """Select rewrites sequentially, with optional full grades for parent selection.

    schedule(round_index, pool, grades) returns a tracked parent and its
    minibatch IDs. grades(prompt) pays for any missing validation grades for
    a tracked prompt, in validation order. A minibatch improvement enrolls
    the rewrite in the pool even if it has a lower full score than the incumbent.
    propose(round_index, parent, examples) gets the original rows and paid
    parent observations on its minibatch. A perfect minibatch skips the round.
    The best full-validation score wins, keeping the earlier prompt on ties.
    """
    if type(rounds) is not int or rounds < 0:
        raise ValueError('Sequential rewrite rounds must be a nonnegative integer')
    replies = _BinaryReplies(validation, evaluate, observed_charge)
    pool = [incumbent]
    if rounds == 0 or replies.perfect(incumbent):
        return incumbent

    def grades(prompt):
        if prompt not in pool:
            raise ValueError('Full grades are available only for tracked prompts')
        return tuple(replies.observe(prompt, row).passed for row in replies.full)

    for index in range(rounds):
        parent, ids = schedule(index, tuple(pool), grades)
        if parent not in pool:
            raise ValueError('The rewrite parent must be tracked')
        batch = replies.batch(ids)
        examples = tuple((replies.by_id[row.id], replies.observe(parent, row)) for row in batch)
        if all(reply.passed for _, reply in examples):
            continue
        rewrite = propose(index, parent, examples)
        if rewrite in pool or not replies.improves_batch(parent, rewrite, batch):
            continue
        pool.append(rewrite)
        if index + 1 < rounds and replies.perfect(rewrite):
            return rewrite

    leader = incumbent
    for rewrite in pool[1:]:
        if replies.improves_full(leader, rewrite):
            leader = rewrite
    return leader
