"""Optionally fund a second independent admission after an exact rejection."""

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction

from .qualification_budget import AdmissionDecision, qualify_with_budget_lookahead


__all__ = ['FundedAdmissionResult', 'qualify_with_funded_retry']


@dataclass(frozen=True)
class FundedAdmissionResult:
    prompt: str
    first: AdmissionDecision | None = None
    retry: AdmissionDecision | None = None
    retry_candidate: str | None = None

    @property
    def qualification_evaluations(self):
        return sum(len(proof.observations) for proof in (self.first, self.retry) if proof is not None)


def qualify_with_funded_retry(incumbent, nominee, cycles, evaluate, validation_grades, *,
                              minimum_retry_lookups, evaluation_limit=24, maximum_extension_rows=4, minimum_gain=1):
    """Qualify a frozen nominee and, after exact rejection, one already-paid rival.

    Supply an ordered sequence of WitnessCycle values and a ledger mapping
    (prompt, validation row ID) to exact bool. The callback receives a prompt,
    Row, and repeat index. Use distinct noncritical qualification rows from
    one family, disjoint from all validation and held-out rows.
    """
    limits = (minimum_retry_lookups, evaluation_limit, maximum_extension_rows)
    if any(type(value) is not int or value < 0 for value in limits) or maximum_extension_rows > 12:
        raise ValueError('Use nonnegative lookup limits and at most 12 tie-extension rows')
    if type(minimum_gain) is not int or minimum_gain < 1:
        raise ValueError('The minimum gain must be a positive integer')
    if nominee is None or nominee == incumbent:
        return FundedAdmissionResult(incumbent)

    roster, validation = {}, set()
    panels = []
    for cycle in cycles:
        for prompt in cycle.candidates:
            if prompt == incumbent or prompt in roster:
                raise ValueError('Use a distinct roster of challengers across the episode')
            roster[prompt] = len(panels)
        validation.update(row.id for row in cycle.validation)
        panels.append(tuple(cycle.qualification))

    rows = tuple(row for panel in panels for row in panel)
    ids = {row.id for row in rows}
    if (nominee not in roster or any(not 1 <= len(panel) <= 12 for panel in panels)
            or len(ids) != len(rows) or len({row.family for row in rows}) != 1
            or any(row.critical for row in rows) or ids & validation):
        raise ValueError('Use an enrolled nominee and distinct single-family panels disjoint from validation')

    passes, counts = Counter(), Counter()
    for (prompt, case_id), passed in validation_grades.items():
        if (prompt != incumbent and prompt not in roster) or case_id not in validation or type(passed) is not bool:
            raise ValueError('Each paid grade must be boolean and belong to a declared prompt and validation row')
        passes[prompt] += passed
        counts[prompt] += 1

    def prove(candidate, base, reserve, cap):
        priors = tuple((passes[prompt], counts[prompt]) for prompt in (incumbent, candidate))
        return qualify_with_budget_lookahead(incumbent, candidate, base, evaluate, reserve=reserve,
                                             minimum_gain=minimum_gain, validation_counts=priors,
                                             evaluation_limit=cap, prioritize_promotion=False)

    initial_slot = roster[nominee]
    base = panels[initial_slot]
    reserve = tuple(row for panel in panels[:initial_slot] for row in panel)[:maximum_extension_rows]
    first = prove(nominee, base, reserve, evaluation_limit)
    initial = FundedAdmissionResult(first.prompt, first)
    remaining = evaluation_limit - len(first.observations)
    if first.status != 'rejected' or remaining < minimum_retry_lookups:
        return initial

    rival = max((prompt for prompt in roster if prompt != nominee and counts[prompt]), default=None,
                key=lambda prompt: Fraction(passes[prompt] + 1, counts[prompt] + 2))
    if rival is None:
        return initial

    retired = {row.id for row in base}
    if first.used_reserve:
        retired.update(row.id for row in reserve)
    preferred = roster[rival]
    order = (preferred, *(slot for slot in range(len(panels)) if slot != preferred))
    slot = next((slot for slot in order if retired.isdisjoint(row.id for row in panels[slot])), None)
    if slot is None or remaining < len(panels[slot]) + minimum_gain:
        return initial

    backup = panels[slot]
    spare = tuple(row for panel in panels[:slot] for row in panel if row.id not in retired)[:maximum_extension_rows]
    second = prove(rival, backup, spare, remaining)
    return FundedAdmissionResult(second.prompt, first, second, rival)
