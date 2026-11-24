"""Choose a search screen from the incumbent's paid qualification prefix."""

from .two_sided_certificate_cycle import _run


def run_qualification_prefix_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                   metric_limit, qualify, screens, minimum_gain=1, seed=0):
    """Use the screen at the position of the first incumbent qualification miss.

    Supply one screen per qualification row. The dispatcher uses the original
    precheck replies and makes no routing probes. If the incumbent precheck
    closes the search, no screen runs. The selected screen receives only the
    validation inputs. The original exact qualification settles deployment.
    """
    rows, screens = tuple(qualification_rows), tuple(screens)
    if not rows or len(rows) != len(screens) or not all(map(callable, screens)):
        raise ValueError('Supply one callable search screen per qualification row')

    read_count, first_miss = 0, None

    def record(prompt, row, repeat):
        nonlocal read_count, first_miss
        grade = qualify(prompt, row, repeat)
        if first_miss is None:
            if grade is False:
                first_miss = read_count
            read_count += 1
        return grade

    def select(base, roster, panel, observe, cap):
        return screens[first_miss](base, roster, panel, observe, cap)

    return _run(incumbent, candidates, validation, rows, evaluate, metric_limit=metric_limit, qualify=record,
                minimum_gain=minimum_gain, seed=seed, screen=select)
