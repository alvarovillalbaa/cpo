"""Compare both exact paired rewrite orders on the same paid samples."""

from functools import partial

from . import grounded_staged_policy_comparison as comparison


OPENING = dict(certify_validation=True, certify_dominance=True, paired_rewrite=True, charge_priority=True)
ARMS = (*comparison.ARMS, comparison.PAIRED, comparison.CHARGED)
ARCHIVE_FILES = comparison.ARCHIVE_FILES
PricedReply = comparison.PricedReply
prepare = partial(comparison.prepare, **OPENING)
run = partial(comparison.run, **OPENING)
replay = partial(comparison.replay, **OPENING)
grade = partial(comparison.grade, paired_rewrite=True, charge_priority=True)


if __name__ == '__main__':
    comparison.main(**OPENING)
