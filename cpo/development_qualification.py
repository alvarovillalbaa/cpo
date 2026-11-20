"""Stop a paired development panel once its comparison gate cannot pass."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Literal


CANDIDATE, INITIAL = 'cpo', 'initial'


@dataclass(frozen=True)
class Sample:
    task: str
    case: str
    repeat: int
    critical: bool
    arms: tuple[str, ...]


@dataclass(frozen=True)
class QualificationResult:
    status: Literal['qualified', 'rejected']
    observations: tuple[bool, ...]
    reasons: tuple[dict, ...]


def rejection_reasons(schedule, observed, gate, costs):
    """Test the most favorable completion for the candidate of a validated schedule."""
    cells = defaultdict(dict)
    for index, sample in enumerate(schedule):
        passed = observed[index] if index < len(observed) else CANDIDATE in sample.arms
        cells[sample.task, sample.case, sample.repeat, sample.critical].update(dict.fromkeys(sample.arms, passed))
    scores = Counter((task, arm) for (task, _, _, _), row in cells.items() for arm, passed in row.items() if passed)
    tasks = sorted({task for task, _, _, _ in cells})
    reasons = [{'gate': 'task-floor', 'task': task, 'maximumPasses': scores[task, CANDIDATE],
                'requiredPasses': gate['minimumPassesPerTask']}
               for task in tasks if scores[task, CANDIDATE] < gate['minimumPassesPerTask']]

    for arm in sorted({*costs, INITIAL} - {CANDIDATE}):
        failed_tasks = [task for task in tasks if scores[task, CANDIDATE] < scores[task, arm]]
        if failed_tasks:
            reasons.append({'gate': 'task-regression', 'arm': arm, 'tasks': failed_tasks})
        if any(critical and row[arm] and not row[CANDIDATE] for (_, _, _, critical), row in cells.items()):
            reasons.append({'gate': 'critical-regression', 'arm': arm})
        if arm == INITIAL:
            continue
        deltas = Counter()
        for (task, case, _, _), row in cells.items():
            deltas[task, case] += row[CANDIDATE] - row[arm]
        best_gain = sum(deltas.values())
        efficiency_possible = (costs[arm] > 0 and
                               100 * costs[CANDIDATE] <= costs[arm] * gate['maxSearchCostPercentForEfficiency'] and
                               all(delta >= 0 for delta in deltas.values()))
        if best_gain < gate['minimumAddedPasses'] and not efficiency_possible:
            reasons.append({'gate': 'quality-or-efficiency', 'arm': arm, 'maximumAddedPasses': best_gain})
    return reasons


def check_schedule(schedule, costs, gate):
    if (CANDIDATE not in costs or INITIAL in costs or len(costs) < 2
            or any(type(amount) is not int or amount < 0 for amount in costs.values())):
        raise ValueError('Supply nonnegative integer search costs for CPO and at least one separate comparator')
    for key in ('minimumPassesPerTask', 'minimumAddedPasses', 'maxSearchCostPercentForEfficiency'):
        amount = gate.get(key)
        if type(amount) is not int or amount < 0 or key.startswith('max') and amount > 100:
            raise ValueError(f'Invalid qualification gate threshold {key}')
    arms = {*costs, INITIAL}
    cells, critical, repeats = defaultdict(set), {}, defaultdict(set)
    for sample in schedule:
        if (not isinstance(sample, Sample) or type(sample.repeat) is not int or sample.repeat < 0
                or type(sample.critical) is not bool or not isinstance(sample.arms, tuple) or not sample.arms):
            raise ValueError('A planned reply requires a case, repeat, critical flag, and arm tuple')
        case = sample.task, sample.case
        if critical.setdefault(case, sample.critical) != sample.critical:
            raise ValueError('All repeats of a case need the same critical flag')
        shared = set(sample.arms)
        cell = cells[case, sample.repeat]
        if len(shared) != len(sample.arms) or not shared <= arms or shared & cell:
            raise ValueError('Each arm may appear only once for a case and repeat')
        cell.update(shared)
        repeats[case].add(sample.repeat)
    if not cells or any(cell != arms for cell in cells.values()):
        raise ValueError('The schedule must cover every arm on every case and repeat')
    if any(indices != set(range(len(indices))) for indices in repeats.values()):
        raise ValueError('Case repeats must start at zero and be contiguous')


def run_development_qualification(schedule, observe, *, gate, search_costs):
    """Call observe(sample) at most once per physical sample in the supplied order.

    The complete schedule must partition the arms on every case and repeat.
    The observer returns one exact boolean shared by all arms in that sample.
    Observations correspond to the paid prefix. A positive decision always
    requires the complete schedule. Callback exceptions propagate immediately.
    """
    schedule, costs, gate = tuple(schedule), dict(search_costs), dict(gate)
    check_schedule(schedule, costs, gate)
    observed = []
    for sample in schedule:
        reasons = rejection_reasons(schedule, observed, gate, costs)
        if reasons:
            return QualificationResult('rejected', tuple(observed), tuple(reasons))
        passed = observe(sample)
        if type(passed) is not bool:
            raise ValueError('A qualification sample requires an exact boolean outcome')
        observed.append(passed)
    reasons = rejection_reasons(schedule, observed, gate, costs)
    return QualificationResult('rejected' if reasons else 'qualified', tuple(observed), tuple(reasons))
