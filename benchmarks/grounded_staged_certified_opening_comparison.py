"""Compare certified opening validation and staged CPO with split-safe GEPA."""

from functools import partial

from . import grounded_staged_policy_comparison as comparison
from .grounded_staged_policy_comparison import ARCHIVE_FILES, ARMS, grade


prepare = partial(comparison.prepare, certify_validation=True)
run = partial(comparison.run, certify_validation=True)
replay = partial(comparison.replay, certify_validation=True)


if __name__ == '__main__':
    comparison.main(certify_validation=True)
