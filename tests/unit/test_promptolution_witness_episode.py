"""T2 checks for full archive rosters, admission budgets, and paired resampling."""

import pytest

from benchmarks import promptolution_witness_episode as episode


def test_episode_keeps_the_holdout_and_every_admission_case_disjoint():
    held = set(range(90))
    layouts = episode.schedule({'programs': episode.PROGRAMS}, 'gsm8k', 17, held)
    rosters, validation, training, admission = zip(*layouts, strict=True)
    assert {prompt for roster in rosters for prompt in roster} == set(episode.PROGRAMS) - {episode.START}
    assert all(len(roster) == 2 for roster in rosters)
    assert all(anchors == validation[0] for anchors in validation)
    scheduled = set(validation[0]).union(*(set(rows) for rows in (*training, *admission)))
    assert len(scheduled) == episode.VALIDATION + episode.CYCLES * (episode.TRAIN + episode.ADMISSION)
    assert scheduled.isdisjoint(held)
    with pytest.raises(ValueError, match='protect'):
        episode.play({}, layouts, 17, episode.CPO, held | {validation[0][0]})


def test_a_rejected_nomination_spends_an_attempt_and_charges_the_proof():
    held = set(range(90))
    layouts = episode.schedule({'programs': episode.PROGRAMS}, 'sst5', 17, held)
    anchors = set(layouts[0][1])
    matrix = {prompt: ''.join('1' if prompt != episode.START and case in anchors else '0' for case in range(300))
              for prompt in episode.PROGRAMS}
    one, many = [episode.play(matrix, layouts, 17, method, held) for method in (episode.CPO, episode.UNRESTRICTED)]
    assert one[0] == many[0] == episode.START
    assert one[2]['decisions'] == ['rejected']
    assert many[2]['decisions'] == ['rejected'] * episode.CYCLES
    assert 0 < one[1]['admissionLookups'] < many[1]['admissionLookups']
    assert all(case not in held for (prompt, case), passed in (*many[2]['search'], *many[2]['admission']))


def test_paired_draws_reselect_the_affordable_controls():
    best, tied, expensive = 'best', 'tied', 'expensive'
    totals = {method: {'paidLookups': cost} for method, cost in (
        (episode.CPO, 10), (best, 9), (tied, 9), (expensive, 11))}
    vectors = {episode.CPO: [3] * episode.HOLDOUT, best: [4, 0] * (episode.HOLDOUT // 2),
               tied: [0, 4] * (episode.HOLDOUT // 2), expensive: [8] * episode.HOLDOUT}
    comparison = episode.compare({'resampleSeed': 17, 'draws': 100}, [(totals, vectors)], (best, tied, expensive))
    assert comparison['control'] == best
    assert comparison['affordableControls'] == [best, tied]
    assert set(comparison['controlSelectionsInPairedDraws']) == {best, tied}
