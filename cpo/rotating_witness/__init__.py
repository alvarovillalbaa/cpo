"""Budgeted witness nomination followed by independent paired qualification."""

from random import Random

from ..fixed_pool_cycle import FixedPoolCycleResult
from ..paired_qualification import certify_paired_qualification
from ..single_finalist import FinalistResult

__all__ = ['run_rotating_witness_cycle']


def _nominate(incumbent, candidates, rows, evaluate, *, metric_limit, seed):
    if not candidates or metric_limit == 0:
        return FinalistResult(incumbent, None, 0)

    validation = list(rows)
    Random(seed).shuffle(validation)
    observed = {}

    def observe(prompt, row):
        key = prompt, row.id
        if key not in observed:
            if len(observed) >= metric_limit:
                return None
            passed = evaluate(prompt, row).passed
            if type(passed) is not bool:
                raise ValueError('Validation requires exact boolean outcomes')
            observed[key] = passed
        return observed[key]

    first_pass, first_miss = None, None
    for row in validation:
        passed = observe(incumbent, row)
        if passed is None:
            return FinalistResult(incumbent, None, len(observed))
        if passed and first_pass is None:
            first_pass = row
        elif not passed and first_miss is None:
            first_miss = row
        if first_pass is not None and first_miss is not None:
            break
    if first_miss is None:
        return FinalistResult(incumbent, None, len(observed))

    required = 1 + int(first_pass is not None)
    eligible = []
    for prompt in candidates:
        if metric_limit - len(observed) < required:
            break
        if observe(prompt, first_miss) and (first_pass is None or observe(prompt, first_pass)):
            eligible.append(prompt)
            if len(eligible) == 2:
                break
    if not eligible:
        return FinalistResult(incumbent, None, len(observed))

    if len(eligible) == 2 and metric_limit - len(observed) >= 2:
        tie_case = next((row for row in validation if row not in (first_pass, first_miss)), None)
        if tie_case is not None:
            eligible.sort(key=lambda prompt: observe(prompt, tie_case), reverse=True)

    def preserves_critical(prompt):
        for row in validation:
            if row.critical:
                baseline = observe(incumbent, row)
                if baseline is None or (baseline and observe(prompt, row) is not True):
                    return False
        return True

    for prompt in eligible:
        if preserves_critical(prompt):
            return FinalistResult(prompt, prompt, len(observed))
    return FinalistResult(incumbent, eligible[0], len(observed))


def run_rotating_witness_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                               metric_limit, qualify, repeats=1, minimum_gain=1, seed=0,
                               qualification_limit=None):
    """Screen up to two supplied challengers and qualify at most one.

    Validation requires exact Observation values. The screen samples an
    incumbent miss and, when available, an incumbent pass. A third case can
    rank two eligible challengers. A nomination must preserve every critical
    validation pass of the incumbent. Use a different seed in later cycles.
    Qualification uses separate rows and exact boolean replies. A failed or
    unfinished qualification keeps the incumbent.
    """
    candidates, validation, qualification_rows = tuple(candidates), tuple(validation), tuple(qualification_rows)
    all_ids = [row.id for row in (*validation, *qualification_rows)]
    if not validation or not qualification_rows or len(set(all_ids)) != len(all_ids):
        raise ValueError('Validation and qualification need nonempty panels with distinct, disjoint row IDs')
    if incumbent in candidates or len(set(candidates)) != len(candidates):
        raise ValueError('The challenger pool must be distinct from the incumbent')
    if type(metric_limit) is not int or metric_limit < 0:
        raise ValueError('The search cap must be a nonnegative integer')
    if type(repeats) is not int or repeats < 1 or type(minimum_gain) is not int or minimum_gain < 1:
        raise ValueError('Qualification repeat and gain thresholds must be positive integers')
    if qualification_limit is not None and (type(qualification_limit) is not int or qualification_limit < 0):
        raise ValueError('Qualification limit must be a nonnegative integer')

    selection = _nominate(incumbent, candidates, validation, evaluate, metric_limit=metric_limit, seed=seed)
    if selection.prompt == incumbent:
        return FixedPoolCycleResult(selection, None)
    decision = certify_paired_qualification(
        incumbent, selection.prompt, qualification_rows, qualify, repeats=repeats, minimum_gain=minimum_gain,
        seed=seed, evaluation_limit=qualification_limit,
    )
    return FixedPoolCycleResult(selection, decision)
