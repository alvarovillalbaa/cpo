"""Preserve batched field-scored rewrite choices with bounded validation reads."""

from ._paired_read_order import read_charge
from .paired_field_rewrite import _validated_field_score, _wins
from .sequential_field_rewrite import SequentialValidationGrades


def select_batched_field_rewrites(
    incumbent, training, validation, evaluate, schedule, propose, *,
    rounds, width, minibatch_size, metric_limit, observed_charge=None,
):
    """Run fixed-width, same-parent rounds under the full-read GEPA horizon.

    The schedule receives the ordered candidate pool and its paid validation
    grades. It returns one parent and one training minibatch per proposal.
    Padded minibatches can repeat an observation without evaluating it twice.
    The proposer receives its slot, that parent, and its ordered observations.
    The selector keeps all strict minibatch improvements, deduplicating
    within each round in proposal order. Independent admission is separate.
    """
    training, validation = tuple(training), tuple(validation)
    train_ids = {row.id for row in training}
    val_ids = tuple(row.id for row in validation)
    by_id = {row.id: row for row in (*training, *validation)}
    if not training or not validation or len(by_id) != len(training) + len(validation):
        raise ValueError('Training and validation require distinct, disjoint case IDs')
    fields = validation[0].fields
    if type(fields) is not int or fields <= 0 or any(
            type(row.fields) is not int or row.fields != fields for row in by_id.values()):
        raise ValueError('Batched field scoring requires a uniform positive field count')
    if (type(rounds) is not int or rounds < 0 or type(width) is not int or width < 2
            or type(minibatch_size) is not int or not 1 <= minibatch_size <= len(training)
            or type(metric_limit) is not int or metric_limit < len(validation)):
        raise ValueError('The search budget must cover valid rounds and incumbent validation')
    if observed_charge is not None and not callable(observed_charge):
        raise ValueError('Observed charge must be a callback')

    weight = 1 << (max(len(training), len(validation)) * fields).bit_length()
    denominator = weight + fields
    scores, replies, charges = {}, {}, {}
    accounted = {(incumbent, case) for case in val_ids}
    pool = [incumbent]
    newest = (incumbent,)
    round_reserve = width * (2 * minibatch_size + len(val_ids))

    def observe(prompt, case):
        key = prompt, case
        if key not in scores:
            if key not in accounted or len(scores) >= metric_limit:
                raise ValueError('A field read exceeded the batched search scope')
            row = by_id[case]
            reply = evaluate(prompt, row)
            scores[key] = _validated_field_score(reply, fields, weight)
            replies[key] = reply
            if observed_charge is not None:
                charges[key] = read_charge(observed_charge, prompt, row, reply)
        return scores[key]

    def complete(prompt):
        return tuple(read(prompt, index) for index in range(len(val_ids)))

    def peek(prompt, index):
        score = scores.get((prompt, val_ids[index]))
        return None if score is None else score / denominator

    def read(prompt, index):
        if prompt not in pool:
            raise ValueError('Validation grades are available only for tracked prompts')
        return observe(prompt, val_ids[index]) / denominator

    grades = SequentialValidationGrades(complete, peek, read)

    def perfect(prompt):
        return (all(scores.get((prompt, case), denominator) == denominator for case in val_ids)
                and all(observe(prompt, case) == denominator for case in val_ids))

    for index in range(rounds):
        if len(accounted) + round_reserve > metric_limit:
            break
        if any(perfect(prompt) for prompt in newest):
            break
        parent, sampled = schedule(index, tuple(pool), grades)
        batches = tuple(tuple(batch) for batch in sampled)
        if parent not in pool or len(batches) != width or any(
                len(batch) != minibatch_size or not train_ids.issuperset(batch) for batch in batches):
            raise ValueError('The schedule must supply one tracked parent and valid training minibatches')
        feedback = []
        for batch in batches:
            accounted.update((parent, case) for case in batch)
            for case in batch:
                observe(parent, case)
            feedback.append(tuple((by_id[case], replies[parent, case]) for case in batch))
        children = tuple(propose(index * width + slot, parent, examples) for slot, examples in enumerate(feedback))
        accepted = {}
        for child, batch in zip(children, batches, strict=True):
            accounted.update((child, case) for case in batch)
            if child != parent and _wins(parent, child, batch, scores, observe, denominator):
                accepted[child] = None
        newest = tuple(accepted)
        pool.extend(newest)
        accounted.update((child, case) for child in newest for case in val_ids)

    leader = incumbent
    for child in dict.fromkeys(pool[1:]):
        if child != leader and _wins(leader, child, val_ids, scores, observe, denominator,
                                     charges=charges if observed_charge is not None else None, full_order=val_ids):
            leader = child
    return leader
