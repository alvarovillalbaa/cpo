"""Plan a scalar admission certificate around its remaining lookup cap."""

from dataclasses import dataclass
from functools import lru_cache

from ..paired_qualification import QualificationDecision, QualificationObservation


@dataclass(frozen=True)
class AdmissionDecision(QualificationDecision):
    used_reserve: bool | None


@lru_cache(maxsize=120_000)
def _plan(size, reserve_size, minimum, initial_budget, prior, prioritize_promotion, old_read, old_pass, new_read, new_pass):
    lower = -size + old_read - old_pass + new_pass
    upper = size - old_pass - new_read + new_pass
    if lower >= minimum:
        return 1.0, 1.0, 0.0, None
    can_tie = reserve_size and lower <= 0 <= upper
    if upper < minimum and not can_tie:
        return 0.0, 1.0, 0.0, None
    remaining = initial_budget - old_read - new_read
    if can_tie and lower == upper == 0:
        posterior = ((prior[0][0] + old_pass, prior[0][1] + size),
                     (prior[1][0] + new_pass, prior[1][1] + size))
        return (*_plan(reserve_size, 0, minimum, remaining, posterior, prioritize_promotion, 0, 0, 0, 0)[:3], None)
    if remaining == 0:
        return 0.0, 0.0, 0.0, None

    best, best_score = None, None
    for side, (read, passed) in enumerate(((old_read, old_pass), (new_read, new_pass))):
        if read == size:
            continue
        prior_passes, prior_reads = prior[side]
        chance = (prior_passes + passed + 1) / (prior_reads + read + 2)
        next_state = [old_read, old_pass, new_read, new_pass]
        next_state[2 * side] += 1
        miss = _plan(size, reserve_size, minimum, initial_budget, prior, prioritize_promotion, *next_state)
        next_state[2 * side + 1] += 1
        hit = _plan(size, reserve_size, minimum, initial_budget, prior, prioritize_promotion, *next_state)
        promotes, settles, cost = (a + chance * (b - a) for a, b in zip(miss[:3], hit[:3], strict=True))
        score = (promotes, settles, -(1 + cost)) if prioritize_promotion else (-(1 + cost),)
        if best_score is None or score > best_score:
            best = promotes, settles, 1 + cost, side
            best_score = score
    return best


def qualify_with_budget_lookahead(incumbent, challenger, rows, evaluate, *, reserve=(), minimum_gain=1,
                                  validation_counts=((0, 0), (0, 0)), evaluation_limit=None,
                                  prioritize_promotion=True):
    """Use paid priors to plan reads and exact observed bounds to admit a prompt."""
    rows, reserve = tuple(rows), tuple(reserve)
    all_rows = (*rows, *reserve)
    if (not rows or max(len(rows), len(reserve)) > 12 or len({row.id for row in all_rows}) != len(all_rows)
            or len({row.family for row in all_rows}) != 1 or any(row.critical for row in all_rows)):
        raise ValueError('Budget lookahead requires distinct noncritical cases from one family and panels of up to 12')
    if type(minimum_gain) is not int or minimum_gain < 1:
        raise ValueError('The minimum gain must be a positive integer')
    if evaluation_limit is not None and (type(evaluation_limit) is not int or evaluation_limit < 0):
        raise ValueError('The evaluation limit must be a nonnegative integer')
    counts = tuple(tuple(pair) for pair in validation_counts)
    if (len(counts) != 2 or any(len(pair) != 2 for pair in counts) or
            any(type(wins) is not int or type(reads) is not int or not 0 <= wins <= reads for wins, reads in counts)):
        raise ValueError('Use valid paid validation counts for both prompts')
    if incumbent == challenger:
        return AdmissionDecision('rejected', incumbent, (), 0, 0, False)

    hits, total = map(sum, zip(*counts))
    pooled = (round(12 * hits / total), 12) if total else (0, 0)
    prior = pooled, pooled
    prompts = incumbent, challenger
    budget = 2 * len(all_rows) if evaluation_limit is None else min(evaluation_limit, 2 * len(all_rows))
    observed = []

    for panel, extension_size, extended in ((rows, len(reserve), False), (reserve, 0, True)):
        size = len(panel)
        read, wins = [0, 0], [0, 0]
        available = min(budget - len(observed), 2 * (size + extension_size))
        while True:
            lower = -size + read[0] - wins[0] + wins[1]
            upper = size - wins[0] - read[1] + wins[1]
            can_tie = extension_size and lower <= 0 <= upper
            if can_tie and lower == upper == 0:
                prior = tuple((hits + won, count + seen) for (hits, count), won, seen in zip(prior, wins, read, strict=True))
                break
            planning_budget = available if prioritize_promotion else 2 * (size + extension_size)
            _, _, _, side = _plan(size, extension_size, minimum_gain, planning_budget, prior, prioritize_promotion,
                                  read[0], wins[0], read[1], wins[1])
            if read[0] + read[1] == available:
                side = None
            if side is None:
                status = 'promoted' if lower >= minimum_gain else 'rejected' if upper < minimum_gain and not can_tie else 'undecided'
                selected = challenger if status == 'promoted' else incumbent
                return AdmissionDecision(status, selected, tuple(observed), lower, upper,
                                         None if status == 'undecided' and can_tie else extended)
            row = panel[read[side]]
            passed = evaluate(prompts[side], row, 0)
            if type(passed) is not bool:
                raise ValueError('Qualification requires exact boolean replies')
            read[side] += 1
            wins[side] += passed
            observed.append(QualificationObservation(prompts[side], row.id, 0, passed))
    raise RuntimeError('A complete scalar proof must settle its decision')
