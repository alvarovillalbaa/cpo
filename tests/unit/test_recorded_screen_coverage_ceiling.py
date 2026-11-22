from benchmarks import recorded_screen_coverage_ceiling as study


def test_coverage_removes_options_at_each_gate():
    board = {
        'start': (1, 0, 1, 0, 1, 0, 0, 0, 0),
        'roster-only': (1, 1, 0, 0, 1, 1, 1, 1, 1),
        'qualification-only': (1, 0, 1, 1, 1, 1, 1, 1, 0),
        'unread': (1, 1, 1, 1, 1, 1, 1, 0, 0),
        'screened': (1, 1, 1, 1, 1, 1, 0, 0, 0),
    }
    cells = {prompt: [(value, None, False) for value in scores] for prompt, scores in board.items()}
    cohorts = ([], [0, 1], [2, 3], [4, 5, 6, 7, 8])
    menus = study.menus(cells, 'start', tuple(board)[1:], cohorts, {'screened'}, 'start', cap=4)
    assert study.headroom(menus, start_score=1, actual_score=1) == {
        'roster': 4, 'qualification': 3, 'validation-and-qualification': 2, 'paid-screen': 1,
        'funded-after-screen': 1, 'nomination': 0,
    }
    limited = study.menus(cells, 'start', tuple(board)[1:], cohorts, {'screened'}, 'start', cap=3)
    assert not limited['funded-after-screen']


def test_a_hindsight_veto_can_always_retain_the_start():
    menus = dict.fromkeys(study.MENU_NAMES, {'qualified-but-worse': 1})
    assert study.headroom(menus, start_score=3, actual_score=1) == dict.fromkeys(study.MENU_NAMES, 2)
