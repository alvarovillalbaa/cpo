from itertools import product

import pytest

from benchmarks import recorded_validation_tail_language_frontier as study


def test_subject_budget_pooling_matches_all_mix_combinations():
    labels = (study.frontier.RETAIN, 'sequential/20', 'batched/40')
    options = {'subject-a': ((5, 0), (8, 7), (7, 3)), 'subject-b': ((4, 0), (6, 2), (10, 8)),
               'subject-c': ((6, 0), (10, 6), (8, 3))}
    panels = {subject: {label: {'holdoutPasses': score, 'paidLookups': cost}
                        for label, (score, cost) in zip(labels, choices, strict=True)}
              for subject, choices in options.items()}
    choices = [(sum(score for score, _ in picked), sum(cost for _, cost in picked))
               for picked in product(*options.values())]
    budgets = {str(amount): amount for amount in range(0, 25)}
    results = study.by_subject_ceiling(panels, labels[1:], budgets)
    for name, budget in budgets.items():
        score, cost = max((entry for entry in choices if entry[1] <= budget), key=lambda entry: (entry[0], -entry[1]))
        witness = results[name]['settingsBySubject']
        assert results[name]['holdoutPasses'] == score
        assert results[name]['paidLookups'] == cost
        assert witness.keys() == panels.keys()
        assert sum(panels[subject][mode]['holdoutPasses'] for subject, mode in witness.items()) == score
        assert sum(panels[subject][mode]['paidLookups'] for subject, mode in witness.items()) == cost


@pytest.mark.parametrize('mode', study.cost.MODES)
def test_quote_boundaries_match_direct_integer_cap_replays_on_language_episodes(mode):
    pytest.importorskip('gepa')
    plan, panels, _, _ = study.prepare()
    lowest, highest = plan['minimumSearchCap'], plan['searchCap']
    language = study.reference_runner.language
    checked = set()
    for cohort, subject, _, matrix in panels:
        if cohort in checked:
            continue
        cells = {str(i): tuple((int(passed), None, False) for passed in grades) for i, grades in enumerate(matrix)}
        for seed in plan['seeds']:
            start, roster, groups = language.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
            args = cells, start, roster, groups, seed
            paths = study.cost.budget_paths(args, mode, lowest, highest)
            if len(paths) < 3:
                continue
            cap_points = tuple(paths)
            for cap in range(lowest, highest + 1):
                preceding = max(point for point in cap_points if point <= cap)
                assert study.cost.run(args, mode, cap) == paths[preceding]
            checked.add(cohort)
            break
    assert checked == {cohort for cohort, *_ in panels}
