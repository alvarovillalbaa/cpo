from random import Random

from benchmarks import recorded_one_read_backup as study
from cpo import Observation, Row


def observations(**prompts):
    return {(name, row): Observation(value, {}) for name, scored in prompts.items() for row, value in scored.items()}


def test_probe_can_only_fund_a_one_reply_certificate_and_reserves_training():
    rows = (Row('a', 'validation'), Row('b', 'validation'), Row('c', 'validation'))
    training = (Row('t', 'training'),)
    ledger = observations(start={'a': True, 'b': False, 'c': False}, main={'a': True, 'b': True},
                          alternate={'a': True}, cannot_win={'a': False})
    roster = ('main', 'alternate', 'cannot_win', 'unread')
    needed = len(ledger) + 4
    assert study.probe_options('start', 'main', roster, rows, training, ledger, needed) == [
        ('alternate', rows[1]), ('alternate', rows[2])]
    assert not study.probe_options('start', 'main', roster, rows, training, ledger, needed - 1)


def test_missing_protection_forces_the_probe_case_and_a_known_loss_excludes_candidate():
    rows = (Row('a', 'validation', True), Row('b', 'validation'), Row('c', 'validation'))
    ledger = observations(start={'a': True, 'b': False, 'c': False}, alternate={'b': True},
                          lost={'a': False, 'b': True})
    assert study.probe_options('start', 'main', ('main', 'alternate', 'lost'), rows, (), ledger, 100) == [
        ('alternate', rows[0])]


def test_archived_probe_changes_only_seeded_retention_and_buys_at_most_one_reply():
    plan, data, _ = study.prepare()
    settings = plan['datasets']['aime']
    cells = study.math.load_cells('aime', data['aime']['record'])
    attempted = 0
    for seed in settings['seeds'][:4]:
        cohorts = study.math.split_cases(45, seed, settings['cohorts'])
        for start in tuple(cells)[1:]:
            available = [name for name in cells if name != start]
            roster = Random(f'{seed}/{start}').sample(available, len(available))
            args = (cells, start, roster, cohorts, seed, plan['searchCap'])
            point, trace, _, options = study.run_candidate(*args)
            baseline = study.parent.run_trial(*args, study.prior.CANDIDATE, study.parent.EXPECTED)[1]
            assert point.get('validationProbes', 0) == bool(options)
            assert point['searchLookups'] <= plan['searchCap']
            if options:
                attempted += 1
                assert baseline[3] == start
            else:
                assert trace[3] == baseline[3]
    assert attempted > 0
