"""Measure candidate-selection headroom in the archived first-miss screen transfer."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_one_failure_screen_transfer as prior
from cpo._contract import digest


RECEIPT = 'docs/recorded-one-failure-screen-transfer-results-v1.json'
RECEIPT_SHA256 = 'e4f2ac401077b83705fa79befa036af71d00fb65e66b1ae625af9900f42b288d'
MENU_NAMES = ('roster', 'qualification', 'validation-and-qualification', 'paid-screen', 'funded-after-screen',
              'nomination')


def prepare():
    source, panels = prior.prepare()
    archived = prior.cost.prior.baseline.read_reference(RECEIPT, RECEIPT_SHA256, source)
    paths = (Path(__file__), Path(prior.__file__), Path(prior.prior.__file__))
    plan = {**source, 'protocol': 'recorded-screen-coverage-ceiling-v1',
            'parentPlanSha256': digest(source), 'parentReceiptSha256': RECEIPT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'menus': MENU_NAMES,
            'scope': 'Reproduce all three cap-13 screen paths before examining unread grades. Starting from '
                     'each actual deployment, measure the best improvement in the whole roster, after '
                     'independent qualification, with both strict certificates, among candidates with '
                     'any paid validation, within the remaining cap after screening, and within the '
                     'original nomination or retained start. '
                     'Use full archived validation, qualification and holdout answers for bounds only.'}
    return plan, panels, archived


def observed_trial(arguments, label):
    original = prior.prior.select
    paid = {}

    def choose(incumbent, candidates, rows, observe, ledger, **settings):
        winner = original(incumbent, candidates, rows, observe, ledger, **settings)
        if paid:
            raise ValueError('Expected a single search invocation')
        paid.update(ledger)
        return winner

    with patch.object(prior.prior, 'select', choose):
        if label == prior.PRIMARY:
            point, trace, grades, audit = prior.one_failure_trial(arguments)
        else:
            point, trace, grades, audit = prior.prior.trial(arguments, label.split('/')[0], prior.CAP)
    if len(paid) != point['searchLookups']:
        raise ValueError('Coverage requires every charged validation reply')
    return point, trace, grades, audit, {prompt for prompt, _ in paid if prompt != arguments[1]}


def menus(cells, start, roster, cohorts, screened, nominee, *, cap):
    _, validation, qualification, heldout = cohorts

    def passes(prompt, cases):
        return sum(cells[prompt][case][0] for case in cases)

    validation_target = passes(start, validation) + 1
    qualification_target = passes(start, qualification) + 1
    available = {prompt: passes(prompt, heldout) for prompt in (start, *roster)}
    qualified = {prompt: value for prompt, value in available.items()
                 if prompt != start and passes(prompt, qualification) >= qualification_target}
    certified = {prompt: value for prompt, value in qualified.items()
                 if passes(prompt, validation) >= validation_target}
    witness = next((case for case in validation if not cells[start][case][0]), None)
    screened_candidates = {prompt: value for prompt, value in certified.items() if prompt in screened}
    remaining = cap - len(validation) - len(screened)
    funded = {prompt: value for prompt, value in screened_candidates.items()
              if validation_target - cells[prompt][witness][0] <= remaining}
    return {'roster': available, 'qualification': qualified, 'validation-and-qualification': certified,
            'paid-screen': screened_candidates, 'funded-after-screen': funded,
            'nomination': {prompt: value for prompt, value in funded.items() if prompt == nominee}}


def headroom(menus_by_stage, start_score, actual_score):
    previous = None
    extra = {}
    for name in MENU_NAMES:
        ceiling = max([start_score, actual_score, *menus_by_stage[name].values()])
        gain = ceiling - actual_score
        if previous is not None and gain > previous:
            raise ValueError('Each successive menu must be a subset of the preceding one')
        extra[name] = gain
        previous = gain
    return extra


def measure_panel(subject, matrix, plan):
    cells = {str(index): tuple((int(passed), None, False) for passed in vector) for index, vector in enumerate(matrix)}
    totals = {label: Counter() for label in prior.METHODS}
    events = {label: Counter() for label in prior.METHODS}
    traces = {label: [] for label in prior.METHODS}
    ceilings = {label: {stage: Counter() for stage in MENU_NAMES} for label in prior.METHODS}
    for seed in plan['seeds']:
        start, roster, cohorts = prior.fixed.archive.transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
        arguments = cells, start, roster, cohorts, seed
        retain = sum(cells[start][case][0] for case in cohorts[-1])
        for label in prior.METHODS:
            point, trace, _, audit, screened = observed_trial(arguments, label)
            nominee, deployed = trace[2:4]
            if nominee != start and nominee not in screened:
                raise ValueError('Every nominee must have received a paid validation check')
            options = menus(cells, start, roster, cohorts, screened, nominee, cap=plan['candidateSearchCap'])
            if deployed != start and deployed not in options['nomination']:
                raise ValueError('The actual deployment must clear the two strict gates')
            actual = point['holdoutPasses']
            for stage, extra in headroom(options, retain, actual).items():
                ceilings[label][stage].update(extraPasses=extra, trialsWithHeadroom=int(extra > 0))
            totals[label].update({metric: point[metric] for metric in prior.cost.METRICS})
            events[label].update(audit, nominations=int(nominee != start), promotions=int(deployed != start))
            traces[label].append(trace)
    return totals, events, {label: digest(trace) for label, trace in traces.items()}, ceilings


def replay(plan, panels, archived):
    totals, events, coverage, details = {}, {}, {}, {}
    for subject, model, matrix in panels:
        panel = f'{subject}/{model}'
        points, counts, traces, ceilings = measure_panel(subject, matrix, plan)
        anchor = archived['panels'][panel]
        if counts != anchor['events'] or traces != anchor['decisionTracesSha256']:
            raise ValueError('The archive audit must reproduce the original panel decisions and paid evidence')
        for label in prior.METHODS:
            totals.setdefault(label, Counter()).update(points[label])
            events.setdefault(label, Counter()).update(counts[label])
            scoped = coverage.setdefault(label, {})
            for name, ceiling in ceilings[label].items():
                scoped.setdefault(name, Counter()).update(ceiling)
        details[panel] = ceilings
    if events != archived['events'] or any(totals[label] != archived['totals'][label] for label in totals):
        raise ValueError('The audit must reproduce the original transfer outcomes')
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'totals': totals,
            'ceilings': coverage, 'panels': details}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
