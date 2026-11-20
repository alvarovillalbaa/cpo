"""Probe required critical cases before paying for complete confirmations."""

from collections import Counter

from .covered_pool import select_covered_pool
from .coverage_confirmation import confirm_covered_gain
from .pool import PoolResult


def required_miss(baseline, strata):
    """Return the first incumbent miss whose stratum has no other witness."""
    counts = Counter(strata.values())
    return next((case for case, passed in baseline.items()
                 if not passed and case in strata and counts[strata[case]] == 1), None)


def select_required_covered_pool(candidates, validation, evaluate, *, metric_limit, critical_strata):
    """Run the coverage-aware race, testing a provably required miss first when present."""
    candidates, validation = tuple(candidates), tuple(validation)
    if not candidates or len(set(candidates)) != len(candidates):
        raise ValueError('Pool requires distinct candidates and an incumbent')
    incumbent, *challengers = candidates
    strata = dict(critical_strata)
    observations = {}

    def baseline_observation(prompt, row):
        observation = evaluate(prompt, row)
        observations[row.id] = observation
        return observation

    initial = select_covered_pool((incumbent,), validation, baseline_observation,
                                  metric_limit=metric_limit, critical_strata=strata)
    baseline = {row.id: observations[row.id].passed for row in validation}
    witness = required_miss(baseline, strata)
    if witness is None:
        return select_covered_pool(
            candidates, validation,
            lambda prompt, row: observations[row.id] if prompt == incumbent else evaluate(prompt, row),
            metric_limit=metric_limit, critical_strata=strata,
        )

    rows = {row.id: row for row in validation}
    protected = {key for key in strata if baseline[key]}
    winner, score, spent = incumbent, initial.validation_passes, initial.evaluations

    def read(prompt, row_id):
        nonlocal spent
        passed = evaluate(prompt, rows[row_id]).passed
        if type(passed) is not bool:
            raise ValueError('Pool observations require an exact boolean outcome')
        spent += 1
        return passed

    for prompt in challengers:
        if spent + len(rows) > metric_limit or score == len(rows):
            break
        if not read(prompt, witness):
            continue
        measured = confirm_covered_gain(baseline, score, protected, strata, {witness: True},
                                        lambda row_id: read(prompt, row_id))
        if measured is not None:
            winner, score = prompt, measured
    return PoolResult(winner, score, spent)
