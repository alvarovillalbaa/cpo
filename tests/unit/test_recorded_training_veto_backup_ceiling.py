from benchmarks import recorded_training_veto_backup_ceiling as study


def test_exact_known_replies_tighten_only_their_own_proof_bound():
    paid = {('old', 0): True, ('old', 1): False, ('new', 0): True}
    assert study.proof_floor('old', 'new', (0, 1, 2), paid, promote=True) == 2
    assert study.proof_floor('old', 'new', (0, 1, 2), paid, promote=False) == 2
    paid['new', 1] = True
    assert study.proof_floor('old', 'new', (0, 1, 2), paid, promote=True) == 1
    assert study.proof_floor('old', 'new', (0, 1, 2), paid, promote=False) == 2


def test_offer_needs_all_three_gains_and_charges_every_unread_proof():
    outcomes = {'start': (0, 1, 1, 0, 0, 1, 0, 0, 0),
                'first': (0, 1, 1, 1, 0, 1, 1, 0, 0),
                'backup': (1, 1, 1, 1, 1, 1, 1, 0, 0),
                'weak': (1, 1, 1, 1, 0, 1, 1, 0, 0)}
    cells = {prompt: [(value,) for value in values] for prompt, values in outcomes.items()}
    cohorts = ((0, 1, 7, 8), (2, 3), (4, 5), (6,))
    search = {('start', 2): True, ('start', 3): False, ('backup', 2): True,
              ('start', 1): True, ('first', 0): False}
    proof = {('start', 4): False}
    roster = ('first', 'backup', 'weak')
    assert study.offers(cells, 'start', 'first', roster, cohorts, search, proof, cap=9) == [
        study.Offer(gain=1, validation=1, training=3, qualification=2, primary_veto=0)]
    assert not study.offers(cells, 'start', 'first', roster, cohorts, search, proof, cap=8)
    cells['first'][0] = (1,)
    assert not study.offers(cells, 'start', 'first', roster, cohorts, search, proof, cap=9)
