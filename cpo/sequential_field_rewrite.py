"""Select sequential typed rewrites using paired bounds and disjoint feedback."""

from ._paired_read_order import read_charge
from .paired_field_rewrite import _validated_field_score, _wins


def select_sequential_field_rewrites(
    incumbent, training, validation, evaluate, schedule, propose, *,
    rounds, minibatch_size, metric_limit, observed_charge=None, reinvest_savings=False,
):
    """Match sequential GEPA's field gates, full-round reserve and score order.

    schedule(index, pool, grades) returns a tracked parent and training IDs.
    grades(prompt) returns that prompt's complete normalized validation scores
    in validation order, paying for any missing replies. The proposer receives
    (index, parent, examples), with only paid training rows and observations.
    It runs for every entered round so stateful proposal sequences stay intact.

    With reinvest_savings, budget charged reads and still-unread validation
    reserved for every tracked prompt. Once the scheduler picks a parent,
    reserve only its missing minibatch reads alongside a full new child.
    """
    training, validation = tuple(training), tuple(validation)
    train_ids, val_ids = tuple(row.id for row in training), tuple(row.id for row in validation)
    by_id = {row.id: row for row in (*training, *validation)}
    if not training or not validation or len(by_id) != len(train_ids) + len(val_ids):
        raise ValueError('Training and validation require distinct, disjoint case IDs')
    fields = validation[0].fields
    if type(fields) is not int or fields <= 0 or any(
            type(row.fields) is not int or row.fields != fields for row in by_id.values()):
        raise ValueError('Sequential field scoring requires a uniform positive field count')
    if (type(rounds) is not int or rounds < 0 or type(minibatch_size) is not int
            or not 1 <= minibatch_size <= len(training) or type(metric_limit) is not int or metric_limit < len(val_ids)):
        raise ValueError('The search budget must cover valid rounds and the incumbent validation')
    if observed_charge is not None and not callable(observed_charge):
        raise ValueError('Observed charge must be a callback')

    weight = 1 << (max(len(train_ids), len(val_ids)) * fields).bit_length()
    denominator = weight + fields
    train_set, val_set = set(train_ids), set(val_ids)
    pool = [incumbent]
    replies, scores, charges = {}, {}, {}
    # Maintain the control's round horizon even when the paired proof
    # skips reads. This also gives every actual read a place in the reserve.
    validation_reserve = {(incumbent, case) for case in val_ids}
    accounted = set(validation_reserve)
    child_reserve = minibatch_size + len(val_ids)

    def committed_reads():
        return len(scores.keys() | validation_reserve) if reinvest_savings else len(accounted)

    def observe(prompt, case):
        key = prompt, case
        if key not in scores:
            if key not in accounted or len(scores) >= metric_limit:
                raise ValueError('A field read exceeded the sequential search scope')
            row = by_id[case]
            reply = evaluate(prompt, row)
            scores[key] = _validated_field_score(reply, fields, weight)
            replies[key] = reply
            if observed_charge is not None:
                charges[key] = read_charge(observed_charge, prompt, row, reply)
        return scores[key]

    def grades(prompt):
        if prompt not in pool:
            raise ValueError('Full grades are available only for tracked prompts')
        return tuple(observe(prompt, case) / denominator for case in val_ids)

    def perfect(prompt):
        if any(owner == prompt and case in val_set and value < denominator
               for (owner, case), value in scores.items()):
            return False
        return all(observe(prompt, case) == denominator for case in val_ids)

    latest = incumbent
    for index in range(rounds):
        min_reserve = child_reserve if reinvest_savings else child_reserve + minibatch_size
        remaining = metric_limit - committed_reads()
        if min_reserve > remaining:
            break
        if latest is not None and perfect(latest):
            return latest
        parent, ids = schedule(index, tuple(pool), grades)
        batch = tuple(ids)
        if parent not in pool or len(batch) != minibatch_size or len(set(batch)) != len(batch) or not set(batch) <= train_set:
            raise ValueError('The schedule must select a tracked parent and distinct training rows')
        if reinvest_savings and child_reserve + sum((parent, case) not in scores for case in batch) > remaining:
            break
        accounted.update((parent, case) for case in batch)
        for case in batch:
            observe(parent, case)
        child = propose(index, parent, tuple((by_id[case], replies[parent, case]) for case in batch))
        latest = None
        if reinvest_savings and all(scores[parent, case] == denominator for case in batch):
            continue
        accounted.update((child, case) for case in batch)
        if child != parent and _wins(parent, child, batch, scores, observe, denominator):
            latest = child
            pool.append(child)
            new_reserve = {(child, case) for case in val_ids}
            validation_reserve.update(new_reserve)
            accounted.update(new_reserve)

    leader = incumbent
    for rewrite in dict.fromkeys(pool[1:]):
        if leader == rewrite:
            continue
        paired = {key: value for key, value in scores.items() if key[0] in (leader, rewrite) and key[1] in val_set}
        paired_charges = {key: charges[key] for key in paired} if observed_charge is not None else None

        def observe_pair(prompt, case):
            key = prompt, case
            paired[key] = observed = observe(prompt, case)
            if paired_charges is not None:
                paired_charges[key] = charges[key]
            return observed

        if _wins(leader, rewrite, val_ids, paired, observe_pair, denominator,
                 charges=paired_charges, full_order=val_ids):
            leader = rewrite
    return leader
