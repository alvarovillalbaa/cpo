"""Prove one repaired qualification case while preserving every incumbent pass."""

from collections import Counter
from dataclasses import replace
from functools import lru_cache

from .deferred_certificate_cycle import _screen
from .expected_qualification import _pass_rate
from .fixed_pool_cycle import FixedPoolCycleResult
from .paired_qualification import QualificationDecision, QualificationObservation, certify_paired_qualification
from .single_finalist import FinalistResult


_UNREAD, _INCUMBENT_FAIL, _INCUMBENT_PASS, _CHALLENGER_FAIL, _CHALLENGER_PASS = range(5)
_TIE, _REPAIR, _REGRESSION = range(5, 8)
_TRANSITIONS = {
    (_UNREAD, 0): (_INCUMBENT_FAIL, _INCUMBENT_PASS),
    (_UNREAD, 1): (_CHALLENGER_FAIL, _CHALLENGER_PASS),
    (_INCUMBENT_FAIL, 1): (_TIE, _REPAIR),
    (_INCUMBENT_PASS, 1): (_REGRESSION, _TIE),
    (_CHALLENGER_FAIL, 0): (_TIE, _REGRESSION),
    (_CHALLENGER_PASS, 0): (_REPAIR, _TIE),
}


def _status(counts, repaired):
    unread, incumbent_fail, incumbent_pass, challenger_fail, challenger_pass = counts
    if repaired and not (unread or incumbent_pass or challenger_fail):
        return 'promoted'
    if not (repaired or unread or incumbent_fail or challenger_pass):
        return 'rejected'
    return None


@lru_cache(maxsize=32_768)
def _next_read(counts, repaired, rates):
    if _status(counts, repaired) is not None:
        return 0, None
    # Scale by four to the number of unread replies for exact quarter-rate ties.
    scale = 4 ** (sum(counts) + counts[_UNREAD])
    best = None
    for (row_state, side), outcomes in _TRANSITIONS.items():
        if not counts[row_state] or (repaired and row_state in (_INCUMBENT_FAIL, _CHALLENGER_PASS)):
            continue
        expected = scale
        for likelihood, outcome in zip((4 - rates[side], rates[side]), outcomes, strict=True):
            if outcome == _REGRESSION:
                continue
            remaining = list(counts)
            remaining[row_state] -= 1
            if outcome < _TIE:
                remaining[outcome] += 1
            next_cost, _ = _next_read(tuple(remaining), repaired or outcome == _REPAIR, rates)
            expected += likelihood * next_cost
        option = expected, (row_state, side)
        if best is None or option < best:
            best = option
    return best


def certify_regression_free_qualification(incumbent, challenger, rows, qualify, *,
                                          incumbent_prefix=(), validation_counts=((0, 0), (0, 0)), seed=0):
    """Certify at least one repair and zero regressions using one grade per side.

    Supply previously paid incumbent grades in row order. For at most eight
    rows, paid validation counts estimate independent quarter-rate outcomes
    for choosing the next reply. Only observed qualification grades can settle
    the proof. Larger panels use the seeded certificate with all rows protected.
    """
    rows, prefix = tuple(rows), tuple(incumbent_prefix)
    if not rows or len({row.id for row in rows}) != len(rows):
        raise ValueError('Paired qualification requires distinct, nonempty rows')
    if len(prefix) > len(rows) or any(type(grade) is not bool for grade in prefix):
        raise ValueError('The incumbent prefix must contain boolean grades in qualification row order')
    if (len(validation_counts) != 2 or any(len(pair) != 2 for pair in validation_counts)
            or any(type(passed) is not int or type(total) is not int or not 0 <= passed <= total
                   for passed, total in validation_counts)):
        raise ValueError('Validation counts require two (passed, observed) integer pairs')

    paid = [QualificationObservation(incumbent, row.id, 0, grade) for row, grade in zip(rows, prefix)]

    def finish(status):
        favorable = sum(reply.passed == (reply.prompt == challenger) for reply in paid)
        selected = challenger if status == 'promoted' else incumbent
        return QualificationDecision(status, selected, tuple(paid), favorable - len(rows),
                                     favorable + len(rows) - len(paid))

    if incumbent == challenger:
        return QualificationDecision('rejected', incumbent, tuple(paid), 0, 0)

    def read(prompt, row, repeat):
        grade = qualify(prompt, row, repeat)
        if type(grade) is not bool:
            raise ValueError('Qualification requires exact boolean outcomes')
        paid.append(QualificationObservation(prompt, row.id, repeat, grade))
        return grade

    if len(rows) > 8:
        original = {row.id: row for row in rows}
        known = {reply.row_id: reply.passed for reply in paid}

        def reuse(prompt, row, repeat):
            if prompt == incumbent and row.id in known:
                return known[row.id]
            return read(prompt, original[row.id], repeat)

        protected = tuple(replace(row, critical=True) for row in rows)
        decision = certify_paired_qualification(incumbent, challenger, protected, reuse, seed=seed)
        return finish(decision.status)

    rates = tuple(_pass_rate(*counts) for counts in validation_counts)
    states = [_INCUMBENT_PASS if grade else _INCUMBENT_FAIL for grade in prefix]
    states.extend([_UNREAD] * (len(rows) - len(prefix)))
    repaired = False
    prompts = incumbent, challenger
    while True:
        frequencies = Counter(states)
        counts = tuple(frequencies[index] for index in range(_TIE))
        status = _status(counts, repaired)
        if status is not None:
            return finish(status)
        _, (row_state, side) = _next_read(counts, repaired, rates)
        index = states.index(row_state)
        passed = read(prompts[side], rows[index], 0)
        outcome = _TRANSITIONS[row_state, side][passed]
        if outcome == _REGRESSION:
            return finish('rejected')
        repaired = repaired or outcome == _REPAIR
        states[index] = outcome


def run_regression_free_certificate_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                           metric_limit, qualify, seed=0):
    """Apply the reserved certificate screen and require a regression-free one-gain proof."""
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
    prefix = []
    for row in rows:
        grade = qualify(incumbent, row, 0)
        if type(grade) is not bool:
            raise ValueError('Qualification requires exact boolean outcomes')
        prefix.append(grade)
        if not grade:
            break
    else:
        paid = tuple(QualificationObservation(incumbent, row.id, 0, True) for row in rows)
        return FixedPoolCycleResult(retained, QualificationDecision('rejected', incumbent, paid, -len(rows), 0))

    selection, counts = _screen(incumbent, candidates, validation, evaluate, metric_limit)
    if selection.prompt == incumbent:
        paid = tuple(QualificationObservation(incumbent, row.id, 0, grade) for row, grade in zip(rows, prefix))
        decision = QualificationDecision('rejected', incumbent, paid, 0, 0)
    else:
        decision = certify_regression_free_qualification(
            incumbent, selection.prompt, rows, qualify, incumbent_prefix=prefix, validation_counts=counts, seed=seed,
        )
    return FixedPoolCycleResult(selection, decision)
