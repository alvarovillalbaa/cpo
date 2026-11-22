"""Use paired qualification evidence to order the deferred cycle's proof."""

from .deferred_certificate_cycle import _screen
from .expected_qualification import _advance, _bounds, _minimum_expected_reads, _pass_rate, _settled
from .fixed_pool_cycle import FixedPoolCycleResult
from .paired_qualification import QualificationDecision, QualificationObservation
from .prechecked_certificate_cycle import _finish
from .single_finalist import FinalistResult


def _finish_with_partner_evidence(incumbent, challenger, rows, read, history, counts, minimum, seed):
    size = len(rows)
    if size > 8 or len({row.family for row in rows}) != 1 or any(row.critical for row in rows):
        return _finish(incumbent, challenger, rows, read, history, counts, minimum, seed)
    prompts = incumbent, challenger
    sizes = (size,)
    rates = (4 - _pass_rate(*counts[0]), _pass_rate(*counts[1]))
    state = ((len(history), 0, sum(not reply.passed for reply in history)),)
    observed = ({reply.row_id: reply.passed for reply in history}, {})
    while True:
        low, high = _bounds(sizes, state)
        status = _settled(low, high, minimum)
        if status is not None:
            winner = challenger if status == 'promoted' else incumbent
            return QualificationDecision(status, winner, tuple(history), low[0], high[0])
        options = []
        for side, rate in enumerate(rates):
            if len(observed[side]) == size:
                continue
            miss = _minimum_expected_reads(sizes, rates, minimum, _advance(state, 0, side, False))[0]
            hit = _minimum_expected_reads(sizes, rates, minimum, _advance(state, 0, side, True))[0]
            for index, row in enumerate(rows):
                if row.id in observed[side]:
                    continue
                partner = observed[1 - side].get(row.id)
                # Use eighths to average the quarter-rate estimate with the paid partner grade.
                favorable = 2 * rate if partner is None else rate + 4 * (partner == bool(side))
                options.append(((8 - favorable) * miss + favorable * hit, side, index))
        _, side, index = min(options)
        row = rows[index]
        grade = read(prompts[side], row, 0)
        observed[side][row.id] = grade
        state = _advance(state, 0, side, grade == bool(side))


def run_paired_order_certificate_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                       metric_limit, qualify, minimum_gain=1, seed=0):
    """Use the deferred screen and exact proof with same-case reply ordering.

    A paid partner grade changes the next-read estimate. Only actual replies
    settle the qualification bound. Short noncritical panels in one family use
    paired order. Critical cases, multiple families, and panels over eight
    rows use the original deferred cycle's qualification.
    """
    candidates, validation, rows = tuple(candidates), tuple(validation), tuple(qualification_rows)
    ids = {row.id for row in (*validation, *rows)}
    if not validation or not rows or len(ids) != len(validation) + len(rows):
        raise ValueError('Validation and qualification must be nonempty, distinct and disjoint')
    if incumbent in candidates or len(candidates) != len(set(candidates)):
        raise ValueError('The pool needs distinct challengers besides the incumbent')
    if type(metric_limit) is not int or metric_limit < len(validation):
        raise ValueError('The evaluation cap must fund the incumbent validation panel')
    if type(minimum_gain) is not int or minimum_gain < 1:
        raise ValueError('The qualification gain must be a positive integer')

    retained = FinalistResult(incumbent, None, 0)
    if not candidates:
        return FixedPoolCycleResult(retained, QualificationDecision('rejected', incumbent, (), 0, 0))
    size = len(rows)
    if minimum_gain > size:
        return FixedPoolCycleResult(retained, QualificationDecision('rejected', incumbent, (), -size, size))
    history = []

    def read(prompt, row, repeat):
        grade = qualify(prompt, row, repeat)
        if type(grade) is not bool:
            raise ValueError('Qualification requires exact boolean outcomes')
        history.append(QualificationObservation(prompt, row.id, repeat, grade))
        return grade

    misses, upper = 0, size
    for row in rows:
        grade = read(incumbent, row, 0)
        upper -= grade
        misses += not grade
        if upper < minimum_gain:
            decision = QualificationDecision('rejected', incumbent, tuple(history), misses - size, upper)
            return FixedPoolCycleResult(retained, decision)
        if misses == minimum_gain:
            break

    selection, counts = _screen(incumbent, candidates, validation, evaluate, metric_limit)
    if selection.prompt == incumbent:
        decision = QualificationDecision('rejected', incumbent, tuple(history), 0, 0)
    else:
        decision = _finish_with_partner_evidence(
            incumbent, selection.prompt, rows, read, history, counts, minimum_gain, seed,
        )
    return FixedPoolCycleResult(selection, decision)
