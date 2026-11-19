"""Certify a challenger using an existing validation journal and a fresh-call budget."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from .optimizer import Observation, Row


@dataclass(frozen=True)
class ChallengeResult:
    status: Literal['promote', 'critical_regression', 'cannot_improve', 'budget']
    observations: dict[str, bool]
    evaluations: int
    lower_pass_bound: int
    upper_pass_bound: int
    minimum_fresh_for_promotion: int | None


def certify_challenger(
    validation: Iterable[Row],
    incumbent: Mapping[str, bool],
    evaluate: Callable[[Row], Observation],
    *,
    metric_limit: int,
    observed: Mapping[str, bool] | None = None,
) -> ChallengeResult:
    """Require a strict gain and preserve the incumbent's measured critical passes.

    The limit counts fresh challenger evaluations. Supply cached challenger
    observations to continue an interrupted validation on the same rows and
    evaluator. A budget result retains the evidence and the smallest number
    of additional observations that could certify promotion. An eliminated
    challenger has no remaining path to promotion.
    """
    rows = tuple(validation)
    row_ids = {row.id for row in rows}
    if not rows or len(row_ids) != len(rows) or incumbent.keys() != row_ids:
        raise ValueError('Provide one incumbent observation per distinct validation row')
    if type(metric_limit) is not int or metric_limit < 0:
        raise ValueError('The fresh evaluation limit must be a nonnegative integer')
    evidence = dict(observed) if observed is not None else {}
    if evidence.keys() - row_ids or any(type(value) is not bool for value in (*incumbent.values(), *evidence.values())):
        raise ValueError('Validation evidence must contain exact boolean outcomes for known rows')

    protected = {row.id for row in rows if row.critical and incumbent[row.id]}
    pending = iter(sorted((row for row in rows if row.id not in evidence), key=lambda row: row.id not in protected))
    protected_pending = protected - evidence.keys()
    baseline = sum(incumbent.values())
    passed = sum(evidence.values())
    spent = 0
    critical_loss = any(evidence.get(case) is False for case in protected)
    while True:
        upper = passed + len(rows) - len(evidence)
        needed = max(baseline - passed + 1, len(protected_pending))
        if critical_loss:
            status = 'critical_regression'
        elif needed == 0:
            status = 'promote'
        elif upper <= baseline:
            status = 'cannot_improve'
        elif needed > metric_limit - spent:
            status = 'budget'
        else:
            row = next(pending)
            outcome = evaluate(row).passed
            if type(outcome) is not bool:
                raise ValueError('Validation observations must be exact boolean outcomes')
            evidence[row.id] = outcome
            passed += outcome
            spent += 1
            critical_loss = row.id in protected and not outcome
            protected_pending.discard(row.id)
            continue
        remaining = needed if status in ('promote', 'budget') else None
        return ChallengeResult(status, evidence, spent, passed, upper, remaining)
