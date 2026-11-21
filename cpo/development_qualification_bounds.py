"""Assess a development panel with unavailable or output-capped grades."""

from dataclasses import dataclass
from typing import Literal

from .development_qualification import CANDIDATE, check_schedule, rejection_reasons


@dataclass(frozen=True)
class DevelopmentBounds:
    status: Literal['impossible', 'guaranteed', 'undetermined']
    rejection_reasons: tuple[dict, ...] = ()


def assess_development_bounds(schedule, observations, *, gate, search_costs):
    """Certify the shared-sample gate under every completion of missing grades.

    Each observation is an exact boolean or None for a recorded reply without an
    exact grade. A shorter prefix leaves the remaining planned samples unknown.
    Costs are the measured search costs. The caller owns the schedule and decides
    whether its protocol permits a verdict with unknown grades.
    """
    schedule, observed = tuple(schedule), tuple(observations)
    gate, costs = dict(gate), dict(search_costs)
    check_schedule(schedule, costs, gate)
    if len(observed) > len(schedule) or any(value is not None and type(value) is not bool for value in observed):
        raise ValueError('Supply at most one boolean or None per scheduled physical sample')

    # One extremal assignment simultaneously optimizes the candidate's task
    # totals and all matched differences. Shared samples always cancel in a
    # difference. Reversing that assignment simultaneously minimizes them.
    unknown = observed + (None,) * (len(schedule) - len(observed))
    favorable = tuple((CANDIDATE in sample.arms) if result is None else result
                      for sample, result in zip(schedule, unknown, strict=True))
    reasons = rejection_reasons(schedule, favorable, gate, costs)
    if reasons:
        return DevelopmentBounds('impossible', tuple(reasons))
    unfavorable = tuple((CANDIDATE not in sample.arms) if result is None else result
                        for sample, result in zip(schedule, unknown, strict=True))
    if rejection_reasons(schedule, unfavorable, gate, costs):
        return DevelopmentBounds('undetermined')
    return DevelopmentBounds('guaranteed')
