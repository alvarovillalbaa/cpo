"""Select an exact validation winner from a two-witness shortlist."""

from ..pool import PoolResult, select_pool


def select_two_witness_pool(candidates, validation, evaluate, *, metric_limit):
    """Screen challengers on an incumbent miss and pass before the final race.

    The first candidate is the incumbent. Each (prompt, row) is evaluated at
    most once. The limit counts calls to evaluate, including the witnesses.
    Reserve any separate training or qualification budget before calling.
    With too little room for the screen, use the ordinary bounded pool race.
    """
    candidates, rows = tuple(candidates), tuple(validation)
    size = len(rows)
    if not candidates or len(set(candidates)) != len(candidates):
        raise ValueError('Pool requires distinct candidates and an incumbent')
    if not rows or len({row.id for row in rows}) != size:
        raise ValueError('Pool selection requires distinct, nonempty validation rows')
    if type(metric_limit) is not int or metric_limit < size:
        raise ValueError('The budget must cover the incumbent')

    incumbent, *challengers = candidates
    worst_case = size + 2 * len(challengers) + 2 * (size - 2)
    if size < 2 or len(challengers) <= 2 or worst_case > metric_limit:
        return select_pool(candidates, rows, evaluate, metric_limit=metric_limit, adaptive_rejection=True)

    observed = {}

    def observe(prompt, row):
        key = prompt, row.id
        if key not in observed:
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Pool observations require an exact boolean outcome')
            observed[key] = reply
        return observed[key]

    passed = {row.id for row in rows if observe(incumbent, row).passed}
    if len(passed) == size:
        return PoolResult(incumbent, size, len(observed))
    misses = [row for row in rows if row.id not in passed]
    protected = {row.id for row in rows if row.critical and row.id in passed}
    first = misses[0]
    if passed:
        second = min((row for row in rows if row.id in passed), key=lambda row: row.id not in protected)
    else:
        second = misses[1]

    initial = [observe(prompt, first).passed for prompt in challengers]
    ranked = sorted(zip(initial, challengers, strict=True), key=lambda pair: pair[0], reverse=True)
    target = len(passed) + 1
    leaders = []
    for order, (hit, prompt) in enumerate(ranked):
        if hit + size - 1 < target:
            continue
        if len(leaders) == 2 and (hit + 1, hit, -order) <= leaders[-1][0]:
            continue
        second_hit = observe(prompt, second).passed
        score = hit + second_hit
        if (not second_hit and second.id in protected) or score + size - 2 < target:
            continue
        leaders.append(((score, hit, -order), prompt))
        leaders.sort(reverse=True)
        del leaders[2:]

    finalists = (incumbent, *(prompt for _, prompt in leaders))
    result = select_pool(finalists, rows, observe, metric_limit=len(finalists) * size, adaptive_rejection=True)
    return PoolResult(result.prompt, result.validation_passes, len(observed))
