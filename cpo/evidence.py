"""Compatibility checks for component feedback from a measured prompt."""

from collections.abc import Collection, Mapping


def can_reuse_component_feedback(
    source: Mapping[str, str],
    current: Mapping[str, str],
    component: str,
    *,
    dependencies: Collection[str] | None = None,
) -> bool:
    """Require matching values for the edited component and all declared dependencies.

    Omit the scope when dependencies are unknown to require the exact source
    prompt. Pass an empty collection for feedback known to be component-local.
    """
    if source.keys() != current.keys() or component not in source:
        return False
    if dependencies is None:
        return source == current
    return all(name in source and source[name] == current[name] for name in (component, *dependencies))
