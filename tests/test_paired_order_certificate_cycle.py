from itertools import product

from cpo import Observation, Row
from cpo.deferred_certificate_cycle import run_deferred_certificate_cycle
from cpo.paired_order_certificate_cycle import run_paired_order_certificate_cycle


def test_paired_order_preserves_every_three_case_qualification_and_pays_once():
    validation = (Row('validation', 'validation'),)
    qualification = tuple(Row(str(i), 'task') for i in range(3))
    for bits in product((False, True), repeat=6):
        grades = {'start': bits[:3], 'next': bits[3:]}
        for minimum in (1, 2, 3):
            paid = {}

            def qualify(prompt, row, repeat):
                key = prompt, row.id
                assert repeat == 0 and key not in paid
                paid[key] = grades[prompt][int(row.id)]
                return paid[key]

            result = run_paired_order_certificate_cycle(
                'start', ('next',), validation, qualification, lambda prompt, _: Observation(prompt == 'next', {}),
                metric_limit=2, qualify=qualify, minimum_gain=minimum,
            )
            gain = sum(bits[3:]) - sum(bits[:3])
            assert result.prompt == ('next' if gain >= minimum else 'start')
            assert result.qualification_evaluations == len(paid) <= 6


def test_critical_qualification_keeps_the_original_paid_order():
    validation = (Row('validation', 'validation'),)
    qualification = (Row('0', 'proof'), Row('1', 'proof', critical=True))
    grades = {'start': (False, True), 'next': (True, False)}

    def run(cycle):
        paid = []

        def qualify(prompt, row, repeat):
            paid.append((prompt, row.id, repeat))
            return grades[prompt][int(row.id)]

        result = cycle(
            'start', ('next',), validation, qualification, lambda prompt, _: Observation(prompt == 'next', {}),
            metric_limit=2, qualify=qualify, seed=9,
        )
        return result, paid

    assert run(run_paired_order_certificate_cycle) == run(run_deferred_certificate_cycle)
