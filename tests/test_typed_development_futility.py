from itertools import product
import unittest

from benchmarks.typed_development_futility import Sample, rejection_reasons


ARMS = ('cpo', 'initial', 'gepa')


def qualifies(schedule, outcomes, floor, gain_required, costs):
    scores = {(sample.task, sample.case, sample.repeat, arm): passed
              for sample, passed in zip(schedule, outcomes, strict=True) for arm in sample.arms}
    cases = {(sample.task, sample.case): sample.critical for sample in schedule}
    tasks = {task for task, _ in cases}
    repeats = 2
    for task in tasks:
        totals = [sum(scores[task, case, repeat, arm] for family, case in cases if family == task
                      for repeat in range(repeats)) for arm in ARMS]
        if totals[0] < max(floor, *totals[1:]):
            return False
    case_deltas = []
    for (task, case), critical in cases.items():
        pairs = [[scores[task, case, repeat, arm] for arm in ARMS] for repeat in range(repeats)]
        if critical and any(not cpo and (initial or gepa) for cpo, initial, gepa in pairs):
            return False
        case_deltas.append(sum(cpo - gepa for cpo, _, gepa in pairs))
    return sum(case_deltas) >= gain_required or (costs['cpo'] <= 90 and min(case_deltas) >= 0)


class DevelopmentFutilityTests(unittest.TestCase):
    def test_matches_exhaustive_feasibility_with_shared_replies_and_repeats(self):
        schedule = (
            Sample('ticket', 'critical', 0, True, ('cpo', 'initial')),
            Sample('ticket', 'critical', 0, True, ('gepa',)),
            Sample('ticket', 'critical', 1, True, ('cpo',)),
            Sample('ticket', 'critical', 1, True, ('initial', 'gepa')),
            Sample('warehouse', 'ordinary', 0, False, ('cpo',)),
            Sample('warehouse', 'ordinary', 0, False, ('initial',)),
            Sample('warehouse', 'ordinary', 0, False, ('gepa',)),
            Sample('warehouse', 'ordinary', 1, False, ARMS),
        )
        completions = list(product((False, True), repeat=len(schedule)))
        for floor, minimum_gain, cost in product((1, 2), (1, 2), (80, 95)):
            gate = {'minimumPassesPerTask': floor, 'minimumAddedPasses': minimum_gain,
                    'maxSearchCostPercentForEfficiency': 90}
            costs = {'cpo': cost, 'gepa': 100}
            viable = {outcomes[:length] for outcomes in completions
                      if qualifies(schedule, outcomes, floor, minimum_gain, costs)
                      for length in range(len(schedule) + 1)}
            for length in range(len(schedule) + 1):
                for prefix in product((False, True), repeat=length):
                    self.assertEqual(not rejection_reasons(schedule, prefix, gate, costs), prefix in viable,
                                     (floor, minimum_gain, cost, prefix))

    def test_shared_unobserved_reply_cannot_become_a_gain(self):
        schedule = (Sample('ticket', 'one', 0, True, ARMS),)
        gate = {'minimumPassesPerTask': 1, 'minimumAddedPasses': 1, 'maxSearchCostPercentForEfficiency': 90}
        costs = {'cpo': 100, 'gepa': 100}
        self.assertEqual(rejection_reasons(schedule, (), gate, costs),
                         [{'gate': 'quality-or-efficiency', 'arm': 'gepa', 'maximumAddedPasses': 0}])
        self.assertFalse(rejection_reasons(schedule, (), gate, {**costs, 'cpo': 90}))
