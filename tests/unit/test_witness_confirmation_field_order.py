from benchmarks import grounded_fixture, witness_confirmation_field_order as study


def test_reordering_keeps_cases_labels_criticality_and_input_lengths():
    canonical, shifted, plan = study.prepare()

    for task, regions in canonical.items():
        assert shifted[task] == {**regions, 'confirmation': shifted[task]['confirmation']}
        original = {row['input'] for rows in regions.values() for row in rows}
        changed = []
        for before, after in zip(regions['confirmation'], shifted[task]['confirmation'], strict=True):
            assert {**before, 'input': after['input']} == after
            assert grounded_fixture.facts(before['input']) == grounded_fixture.facts(after['input'])
            assert len(before['input'].encode()) == len(after['input'].encode())
            if before['input'] != after['input']:
                assert after['input'] not in original
                changed.append(after)
        assert [row['id'] for row in changed] == plan['probeIdsByTask'][task]
        assert sorted(row['critical'] for row in changed) == [False, False, True, True]


def test_shared_persistent_errors_escape_paired_gate_and_fail_case_gate(tmp_path):
    canonical, shifted, plan = study.prepare()
    result = study.measure(plan, canonical, shifted, tmp_path / 'development')

    assert result['changedRequests'] == 64
    assert result['scheduledRequests'] == 128
    assert result['orderAgnostic']['qualified']
    assert result['oneMissPerProbe']['qualified']
    for case, fault in result['persistentSharedErrorByCase'].items():
        assert fault['pairedQualified']
        assert not fault['qualified']
        assert fault['scoring']['scoredRequests'] == result['scheduledRequests']
        assert [item for cases in fault['absolute']['failedCases'].values() for item in cases] == [case]
    all_faults = result['allProbesFail']
    assert all_faults['scoring']['status'] == 'rejected-early'
    assert all_faults['absolute'] == {'status': 'unmeasured'}
