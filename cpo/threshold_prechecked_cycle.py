"""Run the certificate screen only while its qualification margin is attainable."""

from .fixed_pool_cycle import FixedPoolCycleResult
from .paired_qualification import QualificationDecision, QualificationObservation
from .prechecked_certificate_cycle import _finish, _screen, run_prechecked_certificate_cycle
from .single_finalist import FinalistResult


def run_threshold_prechecked_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                  metric_limit, qualify, minimum_gain=1, seed=0):
    """Credit incumbent replies through the requested number of misses.

    Qualification uses separate cases and retains the original proof cap.
    Search receives no qualification replies. If the incumbent passes
    enough cases to make the minimum gain impossible, keep it before search.
    """
    if type(minimum_gain) is not int or minimum_gain <= 1:
        return run_prechecked_certificate_cycle(
            incumbent, candidates, validation, qualification_rows, evaluate,
            metric_limit=metric_limit, qualify=qualify, minimum_gain=minimum_gain, seed=seed,
        )

    candidates, validation, rows = tuple(candidates), tuple(validation), tuple(qualification_rows)
    ids = {row.id for row in (*validation, *rows)}
    if not validation or not rows or len(ids) != len(validation) + len(rows):
        raise ValueError('Validation and qualification must be nonempty, distinct and disjoint')
    if incumbent in candidates or len(candidates) != len(set(candidates)):
        raise ValueError('The pool needs distinct challengers besides the incumbent')
    if type(metric_limit) is not int or metric_limit < len(validation):
        raise ValueError('The evaluation cap must fund the incumbent validation panel')

    retained = FinalistResult(incumbent, None, 0)
    if not candidates:
        return FixedPoolCycleResult(retained, QualificationDecision('rejected', incumbent, (), 0, 0))
    size = len(rows)
    if minimum_gain > size:
        return FixedPoolCycleResult(retained, QualificationDecision('rejected', incumbent, (), -size, size))
    history = []

    def read(prompt, row, repeat):
        passed = qualify(prompt, row, repeat)
        if type(passed) is not bool:
            raise ValueError('Qualification requires exact boolean outcomes')
        history.append(QualificationObservation(prompt, row.id, repeat, passed))
        return passed

    misses, upper = 0, size
    for row in rows:
        passed = read(incumbent, row, 0)
        upper -= passed
        misses += not passed
        if upper < minimum_gain:
            decision = QualificationDecision('rejected', incumbent, tuple(history), misses - size, upper)
            return FixedPoolCycleResult(retained, decision)
        if misses == minimum_gain:
            break

    selection, counts = _screen(incumbent, candidates, validation, evaluate, metric_limit)
    if selection.prompt == incumbent:
        decision = QualificationDecision('rejected', incumbent, tuple(history), 0, 0)
    else:
        decision = _finish(incumbent, selection.prompt, rows, read, history, counts, minimum_gain, seed)
    return FixedPoolCycleResult(selection, decision)
