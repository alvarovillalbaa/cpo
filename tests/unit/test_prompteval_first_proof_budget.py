from benchmarks.prompteval_first_proof_budget import first_challenger, witness_challenger


LAYOUT = {'validation': [0, 1, 2, 3], 'train': [4, 5], 'alternatives': ['rewrite', 'repair', 'later']}


def test_first_proof_stops_on_a_verified_gain_and_skips_the_remaining_candidates():
    seen = []

    def observe(prompt, case):
        seen.append((prompt, case))
        return case == 0 if prompt == 'prior' else case < 2

    result = first_challenger('prior', LAYOUT, observe, {'evaluationLookupLimit': 12}, rank_opening=False)
    assert result == 'rewrite'
    assert seen == [('prior', 0), ('prior', 1), ('prior', 2), ('prior', 3), ('rewrite', 0), ('rewrite', 1)]


def test_opening_screen_uses_only_training_to_rank_and_still_needs_a_validation_proof():
    seen = []

    def observe(prompt, case):
        seen.append((prompt, case))
        if prompt == 'prior':
            return case == 0
        return prompt == 'repair' if case >= 4 else case < 2

    plan = {'evaluationLookupLimit': 12, 'probeSize': 2}
    selected = first_challenger('prior', LAYOUT, observe, plan, rank_opening=True)
    assert selected == 'repair'
    assert seen[4:] == [('rewrite', 4), ('rewrite', 5), ('repair', 4), ('repair', 5), ('repair', 0), ('repair', 1)]


def test_unfunded_candidate_proof_does_not_buy_training_or_validation_replies():
    seen = []

    def observe(prompt, case):
        seen.append((prompt, case))
        return case < 2

    plan = {'evaluationLookupLimit': 6, 'probeSize': 2}
    assert first_challenger('prior', LAYOUT, observe, plan, rank_opening=True) == 'prior'
    assert seen == [('prior', case) for case in LAYOUT['validation']]


def test_a_rejected_opening_leaves_later_candidates_eligible():
    seen = []

    def observe(prompt, case):
        seen.append((prompt, case))
        return prompt == 'later' or (prompt == 'prior' and case < 2)

    plan = {'evaluationLookupLimit': 12}
    assert first_challenger('prior', LAYOUT, observe, plan, rank_opening=False) == 'later'
    assert seen[4:] == [('rewrite', 0), ('rewrite', 1), ('repair', 0), ('repair', 1),
                        ('later', 0), ('later', 1), ('later', 2)]


def test_paired_witness_prioritizes_the_incumbent_miss_and_checks_the_known_pass():
    seen = []

    def observe(prompt, case):
        seen.append((prompt, case))
        return case == 0 if prompt == 'prior' else prompt == 'repair' or case == 1

    assert witness_challenger('prior', LAYOUT, observe, {'evaluationLookupLimit': 6}) == 'repair'
    assert seen == [('prior', 0), ('prior', 1), ('rewrite', 1), ('rewrite', 0), ('repair', 1), ('repair', 0)]


def test_paired_witness_keeps_a_perfect_incumbent_without_screening():
    seen = []

    def observe(prompt, case):
        seen.append((prompt, case))
        return True

    assert witness_challenger('prior', LAYOUT, observe, {'evaluationLookupLimit': 6}) == 'prior'
    assert seen == [('prior', case) for case in LAYOUT['validation']]


def test_two_finalists_use_one_additional_case_and_keep_the_total_read_limit():
    seen = []

    def observe(prompt, case):
        seen.append((prompt, case))
        if prompt == 'prior':
            return case == 0
        return case < 2 or prompt == 'repair'

    assert witness_challenger('prior', LAYOUT, observe, {'evaluationLookupLimit': 8}, finalists=2) == 'repair'
    assert seen[-2:] == [('rewrite', 2), ('repair', 2)]
    assert len(seen) == 8
