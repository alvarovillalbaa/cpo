"""Compare the paired field rewrite with the other CPO and GEPA policies."""

from functools import partial

from . import grounded_staged_policy_comparison as comparison
from .grounded_staged_policy_comparison import ARCHIVE_FILES


OPENING = {'certify_validation': True, 'certify_dominance': True, 'paired_rewrite': True}
ARMS = (*comparison.ARMS, comparison.PAIRED)
prepare = partial(comparison.prepare, **OPENING)
run = partial(comparison.run, **OPENING)
replay = partial(comparison.replay, **OPENING)
grade = partial(comparison.grade, paired_rewrite=True)


if __name__ == '__main__':
    comparison.main(**OPENING)
