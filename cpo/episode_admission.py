"""Decide whether to retain from a perfect incumbent training prefix."""


def retain_after_training_prefix(incumbent, rows, evaluate, *, count):
    """Retain only after every required training case passes.

    A miss admits the episode to the existing search immediately. The
    training prefix contributes no validation or qualification evidence.
    """
    if type(count) is not int or count < 1 or count > len(rows):
        raise ValueError('The required prefix must fit the available training rows')
    for row in rows[:count]:
        passed = evaluate(incumbent, row)
        if type(passed) is not bool:
            raise ValueError('Training probes require exact boolean grades')
        if not passed:
            return False
    return True
