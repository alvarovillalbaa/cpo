from benchmarks import recorded_screen_tie_qualification as study


def test_two_reads_can_finish_a_witnessed_tie_within_the_original_cap():
    args = episode((1, 0, 1, 1, 0, 0), (1,) * 4)
    paid, old, _, _ = study.trial(args, 0)
    point, trace, held, audit = study.trial(args, 2)
    assert paid['tieNominations'] == 0 and old[2:4] == ('start', 'start')
    assert point['tieNominations'] == point['tiePromotions'] == 1
    assert trace[2:4] == ('challenger', 'challenger') and held == (1,) * 4
    assert audit['tieLookups'] == 2 and point['searchLookups'] <= study.prior.CAP


def test_an_already_paid_tie_cannot_bypass_independent_qualification():
    point, trace, held, audit = study.trial(episode((1, 1, 1, 0, 0, 0), (0,) * 4), 0)
    assert point['tieNominations'] == 1 and point['tiePromotions'] == 0
    assert trace[2:4] == ('challenger', 'start') and held == (0,) * 4
    assert audit['tieLookups'] == 0


def episode(challenger_validation, challenger_proof):
    cohorts = (list(range(10)), list(range(10, 16)), list(range(16, 20)), list(range(20, 24)))
    grades = {'start': (0,) * 10 + (0, 1, 1, 1, 0, 0) + (0,) * 8,
              'challenger': (0,) * 10 + challenger_validation + challenger_proof + (1,) * 4}
    cells = {prompt: [(grade, None, False) for grade in vector] for prompt, vector in grades.items()}
    return cells, 'start', ('challenger',), cohorts, 7
