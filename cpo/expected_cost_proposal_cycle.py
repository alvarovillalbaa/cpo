"""Qualify the result of proposal-driven CPO with an exact early stop."""

from dataclasses import dataclass

from .expected_qualification import certify_expected_qualification
from .optimizer import Result, search
from .paired_qualification import QualificationDecision, certify_paired_qualification


@dataclass(frozen=True)
class ExpectedCostProposalCycleResult:
    search: Result
    qualification: QualificationDecision | None

    @property
    def prompt(self):
        return self.search.prompt if self.qualification is None else self.qualification.prompt

    @property
    def promoted(self):
        return self.qualification is not None and self.qualification.status == 'promoted'

    @property
    def qualification_evaluations(self):
        return 0 if self.qualification is None else len(self.qualification.observations)


def run_expected_cost_proposal_cycle(incumbent, train, validation, holdout, evaluate, propose, *,
                                     metric_limit, rounds, train_per_round, qualify, repeats=1,
                                     minimum_gain=1, seed=0, field_credit=False, opening_pair=None,
                                     qualification_limit=None):
    """Run the existing proposal search and record its exact qualification prefix.

    Training feedback goes to the proposer through the normal search path.
    Only paid validation replies inform the order of the independent proof.
    """
    if type(repeats) is not int or repeats < 1 or type(minimum_gain) is not int or minimum_gain < 1:
        raise ValueError('Qualification repeat and gain thresholds must be positive integers')
    if qualification_limit is not None and (type(qualification_limit) is not int or qualification_limit < 0):
        raise ValueError('Qualification limit must be a nonnegative integer')
    train, validation, holdout = tuple(train), tuple(validation), tuple(holdout)
    row_ids = [row.id for row in (*train, *validation, *holdout)]
    if not holdout or len(set(row_ids)) != len(row_ids):
        raise ValueError('Search and qualification require disjoint row IDs and a nonempty holdout')

    validation_ids = {row.id for row in validation}
    validation_replies = {}

    def observe(prompt, row):
        reply = evaluate(prompt, row)
        if type(reply.passed) is not bool:
            raise ValueError('Search observations require an exact boolean outcome')
        if row.id in validation_ids:
            validation_replies.setdefault(prompt, {})[row.id] = reply.passed
        return reply

    candidate = search(incumbent, train, validation, observe, propose, metric_limit=metric_limit,
                       rounds=rounds, train_per_round=train_per_round, seed=seed,
                       adaptive=True, field_credit=field_credit, opening_pair=opening_pair)
    if candidate.prompt == incumbent:
        return ExpectedCostProposalCycleResult(candidate, None)

    options = dict(repeats=repeats, minimum_gain=minimum_gain, seed=seed, evaluation_limit=qualification_limit)
    if qualification_limit is not None and qualification_limit < 2 * repeats * len(holdout):
        decision = certify_paired_qualification(incumbent, candidate.prompt, holdout, qualify, **options)
    else:
        counts = tuple((sum(replies.values()), len(replies)) for replies in
                       (validation_replies[incumbent], validation_replies[candidate.prompt]))
        decision = certify_expected_qualification(
            incumbent, candidate.prompt, holdout, qualify, validation_counts=counts, **options,
        )
    return ExpectedCostProposalCycleResult(candidate, decision)
