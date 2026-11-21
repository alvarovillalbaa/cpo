"""Preserve batched field-scored rewrite choices with bounded validation reads."""

from ._paired_read_order import read_charge
from .paired_field_rewrite import _validated_field_score, _wins
from .sequential_field_rewrite import SequentialSearchBudget, SequentialValidationGrades, _check_charge


def select_batched_field_rewrites(
    incumbent, training, validation, evaluate, schedule, propose, *,
    rounds, width, minibatch_size, metric_limit, observed_charge=None, price_budget=None,
):
    """Run fixed-width, same-parent rounds under the full-read GEPA horizon.

    The schedule receives the ordered candidate pool and its paid validation
    grades. It returns one parent and one training minibatch per proposal.
    Padded minibatches can repeat an observation without evaluating it twice.
    The proposer receives its slot, that parent, and its ordered observations.
    The selector keeps all strict minibatch improvements, deduplicating
    within each round in proposal order. Independent admission is separate.

    An optional price budget reserves every outstanding validation reply,
    the next batch's possible evaluation calls and all its proposal quotes
    before proposing. Evaluators and proposers enforce their upper quotes.
    A separate proposal limit must cover every proposal in an entered batch.
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
    if price_budget is not None and (not isinstance(price_budget, SequentialSearchBudget) or observed_charge is None):
        raise ValueError('A batched price budget requires observed evaluation charges')

    weight = 1 << (max(len(training), len(validation)) * fields).bit_length()
    denominator = weight + fields
    scores, replies, charges = {}, {}, {}
    validation_reserve = {(incumbent, case) for case in val_ids}
    accounted = set(validation_reserve)
    pool = [incumbent]
    newest = (incumbent,)
    round_reserve = width * (2 * minibatch_size + len(val_ids))
    settled_charge = settled_proposal_charge = 0
    if price_budget is not None and price_budget.evaluation_quote * len(val_ids) > price_budget.limit:
        return incumbent

    def observe(prompt, case):
        nonlocal settled_charge
        key = prompt, case
        if key not in scores:
            if key not in accounted or len(scores) >= metric_limit:
                raise ValueError('A field read exceeded the batched search scope')
            if price_budget is not None and settled_charge + price_budget.evaluation_quote > price_budget.limit:
                raise ValueError('An evaluation has no remaining price reserve')
            row = by_id[case]
            reply = evaluate(prompt, row)
            scores[key] = _validated_field_score(reply, fields, weight)
            replies[key] = reply
            if observed_charge is not None:
                charges[key] = read_charge(observed_charge, prompt, row, reply)
                if price_budget is not None:
                    _check_charge(charges[key], price_budget.evaluation_quote)
                    settled_charge += charges[key]
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
        slots = range(index * width, (index + 1) * width)
        if price_budget is not None:
            quotes = tuple(price_budget.proposal_quote(slot, parent) for slot in slots)
            if any(type(quote) is not int or quote < 0 for quote in quotes):
                raise ValueError('A proposal needs a nonnegative integer price quote')
            parent_reads = {(parent, case) for batch in batches for case in batch} - scores.keys()
            reserved_reads = len(validation_reserve - scores.keys()) + len(parent_reads)
            reserved_reads += width * (minibatch_size + len(val_ids))
            proposal_charge = sum(quotes)
            proposal_limit = price_budget.proposal_limit
            required = reserved_reads * price_budget.evaluation_quote + proposal_charge
            if (settled_charge + required > price_budget.limit or
                    (proposal_limit is not None and settled_proposal_charge + proposal_charge > proposal_limit)):
                break
        feedback = []
        for batch in batches:
            accounted.update((parent, case) for case in batch)
            for case in batch:
                observe(parent, case)
            feedback.append(tuple((by_id[case], replies[parent, case]) for case in batch))
        children = []
        for offset, (slot, examples) in enumerate(zip(slots, feedback, strict=True)):
            child = propose(slot, parent, examples)
            if price_budget is not None:
                charge = price_budget.observed_proposal(slot, parent, child)
                _check_charge(charge, quotes[offset])
                settled_charge += charge
                settled_proposal_charge += charge
            children.append(child)
        accepted = {}
        for child, batch in zip(children, batches, strict=True):
            accounted.update((child, case) for case in batch)
            if child != parent and _wins(parent, child, batch, scores, observe, denominator):
                accepted[child] = None
        newest = tuple(accepted)
        pool.extend(newest)
        new_reserve = {(child, case) for child in newest for case in val_ids}
        validation_reserve.update(new_reserve)
        accounted.update(new_reserve)

    leader = incumbent
    for child in dict.fromkeys(pool[1:]):
        if child != leader and _wins(leader, child, val_ids, scores, observe, denominator,
                                     charges=charges if observed_charge is not None else None, full_order=val_ids):
            leader = child
    return leader
