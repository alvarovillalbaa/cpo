"""Defer incumbent reads when a supplied opening rewrite can be certified."""

from .optimizer import ProposalPair, Result, search


def search_with_opening_certificate(initial, train, validation, evaluate, propose, *, opening_pair,
                                    metric_limit, rounds, train_per_round, proposals_per_round=2,
                                    seed=0, race=True, adaptive=False, field_credit=False):
    """Select a perfect first rewrite after observing one incumbent miss.

    Leave the normal search budget and fallback in place. Speculative reads
    are limited to replies that the ordinary first round would also need.
    Outcome equivalence assumes fixed valid replies for each prompt and row.
    """
    train, validation = tuple(train), tuple(validation)
    settings = dict(opening_pair=opening_pair, metric_limit=metric_limit, rounds=rounds,
                    train_per_round=train_per_round, proposals_per_round=proposals_per_round,
                    seed=seed, race=race, adaptive=adaptive, field_credit=field_credit)
    ids = {row.id for row in (*train, *validation)}
    if (not isinstance(opening_pair, ProposalPair) or not train or not validation
            or len(ids) != len(train) + len(validation) or metric_limit < 2 * len(validation)
            or any(type(value) is not int for value in (rounds, train_per_round, proposals_per_round))
            or min(rounds, train_per_round, proposals_per_round) < 1
            or (field_credit and any(type(row.fields) is not int or row.fields < 1 for row in (*train, *validation)))):
        return search(initial, train, validation, evaluate, propose, **settings)
    rewrite = opening_pair.rewrite
    if not isinstance(rewrite, str) or not rewrite.strip() or rewrite == initial:
        return search(initial, train, validation, evaluate, propose, **settings)

    cache = {}

    def read(prompt, row):
        key = prompt, row.id
        if key not in cache:
            if len(cache) >= metric_limit:
                raise RuntimeError('Search evaluation budget exhausted')
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Validation requires exact boolean outcomes')
            if field_credit and (type(reply.matched_fields) is not int or not 0 <= reply.matched_fields <= row.fields
                                 or reply.passed != (reply.matched_fields == row.fields)):
                raise ValueError('Field observations must match the row capacity and exact-pass decision')
            cache[key] = reply
        return cache[key]

    def fallback():
        result = search(initial, train, validation, read, propose, **settings)
        if result.evaluations != len(cache):
            raise RuntimeError('Opening proof made reads outside the ordinary search path')
        return result

    critical = [row for row in validation if row.critical]
    ordinary = [row for row in validation if not row.critical]
    before = {row.id: read(initial, row).passed for row in critical}
    witness = next((row for row in critical if not before[row.id]), None)
    if witness is None:
        witness = next((row for row in ordinary if not read(initial, row).passed), None)
    if witness is None:
        return fallback()

    # The ordinary race checks critical misses before critical passes.
    for row in sorted(critical, key=lambda row: before[row.id]):
        if not read(rewrite, row).passed:
            return fallback()
    if not witness.critical and not read(rewrite, witness).passed:
        return fallback()

    # The witnessed gain prevents domination by the incumbent. All remaining
    # rows are ordinary, so none can trigger the critical veto.
    for row in ordinary:
        if not read(rewrite, row).passed:
            return fallback()
    return Result(rewrite, len(cache), 0, [{'kind': 'certified-opening-rewrite', 'prompt': rewrite,
                                            'incumbentMiss': witness.id,
                                            'passed': sorted(row.id for row in validation)}])
