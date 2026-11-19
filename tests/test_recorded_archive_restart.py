from benchmarks.recorded_archive_restart import proposal_graph, qualify


def test_retrieval_reopens_only_previously_reachable_earlier_branches():
    source = {'root': ['incumbent', 'other'], 'incumbent': ['near'], 'other': ['far'], 'isolated': ['offline']}
    local, alternatives = proposal_graph(source, 'root', 'incumbent', 15, 'descendants')
    local_first, _ = proposal_graph(source, 'root', 'incumbent', 15, 'local-first')
    mix, _ = proposal_graph(source, 'root', 'incumbent', 15, 'mixed')
    assert alternatives == {'other', 'far'}
    assert local['incumbent'] == ['near']
    assert local_first['incumbent'][0] == 'near'
    assert set(mix['incumbent']) == set(local_first['incumbent']) == {'near', 'far', 'other'}
    assert source['incumbent'] == ['near']


def test_qualification_charges_actual_observations_and_vetoes_a_critical_loss():
    metadata = {'a': {'critical': True}, 'b': {'critical': False}, 'c': {'critical': False}}
    matrix = {'incumbent': {'a': (True, 1), 'b': (False, 0), 'c': (False, 0)},
              'winner': {'a': (True, 1), 'b': (True, 1), 'c': (False, 0)},
              'regression': {'a': (False, 0), 'b': (True, 1), 'c': (True, 1)}}
    assert qualify('incumbent', 'winner', metadata, matrix, list(metadata))[:3] == ('winner', 'promote', 5)
    assert qualify('incumbent', 'regression', metadata, matrix, list(metadata)) == (
        'incumbent', 'critical_regression', 4, {'a': False})
