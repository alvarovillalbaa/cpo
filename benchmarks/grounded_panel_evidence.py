"""Report paired pass differences with each case as one statistical unit."""

from collections import Counter


def sign_flip_distribution(magnitudes):
    """Count possible signed sums after swapping arm labels within each case."""
    sums = Counter({0: 1})
    for magnitude in magnitudes:
        if magnitude == 0:
            continue
        updated = Counter()
        for value, count in sums.items():
            updated[value - magnitude] += count
            updated[value + magnitude] += count
        sums = updated
    return sums


def exact_tail(deltas):
    deltas = tuple(deltas)
    observed = sum(deltas)
    distribution = sign_flip_distribution(map(abs, deltas))
    hits = sum(count for value, count in distribution.items() if value >= observed)
    trials = distribution.total()
    return {'tailAssignments': hits, 'totalAssignments': trials, 'oneSidedP': hits / trials}


def assess(outcomes, expected_cases, *, repeats, controls):
    """Pair grades on the complete sealed panel before computing effects.

    The expected cases map each task to its case IDs and critical flags. The
    exact tail assumes independent within-case arm-label swaps under the null.
    """
    controls = tuple(controls)
    arms = {'initial', 'cpo', *controls}
    if (type(repeats) is not int or repeats < 1 or not controls or len(arms) != len(controls) + 2
            or not expected_cases or outcomes.keys() != expected_cases.keys()):
        raise ValueError('Use the sealed tasks, repeats, and distinct comparison arms')

    per_case = {}
    critical_losses = dict.fromkeys(controls, 0)
    for task, cases in expected_cases.items():
        expected_cells = {(case, repeat) for case in cases for repeat in range(repeats)}
        counts = {(task, case): Counter() for case in cases}
        seen = set()
        for row in outcomes[task]:
            case, repeat, passed = row['id'], row['repeat'], row['passes']
            cell = case, repeat
            if (type(repeat) is not int or cell not in expected_cells or cell in seen
                    or type(cases[case]) is not bool or row['critical'] is not cases[case]
                    or passed.keys() != arms or any(type(value) is not bool for value in passed.values())):
                raise ValueError('Outcome cells must match the sealed case, repeat, critical flag and arms')
            seen.add(cell)
            counts[task, case].update(arm for arm, passed_case in passed.items() if passed_case)
            if row['critical'] and not passed['cpo']:
                for arm in controls:
                    critical_losses[arm] += passed[arm]
        if not expected_cells or seen != expected_cells:
            raise ValueError('Case-level evidence requires a complete matched panel')
        per_case.update(counts)

    comparisons = {}
    for arm in controls:
        deltas = [counts['cpo'] - counts[arm] for counts in per_case.values()]
        comparisons[arm] = {'additionalPasses': sum(deltas),
                            'improvedCases': sum(delta > 0 for delta in deltas),
                            'regressedCases': sum(delta < 0 for delta in deltas),
                            'tiedCases': deltas.count(0),
                            'matchedCriticalLosses': critical_losses[arm],
                            'caseSignFlip': exact_tail(deltas)}
    return {'cases': len(per_case), 'repliesPerCasePerArm': repeats, 'comparisons': comparisons,
            'jointSuperiorityP': max(result['caseSignFlip']['oneSidedP'] for result in comparisons.values())}
