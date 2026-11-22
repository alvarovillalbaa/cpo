"""Defer reserved probes while preserving certificate selection."""

from .challenger import certify_challenger
from .fixed_pool_cycle import FixedPoolCycleResult
from .paired_qualification import QualificationDecision, QualificationObservation
from .prechecked_certificate_cycle import _finish
from .single_finalist import FinalistResult


def _screen(incumbent, candidates, rows, evaluate, metric_limit):
    screened = candidates[:max(0, metric_limit - 2 * len(rows) + 1)]
    if not screened:
        return FinalistResult(incumbent, None, 0), None
    paid = 0

    def observe(prompt, row):
        nonlocal paid
        reply = evaluate(prompt, row)
        if type(reply.passed) is not bool:
            raise ValueError('Validation requires exact boolean outcomes')
        paid += 1
        return reply

    base = {row.id: observe(incumbent, row).passed for row in rows}
    witness = next((row for row in rows if not base[row.id]), None)
    if witness is None:
        return FinalistResult(incumbent, None, paid), None
    passes = sum(base.values())
    order = sorted(rows, key=lambda row: base[row.id])
    # The eager screen pays every reserved probe before the first certificate.
    # Keep that full reservation even when the callback has yet to run.
    remaining = metric_limit - len(rows) - len(screened)

    def certificate(prompt, passed):
        nonlocal remaining
        result = certify_challenger(
            order, base, lambda row: observe(prompt, row), metric_limit=remaining,
            observed={witness.id: passed},
        )
        remaining -= result.evaluations
        if result.status == 'promote':
            counts = ((passes, len(rows)), (sum(result.observations.values()), len(result.observations)))
            return FinalistResult(prompt, prompt, paid), counts
        return None

    failed_probes = []
    for prompt in screened:
        if remaining < passes:
            break
        if observe(prompt, witness).passed:
            certified = certificate(prompt, True)
            if certified is not None:
                return certified
        else:
            failed_probes.append(prompt)
    for prompt in failed_probes:
        if remaining <= passes:
            break
        certified = certificate(prompt, False)
        if certified is not None:
            return certified
    return FinalistResult(incumbent, None, paid), None


def run_deferred_certificate_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                   metric_limit, qualify, minimum_gain=1, seed=0):
    """Use reserved probe priority and charge only replies the screen needs.

    The fixed-pool decision and qualification match threshold prechecking with
    eager probes when each prompt and case has a stable grade. Callback order
    can differ. The search keeps the entire eager reservation, including slots
    that go unused. Qualification receives the same paid validation evidence.
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
