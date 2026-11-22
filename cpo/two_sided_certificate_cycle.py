"""Screen a fixed pool with exact validation of a partially observed pair."""

from functools import partial

from .expected_qualification import _advance, _minimum_expected_reads, _pass_rate
from .fixed_pool_cycle import FixedPoolCycleResult
from .paired_order_certificate_cycle import _finish_with_partner_evidence
from .paired_qualification import QualificationDecision, QualificationObservation
from .single_finalist import FinalistResult


def _next_expected(rows, known, unsafe, favorable):
    size = len(rows)
    sizes = (size,)
    state = ((len(known[0]), len(known[1]), favorable),)
    rates = (4 - _pass_rate(sum(known[0].values()), len(known[0])),
             _pass_rate(sum(known[1].values()), len(known[1])))
    options = []
    for side, seen in enumerate(known):
        if len(seen) == size:
            continue
        miss = _minimum_expected_reads(sizes, rates, 1, _advance(state, 0, side, False))[0]
        hit = _minimum_expected_reads(sizes, rates, 1, _advance(state, 0, side, True))[0]
        for index, row in enumerate(rows):
            if row.id in seen:
                continue
            partner = known[1 - side].get(row.id)
            likelihood = 2 * rates[side] if partner is None else rates[side] + 4 * (partner == bool(side))
            options.append((row.id not in unsafe, (8 - likelihood) * miss + likelihood * hit, index, side))
    _, _, index, side = min(options)
    return rows[index], side


def _certify(rows, base, contender, read, allowance, expected):
    size = len(rows)
    known = base, contender
    for spent in range(allowance + 1):
        favorable = len(base) - sum(base.values()) + sum(contender.values())
        unfavorable = len(base) + len(contender) - favorable
        unresolved = {row.id for row in rows if row.critical and
                      base.get(row.id) is not False and contender.get(row.id) is not True}
        if any(base.get(case) is True and contender.get(case) is False for case in unresolved):
            return False
        if favorable > size and not unresolved:
            return True
        if unfavorable >= size:
            return False
        if max(size + 1 - favorable, len(unresolved)) > allowance - spent:
            return False
        if expected:
            row, side = _next_expected(rows, known, unresolved, favorable)
        else:
            row, side = next((row, side) for row in sorted(rows, key=lambda row: row.id not in unresolved)
                             for side in (0, 1) if row.id not in known[side])
        known[side][row.id] = read(side, row)
    raise RuntimeError('The validation proof must settle or exhaust its allowance')


def _screen(incumbent, candidates, rows, evaluate, cap, *, expected):
    roster = candidates[:max(0, cap - 2 * len(rows) + 1)]
    paid = 0

    def observe(prompt, row):
        nonlocal paid
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Validation requires exact boolean outcomes')
        paid += 1
        return grade

    if not roster:
        return FinalistResult(incumbent, None, paid), None
    base = {}
    for row in rows:
        base[row.id] = observe(incumbent, row)
        if not base[row.id]:
            witness = row
            break
    else:
        return FinalistResult(incumbent, None, paid), None

    unprobed = len(roster)
    expected = expected and len(rows) <= 8

    def attempt(prompt, evidence):
        prompts = incumbent, prompt
        certified = _certify(rows, base, evidence, lambda side, row: observe(prompts[side], row),
                             cap - paid - unprobed, expected)
        if certified:
            return (FinalistResult(prompt, prompt, paid),
                    ((sum(base.values()), len(base)), (sum(evidence.values()), len(evidence))))
        return None

    failed = []
    for prompt in roster:
        # The current probe is reserved. The proof needs one fewer favorable
        # reply after a positive probe, even if every subsequent read helps.
        if cap - paid - unprobed < len(rows) - (len(base) - sum(base.values())):
            break
        unprobed -= 1
        grade = observe(prompt, witness)
        evidence = {witness.id: grade}
        if grade:
            result = attempt(prompt, evidence)
            if result is not None:
                return result
        else:
            failed.append((prompt, evidence))
    for prompt, evidence in failed:
        if cap - paid - unprobed <= len(rows) - (len(base) - sum(base.values())):
            break
        result = attempt(prompt, evidence)
        if result is not None:
            return result
    return FinalistResult(incumbent, None, paid), None


def _run(incumbent, candidates, validation, qualification_rows, evaluate, *,
         metric_limit, qualify, minimum_gain=1, seed=0, screen):
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

    selection, counts = screen(incumbent, candidates, validation, evaluate, metric_limit)
    if selection.prompt == incumbent:
        decision = QualificationDecision('rejected', incumbent, tuple(history), 0, 0)
    else:
        decision = _finish_with_partner_evidence(
            incumbent, selection.prompt, rows, read, history, counts, minimum_gain, seed,
        )
    return FixedPoolCycleResult(selection, decision)


def run_two_sided_certificate_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                    metric_limit, qualify, minimum_gain=1, seed=0):
    """Reserve shared probes and prove a strict gain with paid grades on either side.

    Freeze the candidate roster and supply distinct validation and qualification
    panels. Evaluation must return a boolean grade in Observation.passed.
    Qualification must return a bool. Grades must be stable within the cycle.
    Validation can stop with unread incumbent cases once a strict gain and
    critical-case safety are certain. Use expected-cost order for up to eight
    validation cases and paired row order for larger panels. An independent
    qualification still determines deployment.
    """
    return _run(incumbent, candidates, validation, qualification_rows, evaluate,
                metric_limit=metric_limit, qualify=qualify, minimum_gain=minimum_gain, seed=seed,
                screen=partial(_screen, expected=True))
