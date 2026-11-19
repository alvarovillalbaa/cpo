"""Screen prompt pools and certify a strict improvement on validation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CertifiedPoolResult:
    prompt: str
    lower_pass_bound: int
    upper_pass_bound: int
    evaluations: int


def select_certified_pool(candidates, validation, evaluate, *, metric_limit):
    """Return a challenger only after its observed passes exceed the incumbent's total.

    An unevaluated row contributes zero to the lower bound and one to the upper
    bound. The challenger must pass all critical rows the incumbent passed.
    Search prioritizes likely challengers and measures a certificate for one
    promotion or returns the exactly scored incumbent.
    """
    candidates, validation = tuple(candidates), tuple(validation)
    size = len(validation)
    if not candidates or len(set(candidates)) != len(candidates):
        raise ValueError('Pool requires distinct candidates and an incumbent')
    if not validation or len({row.id for row in validation}) != size:
        raise ValueError('Pool selection requires distinct, nonempty validation rows')
    if type(metric_limit) is not int or metric_limit < size:
        raise ValueError('The budget must cover the incumbent')

    spent = 0

    def observe(prompt, row):
        nonlocal spent
        spent += 1
        outcome = evaluate(prompt, row).passed
        if type(outcome) is not bool:
            raise ValueError('Pool observations require an exact boolean outcome')
        return outcome

    incumbent, *active = candidates
    base = {row.id: observe(incumbent, row) for row in validation}
    incumbent_passes = sum(base.values())
    if incumbent_passes == size:
        return CertifiedPoolResult(incumbent, size, size, spent)
    protected = {row.id for row in validation if row.critical and base[row.id]}
    order = sorted(validation, key=lambda row: row.id not in protected)
    counts = dict.fromkeys(active, 0)
    depth = 0

    while len(active) > 1:
        rounds_left = (len(active) - 1).bit_length()
        # Fund the unobserved suffix for one survivor before screening the others.
        screen_budget = metric_limit - spent - (size - depth)
        width = min(size - depth, screen_budget // ((len(active) - 1) * rounds_left))
        if width <= 0:
            break
        cutoff = depth + width
        survivors = []
        for prompt in active:
            for index in range(depth, cutoff):
                row = order[index]
                if observe(prompt, row):
                    counts[prompt] += 1
                elif row.id in protected:
                    break
                if counts[prompt] + size - index - 1 <= incumbent_passes:
                    break
            else:
                survivors.append(prompt)
        depth = cutoff
        active = sorted(survivors, key=counts.__getitem__, reverse=True)[:(len(active) + 1) // 2]
        if active and depth >= len(protected) and counts[active[0]] > incumbent_passes:
            prompt = active[0]
            return CertifiedPoolResult(prompt, counts[prompt], counts[prompt] + size - depth, spent)

    for prompt in active:
        passes = counts[prompt]
        for index in range(depth, size):
            if spent >= metric_limit:
                break
            row = order[index]
            if observe(prompt, row):
                passes += 1
            elif row.id in protected:
                break
            remaining = size - index - 1
            if index + 1 >= len(protected) and passes > incumbent_passes:
                return CertifiedPoolResult(prompt, passes, passes + remaining, spent)
            if passes + remaining <= incumbent_passes:
                break

    return CertifiedPoolResult(incumbent, incumbent_passes, incumbent_passes, spent)
