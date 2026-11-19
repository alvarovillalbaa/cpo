"""Certify a paired qualification decision using only observed outcomes."""

from collections import Counter
from dataclasses import dataclass
from random import Random
from typing import Literal


@dataclass(frozen=True)
class QualificationObservation:
    prompt: str
    row_id: str
    repeat: int
    passed: bool


@dataclass(frozen=True)
class QualificationDecision:
    status: Literal['promoted', 'rejected', 'undecided']
    prompt: str
    observations: tuple[QualificationObservation, ...]
    lower_gain: int
    upper_gain: int


def certify_paired_qualification(incumbent, challenger, rows, qualify, *, repeats=1, minimum_gain=1,
                                 seed=0, evaluation_limit=None):
    """Match the full cycle gate while stopping as soon as no suffix can change it.

    Rows must be qualification cases disjoint from search. The callback returns
    an exact bool per prompt, row and repeat. The result contains only the
    observed prefix, including a first reply whose counterpart was unnecessary.
    An exhausted evaluation limit can leave the decision undecided.
    """
    rows = tuple(rows)
    if not rows or len({row.id for row in rows}) != len(rows):
        raise ValueError('Paired qualification requires distinct, nonempty rows')
    if type(repeats) is not int or repeats < 1 or type(minimum_gain) is not int or minimum_gain < 1:
        raise ValueError('Repeat and gain thresholds must be positive integers')
    if evaluation_limit is not None and (type(evaluation_limit) is not int or evaluation_limit < 0):
        raise ValueError('Evaluation limit must be a nonnegative integer')
    if incumbent == challenger:
        return QualificationDecision('rejected', incumbent, (), 0, 0)

    high = Counter(row.family for row in rows)
    low = Counter({family: -count * repeats for family, count in high.items()})
    high = Counter({family: count * repeats for family, count in high.items()})
    total_low, total_high = -len(rows) * repeats, len(rows) * repeats
    possible_critical_losses = sum(row.critical for row in rows) * repeats
    observations = []
    order = Random(seed)

    def finish(status):
        selected = challenger if status == 'promoted' else incumbent
        return QualificationDecision(status, selected, tuple(observations), total_low, total_high)

    if minimum_gain > total_high:
        return finish('rejected')
    for row in rows:
        family = row.family
        for repeat in range(repeats):
            prompts = [incumbent, challenger]
            order.shuffle(prompts)
            pair = {}
            could_lose = row.critical
            for prompt in prompts:
                if len(observations) == evaluation_limit:
                    return finish('undecided')
                passed = qualify(prompt, row, repeat)
                if type(passed) is not bool:
                    raise ValueError('The qualifier must return an exact boolean outcome')
                observations.append(QualificationObservation(prompt, row.id, repeat, passed))
                pair[prompt] = passed

                # An observation resolves one binary contribution to the gain.
                if passed == (prompt == challenger):
                    low[family] += 1
                    total_low += 1
                else:
                    high[family] -= 1
                    total_high -= 1
                if could_lose and (pair.get(incumbent) is False or pair.get(challenger) is True):
                    possible_critical_losses -= 1
                    could_lose = False
                critical_loss = row.critical and pair.get(incumbent) is True and pair.get(challenger) is False
                if critical_loss or total_high < minimum_gain or high[family] < 0:
                    return finish('rejected')
                if (possible_critical_losses == 0 and total_low >= minimum_gain and
                        all(value >= 0 for value in low.values())):
                    return finish('promoted')

    raise RuntimeError('A fully observed qualification must have a decision')
