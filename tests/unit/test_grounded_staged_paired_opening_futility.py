"""Check the early rejection rule against all completions of a shared panel."""

from itertools import product

from benchmarks.grounded_staged_paired_opening_futility import CONTROLS, budget, score_until_rejected, staged


def sample(case, arms, *, critical=False):
    row = {'id': case, 'critical': critical, 'expected': {'value': 1}}
    request = {'task': 'task', 'repeat': 0, 'input': case}
    return request, row, arms


def exhaustive_status(samples, outcomes, gate, prices):
    cells = {}
    for (_, row, arms), grade in zip(samples, outcomes, strict=True):
        case = cells.setdefault(row['id'], {'id': row['id'], 'critical': row['critical'], 'passes': {}})
        case['passes'].update(dict.fromkeys(('cpo' if arm == budget.ARM else arm for arm in arms), grade))
    return all(staged.grade({'task': list(cells.values())},
                            {**costs, 'cpo': costs[budget.ARM]}, gate, controls=CONTROLS[1:])['qualified']
               for costs in prices.values())


def test_every_skipped_suffix_has_no_qualifying_completion():
    arms = (*CONTROLS, budget.ARM)
    panels = (
        (sample('shared', arms, critical=True), sample('split', CONTROLS), sample('split', (budget.ARM,))),
        (sample('shared', arms), sample('split', (budget.ARM,), critical=True),
         sample('split', CONTROLS, critical=True)),
    )
    for samples, outcomes, minimum, gain, charge in product(panels, product((False, True), repeat=3),
                                                            (0, 1, 2), (1, 2), (7, 10)):
        gate = {'minimumTaskPasses': minimum, 'minimumAddedPasses': gain, 'efficiencyPercent': 90}
        prices = {'logical search uses': {**dict.fromkeys(CONTROLS, 10), budget.ARM: 8},
                  'actual charge': {**dict.fromkeys(CONTROLS, 10), budget.ARM: charge}}
        pending = iter(outcomes)
        result = score_until_rejected(samples, gate, prices,
                                      lambda _: '{"value": 1}' if next(pending) else '{}')
        paid = result['scoredRequests']
        assert (result['status'] == 'qualified') == exhaustive_status(samples, outcomes, gate, prices)
        if result['status'] == 'qualified':
            assert result['completePanel'] is True
            assert paid == len(samples)
        else:
            for pending_outcomes in product((False, True), repeat=len(samples) - paid):
                assert not exhaustive_status(samples, outcomes[:paid] + pending_outcomes, gate, prices)


def test_identical_selected_prompts_cannot_create_the_required_gain():
    samples = (sample('shared', (*CONTROLS, budget.ARM)),)
    gate = {'minimumTaskPasses': 1, 'minimumAddedPasses': 1, 'efficiencyPercent': 90}
    measures = {'calls': {**dict.fromkeys(CONTROLS, 10), budget.ARM: 7},
                'charge': {**dict.fromkeys(CONTROLS, 10), budget.ARM: 10}}

    def unexpected_dispatch(_):
        raise AssertionError('The gate is impossible before dispatch')

    verdict = score_until_rejected(samples, gate, measures, unexpected_dispatch)
    assert verdict['status'] == 'rejected'
    assert verdict['scoredRequests'] == 0
    assert verdict['verdictsOnBestCompletion']['calls']['qualified'] is True
    assert verdict['verdictsOnBestCompletion']['charge']['qualified'] is False
