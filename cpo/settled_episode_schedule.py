"""Choose an episode schedule once every possible probe outcome agrees."""


def choose_schedule(incumbent, rows, evaluate, *, actions):
    """Read only enough training grades to settle the count-to-action table.

    The table has one action for each possible incumbent pass count. Return
    the same action as a full probe of the supplied case prefix. Callers
    charge only the replies they actually receive.
    """
    rows, actions = tuple(rows), tuple(actions)
    if len(actions) != len(rows) + 1:
        raise ValueError('Provide one action per possible training pass count')

    passes = 0
    for index, row in enumerate(rows):
        possible = actions[passes:passes + len(rows) - index + 1]
        if all(action == possible[0] for action in possible[1:]):
            return possible[0]
        grade = evaluate(incumbent, row)
        if type(grade) is not bool:
            raise ValueError('Training probes require exact boolean grades')
        passes += grade
    return actions[passes]
