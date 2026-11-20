"""Compare certified opening dominance and staged CPO with split-safe GEPA."""

from functools import partial

from . import grounded_staged_policy_comparison as comparison
from .grounded_staged_policy_comparison import ARCHIVE_FILES, ARMS, grade


OPENING = {'certify_validation': True, 'certify_dominance': True}
prepare = partial(comparison.prepare, **OPENING)
run = partial(comparison.run, **OPENING)
replay = partial(comparison.replay, **OPENING)


if __name__ == '__main__':
    comparison.main(**OPENING)
