from types import SimpleNamespace

from benchmarks import full_roster_no_nominee_repair as study
from cpo.single_finalist import FinalistResult


def original(spent=1):
    return SimpleNamespace(prompt='base', cycles=[SimpleNamespace(search=FinalistResult('base', None, spent))])


def test_paid_paired_loss_excludes_an_apparent_repair():
    paid = [('validation', 'base', 1, False), ('validation', 'base', 2, True),
            ('validation', 'loses', 1, True), ('validation', 'loses', 2, False),
            ('validation', 'unpaired', 2, True)]
    nominee, probe = study.witness_options('base', ('loses', 'unpaired'), (1, 2), paid)
    assert nominee is None
    assert probe == ('unpaired', 1)


def test_closed_admission_and_exhausted_validation_prevent_extra_reads():
    trial = 'base', ('draft',), ((), (0,), (1, 2, 3, 4), (5,)), 1
    paid = [('validation', 'base', 0, False)]
    assert study.rescue({}, trial, original(19), paid)[:2] == ('base', [])
    complete = [*paid, ('validation', 'draft', 0, True),
                *(('qualification', 'base', case, True) for case in trial[2][2])]
    start, extra, stats = study.rescue({}, trial, original(), complete)
    assert start == 'base' and extra == []
    assert stats['paidWitnessWithClosedAdmission'] == 1


def test_one_new_witness_uses_the_original_qualification_without_repaying_prefix():
    trial = 'base', ('draft', 'other'), ((), (0,), (1, 2, 3, 4), (5,)), 1
    cells = {'base': [(0, None)] * 5, 'draft': [(1, None)] * 5}
    paid = [('validation', 'base', 0, False), ('qualification', 'base', 1, False)]
    selected, extra, stats = study.rescue(cells, trial, original(), paid)
    assert selected == 'draft'
    assert extra[0] == ('validation', 'draft', 0, True)
    assert len([reply for reply in extra if reply[0] == 'validation']) == 1
    assert ('qualification', 'base', 1, False) not in extra
    assert stats['additionalDeployments'] == 1
