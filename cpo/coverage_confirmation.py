"""Confirm a validation improvement with mandatory case and group coverage."""

from collections import Counter
from collections.abc import Callable, Hashable, Iterable, Mapping


def confirm_covered_gain(
    baseline: Mapping[str, bool],
    target: int,
    protected: Iterable[str],
    strata: Mapping[str, Hashable],
    known: Mapping[str, bool],
    evaluate: Callable[[str], bool],
    *,
    prioritize_coverage: bool = True,
) -> int | None:
    """Return an exact improved score or abandon a disproved candidate.

    Every protected row must pass and every represented stratum must have
    a passing member. The caller reserves enough lookups for every unseen
    row. Cached observations are free and are never requested again.
    """
    protected = set(protected)
    rows = baseline.keys()
    if not protected <= rows or not strata.keys() <= rows or not known.keys() <= rows:
        raise ValueError('Confirmation evidence and constraints must refer to validation rows')
    if any(known.get(row) is False for row in protected):
        return None

    uncovered = set(strata.values()) - {group for row, group in strata.items() if known.get(row) is True}
    remaining = Counter(strata[row] for row in strata if row not in known)
    unknown = [row for row in baseline if row not in known]
    passes, reads_left = sum(known.values()), len(unknown)
    if passes + reads_left <= target or any(remaining[group] == 0 for group in uncovered):
        return None

    def priority(row):
        group = strata.get(row)
        ranked = prioritize_coverage and row in strata and group in uncovered
        coverage_rank = remaining[group] if ranked else len(rows) + 1
        return row not in protected, coverage_rank, baseline[row]

    for row in sorted(unknown, key=priority):
        passed = evaluate(row)
        if type(passed) is not bool:
            raise ValueError('Confirmation requires exact boolean observations')
        reads_left -= 1
        passes += passed
        if (not passed and row in protected) or passes + reads_left <= target:
            return None
        if row in strata:
            group = strata[row]
            remaining[group] -= 1
            if passed:
                uncovered.discard(group)
            elif group in uncovered and remaining[group] == 0:
                return None
    return passes
