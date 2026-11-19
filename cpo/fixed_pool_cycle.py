"""Screen and independently qualify a challenger from a supplied prompt pool."""

from dataclasses import dataclass

from .bounded_discovery import select_with_bounded_discovery
from .lazy_incumbent import select_with_lazy_incumbent
from .paired_qualification import QualificationDecision, certify_paired_qualification
from .single_finalist import FinalistResult


_SCREENS = {
    'deferred-first-gain': select_with_lazy_incumbent,
    'bounded-two-reads': select_with_bounded_discovery,
}


@dataclass(frozen=True)
class FixedPoolCycleResult:
    search: FinalistResult
    qualification: QualificationDecision | None

    @property
    def prompt(self):
        return self.search.prompt if self.qualification is None else self.qualification.prompt

    @property
    def promoted(self):
        return self.qualification is not None and self.qualification.status == 'promoted'

    @property
    def qualification_evaluations(self):
        return 0 if self.qualification is None else len(self.qualification.observations)


def run_fixed_pool_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                         metric_limit, qualify, screen='deferred-first-gain', repeats=1,
                         minimum_gain=1, seed=0, qualification_limit=None):
    """Use a fixed search cap and an independent, optionally capped qualification.

    Validation receives exact Observation values from evaluate. Qualification
    receives boolean replies from qualify(prompt, row, repeat). An undecided
    qualification keeps the incumbent and retains its observed prefix.
    """
    validation, qualification_rows = tuple(validation), tuple(qualification_rows)
    row_ids = [row.id for row in (*validation, *qualification_rows)]
    if not validation or not qualification_rows or len(set(row_ids)) != len(row_ids):
        raise ValueError('Validation and qualification need nonempty panels with distinct, disjoint row IDs')
    if screen not in _SCREENS:
        raise ValueError('Unknown fixed-pool screen')
    if type(repeats) is not int or repeats < 1 or type(minimum_gain) is not int or minimum_gain < 1:
        raise ValueError('Qualification repeat and gain thresholds must be positive integers')
    if qualification_limit is not None and (type(qualification_limit) is not int or qualification_limit < 0):
        raise ValueError('Qualification limit must be a nonnegative integer')

    selection = _SCREENS[screen](incumbent, candidates, validation, evaluate, metric_limit=metric_limit)
    if selection.prompt == incumbent:
        return FixedPoolCycleResult(selection, None)
    decision = certify_paired_qualification(
        incumbent, selection.prompt, qualification_rows, qualify, repeats=repeats, minimum_gain=minimum_gain,
        seed=seed, evaluation_limit=qualification_limit,
    )
    return FixedPoolCycleResult(selection, decision)
