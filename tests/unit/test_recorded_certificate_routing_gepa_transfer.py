from benchmarks.recorded_certificate_routing_gepa_transfer import distinct_controls


def test_identical_case_vectors_keep_the_cheapest_then_canonical_control():
    costs = {'late': {'paidLookups': 5}, 'B': {'paidLookups': 4}, 'A': {'paidLookups': 4},
             'other': {'paidLookups': 2}}
    subjects = {'task': {'late': [0, 1], 'B': [0, 1], 'A': [0, 1], 'other': [1, 0]}}
    assert distinct_controls(tuple(costs), costs, subjects) == ('other', 'A')
