"""Reuse paid archive qualification to skip fresh search in continuous replay."""

import argparse
from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import gepa_paid_cap_transfer as gepa
from benchmarks import routed_score_allocation as prior
from benchmarks import routed_training_corroboration as transfer
from benchmarks import routed_validation_ties as ties
from cpo._contract import digest
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
PARENT_SHA256 = '096f581ea76be3be25bd109167d7a944c2825debd16f760796d23b1b1f38dd49'
CPO = 'strict'
METHODS = (CPO, *prior.PRIMARY)
POLICIES = ('ordinary', 'terminal', 'all-cycles')


class PaidQualification:
    def __init__(self, policy, cycles):
        self.policy, self.cycles = policy, cycles
        self.cycle, self.perfect = 0, False
        self.audit = Counter()

    def begin(self, history):
        self.cycle, self.perfect = len(history), False

    def check(self, qualify, incumbent, challenger, cases, evaluate):
        paid = {}

        def observe(prompt, case):
            reply = evaluate(prompt, case)
            if prompt == incumbent:
                paid[case] = reply
            return reply

        result = qualify(incumbent, challenger, cases, observe)
        self.perfect = not result[0] and bool(cases) and all(paid.get(case) is True for case in cases)
        return result

    def skip(self):
        if self.perfect and (self.policy == 'all-cycles' or
                             self.policy == 'terminal' and self.cycle + 1 == self.cycles):
            self.audit.update(skippedFreshSearches=1, skippedBeforeFinal=int(self.cycle + 1 < self.cycles))
            return True
        return False

    @contextmanager
    def capture(self, archive):
        nominal, qualify = archive.nominate, archive.qualify_archived

        def nominate(incumbent, history, attempted, policy):
            self.begin(history)
            return nominal(incumbent, history, attempted, policy)

        def preflight(incumbent, challenger, cases, evaluate):
            return self.check(qualify, incumbent, challenger, cases, evaluate)

        with patch.object(archive, 'nominate', nominate), patch.object(archive, 'qualify_archived', preflight):
            yield


def replay_episode(matrix, held, seed, plan, start, method, policy):
    evidence = PaidQualification(policy, plan['schedule']['cycles'])
    if method == CPO:
        original = ties.split.run
        cycle = ties.split.fixed_pool_cycle

        def run_route(*args):
            original_cycle = cycle.run_fixed_pool_cycle

            def fresh(incumbent, *args, **kwargs):
                if evidence.skip():
                    return FixedPoolCycleResult(FinalistResult(incumbent, None, 0), None)
                return original_cycle(incumbent, *args, **kwargs)

            # The original route chooses its archive qualifier before entering here.
            with (evidence.capture(ties.prior.archive.archive), patch.object(cycle, 'run_fixed_pool_cycle', fresh)):
                return original(*args)

        with patch.object(ties.split, 'run', run_route):
            counts, trace = ties.run(matrix, held, seed, plan, str(start), 'strict')
        selected = tuple(row['decision']['selected'] for row in trace)
    else:
        original_race = gepa.optimize_by_paid_reads

        def fresh(incumbent, *args, **kwargs):
            return (incumbent, 0) if evidence.skip() else original_race(incumbent, *args, **kwargs)

        with evidence.capture(gepa.archive), patch.object(gepa, 'optimize_by_paid_reads', fresh):
            _, counts, peak, trace = gepa.reinvest_episode(
                matrix, held, seed, plan['schedule'], plan, batched=method == prior.PRIMARY[1],
            )
        if peak > plan['searchCap']:
            raise ValueError('GEPA exceeded the recorded paid ceiling')
        selected = tuple(row['selected'] for row in trace)
    counts.update(evidence.audit)
    return counts, trace, selected


