"""Run search only when independent qualification can still improve the incumbent."""

from dataclasses import dataclass, replace

from .paired_qualification import QualificationDecision, QualificationObservation, certify_paired_qualification


@dataclass(frozen=True)
class PrecheckedQualificationResult:
    nominee: str | None
    decision: QualificationDecision
    precheck_evaluations: int

    @property
    def prompt(self):
        return self.decision.prompt

    @property
    def qualification_evaluations(self):
        return len(self.decision.observations)


def run_prechecked_qualification(incumbent, rows, nominate, qualify, *, repeats=1, minimum_gain=1,
                                 seed=0, evaluation_limit=None):
    """Run a zero-argument search and qualify its one nominee using separate cases.

    The precheck stops when a gain is impossible or when the incumbent has
    enough observed misses for the requested gain to remain attainable. Search
    receives no qualification evidence. The result keeps every callback reply
    in dispatch order and uses None for the nominee if the proof skipped search.
    With a cap below a full paired panel, use the ordinary qualification order
    so that spending early cannot change the decision within that cap.
    """
    rows = tuple(rows)
    if not rows or len({row.id for row in rows}) != len(rows):
        raise ValueError('Paired qualification requires distinct, nonempty rows')
    if type(repeats) is not int or repeats < 1 or type(minimum_gain) is not int or minimum_gain < 1:
        raise ValueError('Repeat and gain thresholds must be positive integers')
    if evaluation_limit is not None and (type(evaluation_limit) is not int or evaluation_limit < 0):
        raise ValueError('Evaluation limit must be a nonnegative integer')

    pairs = len(rows) * repeats
    if minimum_gain > pairs:
        decision = QualificationDecision('rejected', incumbent, (), -pairs, pairs)
        return PrecheckedQualificationResult(None, decision, 0)
    if evaluation_limit is not None and evaluation_limit < 2 * pairs:
        nominee = nominate()
        decision = certify_paired_qualification(
            incumbent, nominee, rows, qualify, repeats=repeats, minimum_gain=minimum_gain,
            seed=seed, evaluation_limit=evaluation_limit,
        )
        return PrecheckedQualificationResult(nominee, decision, 0)

    observations = []
    prefix = {}
    misses, upper = 0, pairs

    def observe(prompt, row, repeat):
        passed = qualify(prompt, row, repeat)
        if type(passed) is not bool:
            raise ValueError('The qualifier must return an exact boolean outcome')
        observations.append(QualificationObservation(prompt, row.id, repeat, passed))
        return passed

    cases = ((row, repeat) for row in rows for repeat in range(repeats))
    for row, repeat in cases:
        passed = observe(incumbent, row, repeat)
        prefix[row.id, repeat] = passed
        misses += not passed
        upper -= passed
        if upper < minimum_gain:
            decision = QualificationDecision('rejected', incumbent, tuple(observations), -pairs + misses, upper)
            return PrecheckedQualificationResult(None, decision, len(prefix))
        if misses == minimum_gain:
            break

    def reuse(prompt, row, repeat):
        key = (row.id, repeat)
        if prompt == incumbent and key in prefix:
            return prefix[key]
        return observe(prompt, row, repeat)

    nominee = nominate()
    decision = certify_paired_qualification(incumbent, nominee, rows, reuse, repeats=repeats,
                                           minimum_gain=minimum_gain, seed=seed)
    if nominee != incumbent:
        gains = sum(reply.passed == (reply.prompt == nominee) for reply in observations)
        decision = replace(decision, lower_gain=gains - pairs, upper_gain=gains + pairs - len(observations))
    return PrecheckedQualificationResult(nominee, replace(decision, observations=tuple(observations)), len(prefix))
