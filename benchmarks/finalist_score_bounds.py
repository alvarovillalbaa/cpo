"""Prove the winner of an already funded, two-finalist validation race."""

from collections import Counter

from benchmarks.balanced_finalist_race import matched_prefix
from cpo.single_finalist import FinalistResult


def select_by_bounds(incumbent, candidates, rows, evaluate, *, metric_limit, width, screen_rows,
                     defer_incumbent, audit):
    """Keep the exact race's shortlist, critical gate and deterministic tie order."""
    rows, candidates = tuple(rows), tuple(candidates)[:width]
    count = len(rows)
    if (not 0 < screen_rows <= count or len({row.id for row in rows}) != count
            or len(set((incumbent, *candidates))) != 1 + len(candidates)):
        raise ValueError('Provide a distinct roster and enough distinct rows for its screen')
    finalists = min(2, len(candidates))
    reserve = count + len(candidates) * screen_rows + finalists * (count - screen_rows)
    if metric_limit < reserve:
        raise ValueError('The original exact race must be fully funded')
    if not candidates:
        return FinalistResult(incumbent, None, 0)

    known = {prompt: {} for prompt in (incumbent, *candidates)}
    case_passes, case_reads, stage_reads = Counter(), Counter(), Counter()
    calls, incumbent_passes = 0, 0

    def observe(prompt, row, stage):
        nonlocal calls
        evidence = known[prompt]
        if row.id not in evidence:
            if calls >= metric_limit:
                raise ValueError('The bound race exceeded its funded lookups')
            passed = evaluate(prompt, row).passed
            if type(passed) is not bool:
                raise ValueError('Score bounds require exact boolean outcomes')
            evidence[row.id] = passed
            case_passes[row.id] += passed
            case_reads[row.id] += 1
            calls += 1
            stage_reads[stage] += 1
        return evidence[row.id]

    half = screen_rows // 2
    for row in rows:
        incumbent_passes += observe(incumbent, row, 'incumbentLookups')
        measured = len(known[incumbent])
        if defer_incumbent and half <= min(incumbent_passes, measured - incumbent_passes) and measured >= screen_rows:
            # For an odd screen size the remaining row can be the first case
            # outside the two equal groups, even if it has no measured reply.
            break
    if incumbent_passes == count:
        audit.update(stage_reads)
        return FinalistResult(incumbent, None, calls)

    if len(known[incumbent]) == count:
        prefix = matched_prefix(rows, known[incumbent], screen_rows)[:screen_rows]
    else:
        early = [row for row in rows if row.id in known[incumbent]]
        first = matched_prefix(early, known[incumbent], screen_rows)[:2 * half]
        prefix = (first + [row for row in rows if row not in first])[:screen_rows]
    screened = {prompt: sum(observe(prompt, row, 'screenLookups') for row in prefix) for prompt in candidates}
    ordered = (incumbent, *sorted(candidates, key=screened.__getitem__, reverse=True)[:finalists])
    ranks = {prompt: -i for i, prompt in enumerate(ordered)}
    protected = {row.id for row in rows if row.critical and observe(incumbent, row, 'incumbentLookups')}

    while True:
        possible, confirmed = {}, {}
        for prompt in ordered:
            evidence = known[prompt]
            if any(evidence.get(case) is False for case in protected):
                continue
            low = sum(evidence.values())
            unknown = count - len(evidence)
            possible[prompt] = (low + unknown, ranks[prompt])
            if protected <= evidence.keys():
                confirmed[prompt] = (low, ranks[prompt])

        first = max(confirmed, key=confirmed.__getitem__)
        if all(prompt == first or confirmed[first] >= bound for prompt, bound in possible.items()):
            audit.update(stage_reads)
            return FinalistResult(first, first if first != incumbent else None, calls)

        remaining = {prompt for prompt, upper in possible.items() if prompt == first or upper > confirmed[first]}

        def estimated(prompt):
            observed = known[prompt]
            passed = sum(observed.values())
            estimate = passed + (count - len(observed)) * (passed + 1) / (len(observed) + 2)
            return estimate, ranks[prompt]

        lead = max(remaining, key=estimated)
        rival = max(remaining - {lead}, key=possible.__getitem__)

        def case_rate(row):
            return (case_passes[row.id] + 1) / (case_reads[row.id] + 2)

        reads = []
        for prompt, gain in ((lead, True), (rival, False)):
            pending = [row for row in rows if row.id not in known[prompt]]
            if pending:
                case = max(pending, key=lambda row: (row.id in protected,
                                                      case_rate(row) if gain else 1 - case_rate(row)))
                value = case_rate(case) if gain else 1 - case_rate(case)
                reads.append((prompt, case, case.id in protected, value))
        prompt, case, _, _ = max(reads, key=lambda item: item[2:])
        stage = 'incumbentLookups' if prompt == incumbent else 'finalistLookups'
        observe(prompt, case, stage)
