"""Select fixed-size validation panels with declared critical strata."""

from collections.abc import Iterable, Mapping
from random import Random

from .optimizer import Row, balanced_order


def sample_validation_panel(
    candidates: Iterable[Row],
    *,
    size: int,
    critical_count: int,
    critical_strata: Mapping[str, str] | None = None,
    seed: int = 0,
) -> list[Row]:
    """Select a seeded panel with an exact critical count and optional coverage.

    Strata are caller-supplied case labels keyed by row ID. The sampler
    visits each represented critical stratum before taking a second case
    from any. The ordinary sample is independent of critical stratification.
    """
    pool = list(candidates)
    if len({row.id for row in pool}) != len(pool):
        raise ValueError('Validation candidates require distinct row IDs')
    if type(size) is not int or type(critical_count) is not int or not 0 <= critical_count <= size or size == 0:
        raise ValueError('Provide a positive panel size and a critical quota within it')

    generator = Random(seed)
    generator.shuffle(pool)
    critical = [row for row in pool if row.critical]
    ordinary = [row for row in pool if not row.critical]
    if len(critical) < critical_count or len(ordinary) < size - critical_count:
        raise ValueError('The validation pool cannot meet both quotas')

    if critical_count and critical_strata is not None:
        if any(not critical_strata.get(row.id) for row in critical):
            raise ValueError('Each critical candidate requires a declared stratum')
        by_id = {row.id: row for row in critical}
        order = balanced_order([Row(row.id, critical_strata[row.id]) for row in critical], seed)
        critical = [by_id[row.id] for row in order]

    panel = critical[:critical_count] + ordinary[:size - critical_count]
    generator.shuffle(panel)
    return panel
