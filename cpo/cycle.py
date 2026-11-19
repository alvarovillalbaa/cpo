"""Select a challenger on search data and qualify it against the incumbent."""

from collections import Counter
from dataclasses import dataclass
from random import Random

from .optimizer import Result, search


@dataclass(frozen=True)
class MatchedOutcome:
    row_id: str
    repeat: int
    critical: bool
    incumbent_passed: bool
    challenger_passed: bool


@dataclass(frozen=True)
class CycleResult:
    prompt: str
    search: Result
    outcomes: tuple[MatchedOutcome, ...]
    promoted: bool

    @property
    def qualification_evaluations(self):
        return 2 * len(self.outcomes)


def run_cycle(incumbent, train, validation, holdout, evaluate, propose, *,
              metric_limit, rounds, train_per_round, qualify, repeats=1, minimum_gain=1, seed=0, field_credit=False,
              opening_pair=None):
    """Run one cycle. The qualifier returns a bool for each prompt, row, and repeat."""
    if type(repeats) is not int or repeats < 1 or type(minimum_gain) is not int or minimum_gain < 1:
        raise ValueError("Qualification repeat and gain thresholds must be positive integers")
    train, validation, holdout = tuple(train), tuple(validation), tuple(holdout)
    ids = [row.id for row in (*train, *validation, *holdout)]
    if not holdout or len(set(ids)) != len(ids):
        raise ValueError("Search and qualification require disjoint row IDs and a nonempty holdout")

    candidate = search(incumbent, train, validation, evaluate, propose, metric_limit=metric_limit,
                       rounds=rounds, train_per_round=train_per_round, seed=seed, adaptive=True, field_credit=field_credit,
                       opening_pair=opening_pair)
    if candidate.prompt == incumbent:
        return CycleResult(incumbent, candidate, (), False)

    outcomes = []
    gain_by_family = Counter()
    order = Random(seed)
    for row in holdout:
        for repeat in range(repeats):
            prompts = [incumbent, candidate.prompt]
            order.shuffle(prompts)
            observations = {prompt: qualify(prompt, row, repeat) for prompt in prompts}
            if any(type(passed) is not bool for passed in observations.values()):
                raise ValueError("The qualifier must return an exact boolean outcome")
            outcomes.append(MatchedOutcome(row.id, repeat, row.critical,
                                           observations[incumbent], observations[candidate.prompt]))
            gain_by_family[row.family] += observations[candidate.prompt] - observations[incumbent]

    critical_loss = any(result.critical and result.incumbent_passed and not result.challenger_passed
                        for result in outcomes)
    promoted = (sum(gain_by_family.values()) >= minimum_gain and not critical_loss
                and all(gain >= 0 for gain in gain_by_family.values()))
    return CycleResult(candidate.prompt if promoted else incumbent, candidate, tuple(outcomes), promoted)
