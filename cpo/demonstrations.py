"""Build disjoint demonstration bundles with broad input-condition coverage."""

from collections import defaultdict, deque
from random import Random


def stratified_demo_bundles(cases, strata, *, bundle_size, bundle_count, seed=0):
    """Visit distinct declared strata before taking a second case from one.

    Case IDs and their strata must be hashable. Take scarce strata first
    on the first visit and abundant strata when revisiting. Seeded order
    resolves ties and orders cases within each stratum.
    Each input case can appear at most once across all bundles.
    """
    cases = list(cases)
    if type(bundle_size) is not int or bundle_size < 1 or type(bundle_count) is not int or bundle_count < 1:
        raise ValueError('Demonstration bundle size and count must be positive integers')
    if (len(cases) < bundle_size * bundle_count or len(set(cases)) != len(cases)
            or any(case not in strata for case in cases)):
        raise ValueError('Supply enough distinct demonstration cases with declared strata')
    Random(seed).shuffle(cases)
    available = defaultdict(deque)
    for case in cases:
        available[strata[case]].append(case)
    bundles = []
    for _ in range(bundle_count):
        used = set()
        bundle = []
        for _ in range(bundle_size):
            group = min(available, key=lambda key: (
                key in used, -len(available[key]) if key in used else len(available[key]),
            ))
            bundle.append(available[group].popleft())
            used.add(group)
            if not available[group]:
                del available[group]
        bundles.append(tuple(bundle))
    return tuple(bundles)
