"""Conservative composition for prompts represented by named components."""

from collections.abc import Mapping


def merge_components(ancestor: Mapping[str, str], left: Mapping[str, str],
                     right: Mapping[str, str]) -> dict[str, str] | None:
    """Return a new combination of compatible edits from a common ancestor.

    Both parents must contribute an edit. Conflicting edits to the same
    component return None. The caller still needs to validate the result.
    """
    if not ancestor or ancestor.keys() != left.keys() or ancestor.keys() != right.keys():
        raise ValueError('Ancestor and parents need the same nonempty set of component names')
    merged = {}
    for component, original in ancestor.items():
        a, b = left[component], right[component]
        if a != b and a != original and b != original:
            return None
        merged[component] = a if b == original else b
    return None if merged == left or merged == right else merged
