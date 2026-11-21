from itertools import product

from benchmarks import grounded_witness_scoring_order as study


def sample(case, critical, *arms):
    return study.original.Sample({'task': 'task', 'input': case, 'repeat': 0, 'instruction': ' '.join(arms)},
                                 {'id': case, 'critical': critical}, arms)


def test_gate_order_prioritizes_contested_critical_replies_and_defers_descriptive_work():
    control = study.original.parent.original.CANDIDATE
    candidate = study.CANDIDATE
    descriptive = 'cpo-four-admissions'
    ordinary = sample('ordinary', False, candidate, control)
    shared = sample('shared', True, candidate, control)
    loss_control = sample('contested', True, control)
    loss_candidate = sample('contested', True, candidate)
    diagnostic = sample('contested', True, descriptive)
    samples = [ordinary, shared, diagnostic, loss_control, loss_candidate]

    assert study.order(samples, study.CRITICAL) == [diagnostic, loss_control, loss_candidate, ordinary, shared]
    assert study.order(samples, study.GATE) == [loss_candidate, loss_control, ordinary, shared, diagnostic]
    assert study.order(samples, study.SEALED) == samples


def test_all_orders_keep_exact_gate_decisions_for_every_small_shared_reply_table():
    parent = study.original.parent
    controls = ('initial', *parent.CONTROLS)
    descriptive = next(arm for arm in parent.ARMS if arm not in (*controls, study.CANDIDATE))
    samples = [sample(case, critical, *members)
               for case, critical in (('ordinary', False), ('contested', True))
               for members in ((descriptive,), controls, (study.CANDIDATE,))]
    plan = {'gate': {'minimumTaskPasses': 1, 'minimumAddedPasses': 1, 'efficiencyPercent': 90}}
    costs = {'logical': dict.fromkeys(parent.ARMS, 20), 'attributed': dict.fromkeys(parent.ARMS, 20)}

    for bits in product((False, True), repeat=len(samples)):
        scores = {study.digest(item.request): bit for item, bit in zip(samples, bits, strict=True)}
        full = study.complete_verdict(samples, scores, plan, costs)
        qualifies = all(row['qualified'] for row in full.values())
        for name in study.METHODS:
            ordered = study.order(samples, name)
            result, evidence = study.original.score_until_rejected(
                ordered, plan, costs, lambda item: scores[study.digest(item.request)])
            assert (result['status'] == 'qualified') == qualifies
            if qualifies:
                assert result['scoredRequests'] == len(samples)
                assert evidence['verdicts'] == full
