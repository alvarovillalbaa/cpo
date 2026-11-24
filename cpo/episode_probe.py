"""Measure a small training prefix before choosing an episode schedule."""


def observe_training_prefix(incumbent, candidates, rows, evaluate, *, count, paired):
    """Return an incumbent pass count or the sign of a paired gain.

    The paired probe compares the already ordered first challenger on the
    same training cases. Every callback represents one paid reply. These
    grades choose a schedule and remain outside validation and qualification.
    """
    if type(count) is not int or count < 0 or count > len(rows):
        raise ValueError('The training prefix must fit the available rows')
    if count == 0:
        return '0'
    if paired and not candidates:
        raise ValueError('A paired training probe needs a challenger')

    def read(prompt, row):
        passed = evaluate(prompt, row)
        if type(passed) is not bool:
            raise ValueError('Training probes require exact boolean grades')
        return passed

    base, challenger = 0, 0
    for row in rows[:count]:
        base += read(incumbent, row)
        if paired:
            challenger += read(candidates[0], row)
    if paired:
        difference = challenger - base
        return str((difference > 0) - (difference < 0))
    return str(base)
