"""The narrower native arm keeps independent admission and the same stopping rule."""

from benchmarks import prompteval_narrow_native_admission as trial


def test_native_caps_fund_the_encoded_full_round_reserve():
    settings = trial.native_settings()
    assert len(settings) == 9
    for name, condition in settings.items():
        rows, cap = (condition[key] for key in ('validationRows', 'searchCap'))
        initial_and_round = rows + (rows + 2 * trial.REPLAY.transfer.PROBES) * (2 if 'batched' in name else 1)
        assert cap >= initial_and_round and rows in (8, 12, 16)


def test_a_rejected_admission_stops_and_only_the_enrolled_anchor_prefix_is_used(monkeypatch):
    observed = []

    def nominate(name, incumbent, layout, observe, active):
        observed.append((name, incumbent, layout['validation'], active['evaluationLookupLimit']))
        observe(incumbent, layout['validation'][0])
        challenger, = layout['alternatives']
        observe(challenger, layout['validation'][0])
        return challenger

    monkeypatch.setattr(trial.transfer, 'select', nominate)
    common = {'seed': 11, 'validation': [0, 1, 2], 'train': []}
    layouts = ({**common, 'qualify': [3], 'alternatives': ['1']},
               {**common, 'qualify': [4], 'alternatives': ['2']})
    active = {'evaluationLookupLimit': 6, 'qualificationPolicy': 'extend-ties', 'minimumQualificationGain': 1,
              'maximumExtensionRows': 2}
    final, totals, _ = trial.capped_episode(('100000', '110001', '110011'), [5], '0', layouts, active,
                                            'gepa-sequential/validation-2/cap-6/one-admission', 'retire-assigned', 2)
    assert final == '0'
    assert len(observed) == 1 and observed[0][2:] == ([0, 1], 6)
    assert totals['searchLookups'] == totals['qualificationLookups'] == 2
