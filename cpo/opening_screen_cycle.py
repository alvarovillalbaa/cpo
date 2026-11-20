"""Screen a supplied opening pair and qualify the finalist with fresh evidence."""

from collections import Counter
from dataclasses import replace

from .expected_cost_proposal_cycle import ExpectedCostProposalCycleResult
from .expected_qualification import certify_expected_qualification
from .optimizer import ProposalPair, search
from .paired_qualification import certify_paired_qualification


def run_opening_screen_cycle(incumbent, train, validation, holdout, evaluate, *, opening_pair,
                             metric_limit, qualify, screen_rows=8, repeats=1, minimum_gain=1,
                             seed=0, field_credit=False, qualification_limit=None):
    """Search only the supplied opening, then require full validation and qualification.

    The first screen_rows validation cases drive search. Budget the complete
    finalist and incumbent before screening. A single nominee can qualify
    after an exact validation gain with no critical or family regression.
    """
    if not isinstance(opening_pair, ProposalPair):
        raise ValueError('An opening screen requires a precomputed ProposalPair')
    if type(screen_rows) is not int or screen_rows < 1:
        raise ValueError('Screen size must be a positive integer')
    if type(repeats) is not int or repeats < 1 or type(minimum_gain) is not int or minimum_gain < 1:
        raise ValueError('Qualification repeat and gain thresholds must be positive integers')
    if qualification_limit is not None and (type(qualification_limit) is not int or qualification_limit < 0):
        raise ValueError('Qualification limit must be a nonnegative integer')

    train, validation, holdout = tuple(train), tuple(validation), tuple(holdout)
    ids = [row.id for row in (*train, *validation, *holdout)]
    if not train or not validation or not holdout or len(set(ids)) != len(ids):
        raise ValueError('Search and qualification require nonempty cohorts with disjoint row IDs')
    if type(metric_limit) is not int or metric_limit < 2 * len(validation):
        raise ValueError('The search budget must fund complete validation of a pair')
    if field_credit and any(type(row.fields) is not int or row.fields < 1 for row in (*train, *validation)):
        raise ValueError('Field-aware rows require a positive field count')

    observations = {}

    def observe(prompt, row):
        key = (prompt, row.id)
        if key not in observations:
            if len(observations) >= metric_limit:
                raise RuntimeError('Search evaluation budget exhausted')
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Search observations require an exact boolean outcome')
            if field_credit and (type(reply.matched_fields) is not int
                                 or not 0 <= reply.matched_fields <= row.fields
                                 or reply.passed != (reply.matched_fields == row.fields)):
                raise ValueError('Field observations must match the row capacity and exact-pass decision')
            observations[key] = reply
        return observations[key]

    def unused_proposer(*_):
        raise RuntimeError('An opening screen uses only the precomputed pair')

    prefix, suffix = validation[:screen_rows], validation[screen_rows:]
    result = search(incumbent, train, prefix, observe, unused_proposer, opening_pair=opening_pair,
                    metric_limit=metric_limit - 2 * len(suffix), rounds=1, train_per_round=1,
                    adaptive=True, seed=seed, field_credit=field_credit)
    challenger = result.prompt
    if challenger == incumbent:
        return ExpectedCostProposalCycleResult(result, None)

    incumbent_passes, challenger_passes = 0, 0
    gain_by_family = Counter()
    critical_loss = False
    for row in validation:
        candidate_passed = observe(challenger, row).passed
        incumbent_passed = observe(incumbent, row).passed
        challenger_passes += candidate_passed
        incumbent_passes += incumbent_passed
        gain_by_family[row.family] += candidate_passed - incumbent_passed
        critical_loss |= row.critical and incumbent_passed and not candidate_passed
    accepted = challenger_passes > incumbent_passes and not critical_loss and min(gain_by_family.values()) >= 0
    result = replace(result, prompt=challenger if accepted else incumbent, evaluations=len(observations),
                     events=[*result.events, {'kind': 'full-validation', 'prompt': challenger,
                                             'accepted': accepted, 'critical_loss': critical_loss,
                                             'gain_by_family': dict(gain_by_family)}])
    if not accepted:
        return ExpectedCostProposalCycleResult(result, None)

    options = dict(repeats=repeats, minimum_gain=minimum_gain, seed=seed, evaluation_limit=qualification_limit)
    if qualification_limit is not None and qualification_limit < 2 * repeats * len(holdout):
        decision = certify_paired_qualification(incumbent, challenger, holdout, qualify, **options)
    else:
        counts = ((incumbent_passes, len(validation)), (challenger_passes, len(validation)))
        decision = certify_expected_qualification(incumbent, challenger, holdout, qualify,
                                                 validation_counts=counts, **options)
    return ExpectedCostProposalCycleResult(result, decision)
