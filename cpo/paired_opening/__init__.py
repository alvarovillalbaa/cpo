"""Take the first supplied opening that clears an exact paired proof."""

from ..family_qualification import certify_family_qualification
from ..fixed_pool_cycle import FixedPoolCycleResult
from ..optimizer import ProposalPair
from ..single_finalist import FinalistResult

__all__ = ['run_paired_opening_cycle']


def run_paired_opening_cycle(incumbent, validation, qualification_rows, evaluate, *, opening_pair,
                             metric_limit, qualify, repeats=1, minimum_gain=1, seed=0,
                             qualification_limit=None):
    """Try the rewrite before the repair, then independently qualify one nominee.

    Search requires a strict exact gain, nonregression in each validation
    family, and preserved critical passes. The search ledger reuses incumbent
    grades between the two proofs. Each proof starts only when its remaining
    reads fit the cap. Qualification uses disjoint rows and has its own cap.
    """
    if not isinstance(opening_pair, ProposalPair):
        raise ValueError('The paired opening requires a precomputed ProposalPair')
    prompts = (incumbent, opening_pair.rewrite, opening_pair.repair)
    if any(not isinstance(prompt, str) or not prompt.strip() for prompt in prompts) or len(set(prompts)) != 3:
        raise ValueError('Incumbent, rewrite and repair must be distinct nonempty prompts')
    validation, qualification_rows = tuple(validation), tuple(qualification_rows)
    ids = [row.id for row in (*validation, *qualification_rows)]
    if not validation or not qualification_rows or len(set(ids)) != len(ids):
        raise ValueError('Validation and qualification need nonempty panels with distinct, disjoint row IDs')
    if type(metric_limit) is not int or metric_limit < 0:
        raise ValueError('The search cap must be a nonnegative integer')
    if type(repeats) is not int or repeats < 1 or type(minimum_gain) is not int or minimum_gain < 1:
        raise ValueError('Qualification repeat and gain thresholds must be positive integers')
    if qualification_limit is not None and (type(qualification_limit) is not int or qualification_limit < 0):
        raise ValueError('Qualification limit must be a nonnegative integer')

    search = {}

    def observe(prompt, row, _repeat):
        key = prompt, row.id
        if key not in search:
            search[key] = evaluate(prompt, row).passed
        return search[key]

    for challenger in prompts[1:]:
        pending = sum((prompt, row.id) not in search for prompt in (incumbent, challenger) for row in validation)
        if len(search) + pending > metric_limit:
            break
        proof = certify_family_qualification(incumbent, challenger, validation, observe, seed=seed)
        if proof.status == 'promoted':
            selection = FinalistResult(challenger, challenger, len(search))
            decision = certify_family_qualification(
                incumbent, challenger, qualification_rows, qualify, repeats=repeats, minimum_gain=minimum_gain,
                seed=seed, evaluation_limit=qualification_limit,
            )
            return FixedPoolCycleResult(selection, decision)
    return FixedPoolCycleResult(FinalistResult(incumbent, None, len(search)), None)
