from benchmarks import witness_training_repartition as study


def case(case_id, context, *, critical=False, label='shared'):
    return {'id': case_id, 'context': context, 'critical': critical, 'label': label}


def optimize(blocks):
    return study.optimize(blocks, lambda row: row['context'], lambda row: {row['label']})


def test_exchange_spreads_duplicate_context_without_changing_training_rows():
    original = [[case('a1', 'a'), case('a2', 'a')], [case('b', 'b'), case('c', 'c')]]

    selected, swaps = optimize(original)

    assert swaps == 1
    assert [len({row['context'] for row in block}) for block in selected] == [2, 2]
    assert sorted(row['id'] for block in selected for row in block) == ['a1', 'a2', 'b', 'c']
    assert [row['id'] for row in original[0]] == ['a1', 'a2']


def test_exchange_preserves_each_blocks_original_features():
    original = [[case('a1', 'a', label='first'), case('a2', 'a', label='second')],
                [case('b', 'b'), case('c', 'c')]]

    assert optimize(original) == (original, 0)


def test_exchange_preserves_each_blocks_critical_count():
    original = [[case('a1', 'a', critical=True), case('a2', 'a', critical=True)],
                [case('b', 'b'), case('c', 'c')]]

    assert optimize(original) == (original, 0)