def prepare():
    parent, panels, strict, references = prior.prepare()
    raw = (ROOT / 'docs/routed-score-allocation-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != PARENT_SHA256 or json.loads(raw)['planSha256'] != digest(parent):
        raise ValueError('The preceding MMLU comparison does not match its published seal')
    paths = ('benchmarks/routed_paid_qualification.py', 'benchmarks/gepa_paid_cap_transfer.py',
             'benchmarks/prompteval_archive_cycles.py', *parent['sourceSha256'])
    plan = {**{k: parent[k] for k in ('schedule', 'validationRows', 'searchCap', 'gepaVersion',
                                     'bootstrap', 'minimumLookupSavingPercent')},
            'protocol': 'cpo-routed-paid-qualification-v1', 'methods': METHODS, 'policies': POLICIES,
            'primary': 'terminal', 'parentPlanSha256': digest(parent), 'parentReportSha256': PARENT_SHA256,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'scope': ('Skip fresh search only when the already paid archive comparison rules out a strict gain. '
                      'Compare the final cycle alone with every cycle. Apply both rules to CPO and GEPA.')}
    return plan, panels, strict, references


def label(policy, method):
    return f'{policy}/{method}'


def measure_panel(panel, plan, strict, references):
    matrix, subject = panel['correctness'], panel['subject']
    held = ties.confirmation.holdout(subject, len(matrix[0]))
    starts = ties.costs.retained_prompts(matrix, held, plan['schedule'])
    labels = tuple(label(policy, m) for m in METHODS for policy in POLICIES)
    totals, logs, finals = ({k: factory() for k in labels} for factory in (Counter, list, list))
    for seed, start in zip(plan['schedule']['seeds'], starts, strict=True):
        for method in METHODS:
            base_path = None
            for policy in POLICIES:
                key = label(policy, method)
                counts, trace, chosen = replay_episode(matrix, held, seed, plan, start, method, policy)
                if policy == 'ordinary':
                    base_path = chosen
                elif policy == 'terminal' and chosen != base_path:
                    raise ValueError('Skipping final search changed a deployed prompt')
                totals[key].update(counts)
                if policy != 'ordinary':
                    totals[key].update(changedFinalPrompts=int(chosen[-1] != base_path[-1]))
                logs[key].append(trace)
                finals[key].append(int(chosen[-1]))
    points = {key: {**count, 'paidLookups': count['searchPaid'] + count['qualificationPaid'],
                    'traceSha256': digest(logs[key])} for key, count in totals.items()}
    for method in METHODS:
        source = strict if method == CPO else references[method]
        ties.frontier.expect_reference(points[label('ordinary', method)], source)
    vectors = {key: ties.confirmation.uncertainty.case_totals(matrix, held, prompts) for key, prompts in finals.items()}
    if any(sum(vector.values()) != points[key]['holdoutPasses'] for key, vector in vectors.items()):
        raise ValueError('Paired holdout evidence differs from its trial totals')
    return points, held, vectors


def replay(plan, panels, strict, references):
    details, totals, holdouts = {}, {}, {}
    margins = {policy: {} for policy in POLICIES}
    for panel in panels:
        subject, model = panel['subject'], panel['model']
        name = f'{subject}/{model}'
        points, held, vectors = measure_panel(panel, plan, strict[name], references[name])
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('The two archived models must have the same ordered holdout')
        details[name] = points
        for key, point in points.items():
            totals.setdefault(key, Counter()).update({k: v for k, v in point.items() if type(v) is int})
        for policy, subjects in margins.items():
            cpo = vectors[label(policy, CPO)]
            compared = subjects.setdefault(subject, {m: [0] * len(held) for m in prior.PRIMARY})
            for method, values in compared.items():
                gepa_scores = vectors[label(policy, method)]
                for index, case in enumerate(held):
                    values[index] += cpo[case] - gepa_scores[case]
    comparisons = {}
    for policy, subjects in margins.items():
        ranges = transfer.ranges(subjects, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
        paid = totals[label(policy, CPO)]['paidLookups']
        controls = {m: totals[label(policy, m)]['paidLookups'] for m in prior.PRIMARY}
        enough = all(100 * paid <= (100 - plan['minimumLookupSavingPercent']) * limit for limit in controls.values())
        low, high = ranges['joint']
        gate = 'failed' if not enough or high < 0 else 'passed' if low >= 0 else 'inconclusive'
        comparisons[policy] = {'caseSensitivityRanges': ranges, 'gate': gate,
                               'lookupSavingFractions': {m: 1 - paid / limit for m, limit in controls.items()}}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': details, 'totals': totals, 'comparisons': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, *inputs)
    with args.out.open('x') as stream:
        json.dump(result, stream, sort_keys=True, separators=(',', ':'))
        stream.write('\n')


if __name__ == '__main__':
    main()
