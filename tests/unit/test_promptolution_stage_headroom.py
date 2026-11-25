from benchmarks import promptolution_stage_headroom as study
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.paired_qualification import QualificationDecision
from cpo.single_finalist import FinalistResult


def proof(nominee, *, passed):
    prompt = nominee if passed else 'base'
    verdict = 'promoted' if passed else 'rejected'
    return FixedPoolCycleResult(FinalistResult(nominee, nominee, 3),
                                QualificationDecision(verdict, prompt, (), 0, 1))


def test_veto_keeps_observed_gate_signal_and_pays_for_the_original_move():
    packaged = proof('first', passed=True)
    known = ('known-nominee', proof('second', passed=False))
    assert list(study.edges('base', packaged, (known,), study.NOMINATION)) == [
        (('first', False), 3, ('packaged', 'first', 'first', False, 3)),
        (('base', False), 3, ('veto', 'first', 'base', False, 3)),
    ]
    edges = list(study.edges('base', packaged, (known,), study.QUALIFICATION))
    assert edges[-1] == (('second', True), 3, ('allow-rejected', 'second', 'second', True, 3))


def test_reachable_keeps_feedback_state_even_when_an_arrival_is_more_expensive():
    def step(index, incumbent, rejected, tier):
        assert tier == study.VETO and incumbent == 'base'
        if index == 0:
            yield ('base', True), 1, ('cheap-rejection',)
            yield ('base', False), 2, ('expensive-nonrejection',)
        else:
            yield ('base' if rejected else 'better', False), 1, ('second',)

    score = {'base': 5, 'better': 8}
    choices = study.reachable('base', 2, step, study.VETO, 2, score.__getitem__)
    assert {(point.passes, point.cost, point.actions) for point in choices} == {
        (5, 4, (('cheap-rejection',), ('second',))),
        (8, 5, (('expensive-nonrejection',), ('second',))),
    }


def test_local_and_pooled_budget_attainers_use_their_actual_prices():
    point = study.frontier.Point
    original = [point(5, 4, ()), point(7, 4, ())]
    first = (point(5, 1, (('packaged',),)),)
    second = (point(7, 4, (('packaged',),)), point(10, 6, (('known-nominee',),)))
    result = study.summarize({study.NOMINATION: [first, second]}, original)
    outcome = result['bounds'][study.NOMINATION]
    assert outcome['perEpisodeCaps'] == {'holdoutPasses': 12, 'paidLookups': 5}
    assert outcome['pooledCap'] == {'holdoutPasses': 15, 'paidLookups': 7}
    match = study.price_match([first, second], 14)
    assert (match['targetPasses'], match['holdoutPasses'], match['paidLookups']) == (14, 15, 7)
    assert study.price_match([first, second], 16) is None
