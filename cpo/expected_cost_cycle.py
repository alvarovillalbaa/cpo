"""Run a fixed-pool cycle with expected-cost qualification."""

from .expected_qualification import certify_expected_qualification
from .fixed_pool_cycle import FixedPoolCycleResult, run_fixed_pool_cycle
from .paired_qualification import certify_paired_qualification


def run_expected_cost_fixed_pool_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                       metric_limit, qualify, screen='deferred-first-gain', repeats=1,
                                       minimum_gain=1, seed=0, qualification_limit=None):
    """Use paid validation replies to order the independent exact certificate.

    Search uses the existing fixed-pool screen and budget. A qualification
    cap smaller than a full paired panel retains the original seeded order.
    The result contains the qualification replies in actual callback order.
    """
    if qualification_limit is not None and (type(qualification_limit) is not int or qualification_limit < 0):
        raise ValueError('Qualification limit must be a nonnegative integer')
    qualification_rows = tuple(qualification_rows)
    validation_replies = {}

    def observe(prompt, row):
        reply = evaluate(prompt, row)
        validation_replies.setdefault(prompt, {})[row.id] = reply.passed
        return reply

    # A zero qualification limit stops the existing cycle at its nomination.
    nomination = run_fixed_pool_cycle(
        incumbent, candidates, validation, qualification_rows, observe,
        metric_limit=metric_limit, qualify=qualify, screen=screen, repeats=repeats,
        minimum_gain=minimum_gain, seed=seed, qualification_limit=0,
    )
    if nomination.qualification is None:
        return nomination

    challenger = nomination.search.prompt
    options = dict(repeats=repeats, minimum_gain=minimum_gain, seed=seed, evaluation_limit=qualification_limit)
    if qualification_limit is not None and qualification_limit < 2 * repeats * len(qualification_rows):
        decision = certify_paired_qualification(incumbent, challenger, qualification_rows, qualify, **options)
    else:
        counts = tuple((sum(replies.values()), len(replies)) for replies in
                       (validation_replies.get(incumbent, {}), validation_replies.get(challenger, {})))
        decision = certify_expected_qualification(
            incumbent, challenger, qualification_rows, qualify, validation_counts=counts, **options,
        )
    return FixedPoolCycleResult(nomination.search, decision)
