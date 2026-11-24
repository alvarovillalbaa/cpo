"""T2 mock case IDs and native search transitions."""

from benchmarks.continuous_archive_routing import Span, extend_spans, stages, transfer


def test_compressed_cap_intervals_match_individual_rollouts_with_incumbent_changes():
    def point(prompt, cost):
        return {'paidLookups': cost}, ('unused', 'unused', 'unused', prompt), ()

    transitions = (
        {'start': {3: point('start', 1), 5: point('first', 4), 9: point('start', 2)}},
        {'start': {3: point('start', 1), 4: point('second', 4), 7: point('second', 4)},
         'first': {3: point('first', 1), 5: point('other', 6), 8: point('first', 5)}},
        {'start': {3: point('start', 1)}, 'second': {3: point('second', 2)},
         'other': {3: point('other', 5), 7: point('third', 7)}, 'first': {3: point('third', 5)}},
    )
    spans = [Span(3, 13, 'start')]
    for outcomes in transitions:
        spans = extend_spans(spans, outcomes.__getitem__)
    actual = {cap: (span.prompt, span.paid) for span in spans for cap in range(span.lower, span.upper)}
    expected = {}
    for cap in range(3, 13):
        prompt, paid = 'start', 0
        for step in transitions:
            options = step[prompt]
            point, trace, _ = options[max(boundary for boundary in options if boundary <= cap)]
            prompt = trace[3]
            paid += point['paidLookups']
        expected[cap] = prompt, paid
    assert actual == expected
    for before, after in zip(spans, spans[1:]):
        assert before.upper == after.lower
        assert (before.prompt, before.paid) != (after.prompt, after.paid)


def test_cycles_preserve_first_layout_and_allocate_disjoint_case_roles_and_prompts():
    plan = {'caseCounts': (10, 6, 4), 'challengers': 8, 'cycles': 3}
    start, layout = stages('task', 100, 100, 237, plan)
    old, old_roster, old_roles = transfer.layouts.schedule('task', 100, 100, 237, plan)
    assert (start, layout[0]) == (old, (237, old_roster, old_roles))
    seen_cases, seen_prompts = set(old_roles[-1]), {start}
    for _, roster, roles in layout:
        cases = {case for split in roles[:-1] for case in split}
        assert len(cases) == 20 and not (cases & seen_cases)
        assert len(roster) == 8 and not (set(roster) & seen_prompts)
        seen_cases.update(cases)
        seen_prompts.update(roster)
