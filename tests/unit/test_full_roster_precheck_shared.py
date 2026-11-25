import pytest

from benchmarks import full_roster_precheck_shared as study
from cpo._contract import digest


@pytest.fixture
def wire(tmp_path):
    with (tmp_path / 'wire.jsonl').open('x') as stream:
        yield stream


def test_validation_allowance_is_checked_before_dispatch_and_cache_hits_still_count_logically(wire):
    tasks, plan = study.prepare()
    task = next(iter(tasks))
    requests = []

    def respond(request):
        requests.append(request)
        return '{}'

    journal = study.SharedJournal(wire, {**plan, 'candidateNewValidationLimitPerCycle': 1}, respond, tasks=tasks)
    panel = tasks[task]['validation']
    first = {'task': task, 'role': 'evaluation', 'instruction': 'draft', 'input': panel[0]['input']}
    journal.send(study.CANDIDATE, first)
    journal.send(study.CANDIDATE, first)
    with pytest.raises(study.parent.grounded.ResponderFailed) as error:
        journal.send(study.CANDIDATE, {**first, 'instruction': 'extra draft'})
    assert 'validation allowance' in str(error.value.__cause__)
    assert len(requests) == journal.physical['evaluation'] == 1
    assert journal.logical['evaluation'] == 2
    journal.send(study.CANDIDATE, {**first, 'input': panel[study.parent.VALIDATION]['input']})
    assert journal.physical['evaluation'] == 2


def test_another_arms_admission_cache_does_not_replace_the_reference_proof(wire):
    tasks, plan = study.prepare()
    task = next(iter(tasks))
    request = {'task': task, 'role': 'admission', 'instruction': 'draft', 'repeat': 0,
               'input': tasks[task]['admission'][0]['input']}
    journal = study.SharedJournal(wire, plan, lambda request: '{}', tasks=tasks)
    journal.send('gepa-sequential', request)
    with pytest.raises(study.parent.grounded.ResponderFailed) as error:
        journal.send(study.CANDIDATE, request)
    assert 'reuse the reference' in str(error.value.__cause__)
    journal.send(study.REFERENCE, request)
    journal.send(study.CANDIDATE, request)
    assert journal.physical['admission'] == 1
    assert journal.logical['admission'] == 3


def test_candidate_divergence_stops_before_holdout(monkeypatch):
    choices = {study.REFERENCE: 'reference', study.CANDIDATE: 'candidate'}
    monkeypatch.setattr(study, '_CHOOSE', lambda *_: (choices, {}, [8, 8, 8]))
    with pytest.raises(ValueError, match='agree before holdout'):
        study.choose('ticket', {}, None, None)


def test_shared_fixture_preserves_scores_and_matches_exact_replay(tmp_path):
    _, plan = study.prepare()
    _, prior = study.prior.prepare()
    assert plan['previousPortableSeal'] == digest(prior)
    assert plan['logicalLimitsByRole'] == prior['logicalLimitsByRole']
    assert plan['requestCeiling'] == 1956
    assert plan['physicalLimitsByRole'] == {'reflection': 36, 'evaluation': 1092, 'admission': 288, 'qualification': 540}
    result, verdict = study.run_fixture(digest(plan), tmp_path / 'fixture')
    assert study.replay(tmp_path / 'fixture', tmp_path / 'replay') == (result, verdict)
    assert verdict['sameFeedbackChoices'] and verdict['sameFeedbackHoldoutGrades']
    assert sum(result['physicalCallsByRole'].values()) == 436
    assert not verdict['fullDevelopmentGatePassed']
