"""Order pending paired reads using only costs already observed."""

from collections import deque


def read_charge(callback, prompt, row, reply):
    fee = callback(prompt, row, reply)
    if fee is not None and (type(fee) is not int or fee < 0):
        raise ValueError('Observed charges must be nonnegative integers or None')
    return fee


def by_observed_cost(missing, scores, incumbent, rewrite, denominator, charges):
    pending = {prompt: deque((index, item) for index, item in enumerate(missing) if item[0] == prompt)
               for prompt in (incumbent, rewrite)}
    while pending[incumbent] and pending[rewrite]:
        old = [denominator - score for (prompt, _), score in scores.items() if prompt == incumbent]
        new = [score for (prompt, _), score in scores.items() if prompt == rewrite]
        old_weight, new_weight = len(old), len(new)
        if all(charge is not None for charge in charges.values()):
            old_cost, new_cost = (sum(fee for (owner, _), fee in charges.items() if owner == prompt)
                                  for prompt in (incumbent, rewrite))
            if old_cost and new_cost:
                old_weight, new_weight = old_cost, new_cost

        # Compare the observed gain per unit without floating-point rounding.
        old_lift, new_lift = sum(old) * new_weight, sum(new) * old_weight
        if old_lift == new_lift:
            prompt = min(pending, key=lambda choice: pending[choice][0][0])
        else:
            prompt = rewrite if new_lift > old_lift else incumbent
        yield pending[prompt].popleft()[1]
    for queue in pending.values():
        yield from (item for _, item in queue)
