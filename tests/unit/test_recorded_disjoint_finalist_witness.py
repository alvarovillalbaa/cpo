from collections import Counter

from benchmarks import recorded_disjoint_finalist_witness as study
from cpo import Observation, Row


def test_witness_checks_only_the_two_validated_candidates_and_reserves_its_full_cost():
    rows = tuple(Row(str(case), 'validation') for case in range(3))
    witness = (Row('3', 'selection-witness'), Row('4', 'selection-witness'))
    matrix = {'start': (1, 0, 0, 0, 0), 'first': (1, 1, 1, 0, 0), 'alternate': (1, 1, 0, 1, 1),
              'unproven': (1, 0, 0, 1, 1)}
    cells = {prompt: tuple((grade, None, False) for grade in grades) for prompt, grades in matrix.items()}
    ledger = {(prompt, row.id): Observation(bool(cells[prompt][int(row.id)][0]), {})
              for prompt in matrix for row in rows}
    audit = Counter()

    def read(prompt, row):
        assert prompt in ('first', 'alternate') and row in witness and (prompt, row.id) not in ledger
        ledger[prompt, row.id] = grade = Observation(bool(cells[prompt][int(row.id)][0]), {})
        return grade

    args = 'start', 'first', ('first', 'alternate', 'unproven'), rows, witness, read, ledger, cells
    assert study.choose(*args, cap=15, audit=audit) == 'first' and not audit
    assert study.choose(*args, cap=16, audit=audit) == 'alternate'
    assert audit['witnessLookups'] == 3 and audit['replacements'] == 1
    # A subsequent comparison must credit the three replies that already constitute the proof.
    assert study.choose(*args, cap=16, audit=audit) == 'alternate'
    assert audit['witnessLookups'] == 3


def test_separate_witness_can_change_the_single_qualified_nominee():
    cohorts = (list(range(10)), list(range(10, 16)), [16, 17], [18])
    cells = {prompt: tuple((grade, None, False) for grade in outcomes) for prompt, outcomes in {
        'start': (0,) * 10 + (1, 0, 0, 0, 0, 0) + (0, 0, 0),
        'first': (0,) * 10 + (1, 1, 1, 1, 0, 0) + (0, 0, 0),
        'alternate': (0,) * 5 + (1, 1, 1, 1, 1) + (1, 0, 0, 0, 1, 1) + (1, 1, 1),
    }.items()}
    args = (cells, 'start', ('first', 'alternate'), cohorts, 31, 40)
    before = study.prior.run_trial(*args, ())[:3]
    assert before[1][2:4] == ('first', 'start')
    for width in study.WIDTHS.values():
        point, trace, grades = study.paired_trial(args, width, before, Counter())
        assert trace[2:4] == ('alternate', 'alternate') and grades == (1,)
        assert point['witnessLookups'] == width + 1
        assert point['qualificationLookups'] <= 4
