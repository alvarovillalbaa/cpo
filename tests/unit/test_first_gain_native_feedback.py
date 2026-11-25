from benchmarks import first_gain_native_feedback as benchmark


def test_native_reflection_receives_its_sampled_minibatch_in_order(tmp_path):
    tasks, original, plan, expected = benchmark.prepare()
    report = benchmark.verify(tasks, original, plan, expected, tmp_path)
    assert report['originalFixtureMatched']
    batched = benchmark.NATIVE_ARMS[-1]
    assert report['nativeFeedback'][batched]['mismatchedMembership'] > 0
    assert report['physicalRequestsByRole'] == expected['physicalFixtureRequestsByRole']
    assert all(row['sent'] == row['recentlyPaid'] for row in report['changedReflections'])
