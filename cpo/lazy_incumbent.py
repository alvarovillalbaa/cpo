"""Defer incumbent validation without changing the first-gain decision."""

from .challenger import certify_challenger
from .optimizer import Row
from .paired_qualification import certify_paired_qualification
from .single_finalist import FinalistResult


def select_with_lazy_incumbent(incumbent, candidates, validation, evaluate, *, metric_limit, rotate_misses=False,
                               paired_proof=False):
    """Keep eager nominations and exact certificates on deterministic outcomes.

    The logical budget still reserves the complete incumbent panel and space
    to finish a finalist. The result counts only callback calls actually made.
    Rows skipped after a decisive bound cannot change the decision. A paired
    proof can change the order and number of challenger evaluations.
    """
    rows, candidates = tuple(validation), tuple(candidates)
    count = len(rows)
    if not rows or len({row.id for row in rows}) != count:
        raise ValueError('The validation panel must be nonempty and have distinct cases')
    if incumbent in candidates or len(set(candidates)) != len(candidates):
        raise ValueError('The challenger pool must be distinct from the incumbent')
    if type(metric_limit) is not int or metric_limit < count:
        raise ValueError('The evaluation cap must fund the incumbent')

    baseline, misses = {}, []
    cursor = spent = 0

    def observe(prompt, row):
        nonlocal spent
        reply = evaluate(prompt, row)
        if type(reply.passed) is not bool:
            raise ValueError('Validation requires exact boolean outcomes')
        spent += 1
        return reply

    def incumbent_passed(row):
        if row.id not in baseline:
            baseline[row.id] = observe(incumbent, row).passed
        return baseline[row.id]

    def advance():
        nonlocal cursor
        row = rows[cursor]
        cursor += 1
        if not incumbent_passed(row):
            misses.append(row)
        return row

    limit = max(0, metric_limit - (2 * count - 1))
    finalist, evidence = None, {}
    for index, prompt in enumerate(candidates[:limit]):
        wanted = index if rotate_misses else 0
        while len(misses) <= wanted and cursor < count:
            advance()
        if not misses:
            break
        witness = misses[wanted % len(misses)]
        if observe(prompt, witness).passed:
            finalist, evidence = prompt, {witness.id: True}
            break
    if finalist is None:
        return FinalistResult(incumbent, None, spent)

    if paired_proof:
        originals = {row.id: row for row in rows}
        known_first = sorted(rows, key=lambda row: (not row.critical, row.id not in baseline))

        def measure(prompt, case, _repeat):
            row = originals[case.id]
            if prompt == incumbent:
                return incumbent_passed(row)
            if row.id not in evidence:
                evidence[row.id] = observe(finalist, row).passed
            return evidence[row.id]

        # Validation requires a scalar gain. Preserve the critical flags
        # while using one family for the paired proof.
        scalar = [Row(row.id, 'validation', row.critical) for row in known_first]
        decision = certify_paired_qualification(incumbent, finalist, scalar, measure)
        return FinalistResult(decision.prompt, finalist, spent)

    protected = tuple(row for row in rows if row.critical and incumbent_passed(row))
    while len(baseline) < count:
        remaining_protected = next((row for row in protected if row.id not in evidence), None)
        incumbent_low = sum(baseline.values())
        incumbent_high = incumbent_low + count - len(baseline)
        challenger_low = sum(evidence.values())
        challenger_high = challenger_low + count - len(evidence)
        if any(evidence.get(row.id) is False for row in protected) or challenger_high <= incumbent_low:
            return FinalistResult(incumbent, finalist, spent)
        if remaining_protected is None and challenger_low > incumbent_high:
            return FinalistResult(finalist, finalist, spent)
        # Find out whether the eager certificate would have stopped before
        # asking for another challenger reply.
        if challenger_high <= incumbent_high or (
                remaining_protected is None and challenger_low > incumbent_low):
            advance()
            continue
        if remaining_protected is not None:
            row = remaining_protected
        else:
            row = next((miss for miss in misses if miss.id not in evidence), None)
            while row is None and cursor < count:
                scanned = advance()
                if not baseline[scanned.id] and scanned.id not in evidence:
                    row = scanned
            if row is None:
                break
        evidence[row.id] = observe(finalist, row).passed

    order = sorted(rows, key=lambda row: baseline[row.id])
    result = certify_challenger(order, baseline, lambda row: observe(finalist, row),
                                metric_limit=metric_limit - spent, observed=evidence)
    selected = finalist if result.status == 'promote' else incumbent
    return FinalistResult(selected, finalist, spent)
