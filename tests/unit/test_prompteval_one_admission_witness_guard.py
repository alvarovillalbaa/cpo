"""Check that the extra witness uses only paid incumbent grades and a bounded allowance."""

from collections import Counter
from random import Random

from benchmarks.prompteval_one_admission_witness_guard import guarded_nominee


def run(cap, *, rescue=False, can_rescue=True, preserve_only=False, mostly_passes=True):
    cases = list(range(5))
    order = cases.copy()
    Random(12).shuffle(order)
    rows = {'incumbent': (True, True, True, False, True) if mostly_passes else (False, False, False, True, False),
            'early': (True, True, False, True, True),
            'late': (True, True, can_rescue, True, True)}
    grades = {(prompt, case): outcome for prompt, outcomes in rows.items() for case, outcome in zip(order, outcomes)}
    reads = []
    stats = Counter()

    def observe(prompt, case):
        reads.append((prompt, case))
        assert len(reads) <= cap
        return grades[prompt, case]

    nominee = guarded_nominee('incumbent', {'validation': cases, 'seed': 12, 'alternatives': ('early', 'late')},
                              observe, {'evaluationLookupLimit': cap}, stats, rescue=rescue, preserve_only=preserve_only)
    return nominee, reads, stats, order


def test_veto_does_not_buy_an_additional_incumbent_grade():
    nominee, reads, stats, order = run(12)
    assert nominee == 'incumbent'
    assert reads[-1] == ('early', order[2]) and len(reads) == 11
    assert [case for prompt, case in reads if prompt == 'incumbent'] == order[:4]
    assert stats['vetoedNominees'] == stats['extraLogicalLookups'] == 1


def test_rescue_checks_only_an_original_finalist_and_respects_the_cap():
    nominee, reads, stats, order = run(12, rescue=True)
    assert nominee == 'late'
    assert reads[-2:] == [('early', order[2]), ('late', order[2])]
    assert stats['rescuedNominees'] == 1 and stats['extraLogicalLookups'] == 2
    assert run(11, rescue=True)[0] == 'incumbent'
    assert run(12, rescue=True, can_rescue=False)[0] == 'incumbent'


def test_an_unfunded_extra_check_keeps_the_original_nomination():
    nominee, reads, stats, _ = run(10, rescue=True)
    assert nominee == 'early' and len(reads) == 10 and not stats


def test_extra_incumbent_pass_policy_leaves_second_repairs_out():
    assert run(12, mostly_passes=False)[0] == 'incumbent'
    nominee, reads, stats, _ = run(12, preserve_only=True, mostly_passes=False)
    assert nominee == 'early' and len(reads) == 10 and not stats
    assert run(12, preserve_only=True)[0] == 'incumbent'
