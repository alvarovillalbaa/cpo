from itertools import product

from benchmarks import witness_anchor_bounds as replay


def test_all_binary_boards_certify_the_same_exact_winner_when_settled():
    candidates = ('old', 'first', 'second')
    anchors = (0, 1)
    keys = tuple(product(candidates, anchors))
    for values in product((False, True), repeat=len(keys)):
        grades = dict(zip(keys, values, strict=True))
        exact = max(candidates, key=lambda prompt: sum(grades[prompt, case] for case in anchors))
        for cap in range(len(keys) + 1):
            reads = {}

            def grade(prompt, case):
                assert (prompt, case) not in reads
                answer = grades[prompt, case]
                reads[prompt, case] = answer
                return answer

            result = replay.race(candidates, anchors, grade, cap)
            assert result.reads == len(reads) <= cap
            if result.settled or cap == len(keys):
                assert result.prompt == exact
            if result.prompt != 'old':
                assert sum(passed for (prompt, _), passed in reads.items() if prompt == result.prompt) > sum(
                    grades['old', case] for case in anchors)


def test_winner_identity_can_settle_without_finishing_its_score():
    def grade(prompt, _case):
        return prompt == 'candidate'

    result = replay.race(('old', 'candidate'), (1, 2, 3, 4), grade, 8)

    assert result == replay.Race('candidate', 5, True, True)


def test_incumbent_wins_perfect_score_ties_without_challenger_reads():
    def grade(prompt, _case):
        assert prompt == 'old'
        return True

    assert replay.race(('old', 'candidate'), (1, 2, 3, 4), grade, 8) == replay.Race('old', 4, True, False)
