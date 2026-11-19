"""Test whether earlier search stalls predict when to widen the screen."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks.prompteval_paid_witness import meets_gate
from cpo._contract import digest
from cpo.fixed_pool_cycle import run_fixed_pool_cycle


DEFERRED = 'deferred-first-gain'
WIDE = 'bounded-two-reads'
ADAPTIVE = {
    'after-empty': (1, 'empty', False),
    'once-after-two-empty': (2, 'empty', True),
    'once-after-two-unpromoted': (2, 'unpromoted', True),
}
METHODS = (DEFERRED, WIDE, *ADAPTIVE)


class ScreenSchedule:
    def __init__(self, method):
        self.method = method
        self.incumbent = None
        self.empty = self.unpromoted = 0
        self.choices = []
        self.wide_promotions = 0

    def choose(self, incumbent):
        if incumbent != self.incumbent:
            self.empty = self.unpromoted = 0
            self.incumbent = incumbent
        screen = self.method
        if screen in ADAPTIVE:
            threshold, signal, once = ADAPTIVE[screen]
            reached = getattr(self, signal) >= threshold
            screen = WIDE if reached and (not once or WIDE not in self.choices) else DEFERRED
        self.choices.append(screen)
        return screen

    def observe(self, result):
        self.empty = self.empty + 1 if result.search.finalist is None else 0
        self.unpromoted = self.unpromoted + 1 if not result.promoted else 0
        self.wide_promotions += int(self.choices[-1] == WIDE and result.promoted)


def run_episode(matrix, held, seed, original, plan, method):
    schedule = ScreenSchedule(method)

    def select(incumbent, *args, **kwargs):
        result = run_fixed_pool_cycle(incumbent, *args, screen=schedule.choose(incumbent), **kwargs)
        schedule.observe(result)
        return result

    with patch.object(archive, 'run_fixed_pool_cycle', select):
        totals, trace = archive.episode(matrix, held, seed, original, plan, 'recency')
    return totals, trace, schedule


def prepare(phase):
    parent, original, data, gepa, fixed = archive.prepare(phase)
    plan = {
        **{k: parent[k] for k in ('phase', 'gepaReportSha256', 'fixedPoolReportSha256', 'gepaVersion',
                                'searchCap', 'validationRows', 'gate')},
        'protocol': 'cpo-episode-screen-adaptation-v1',
        'archivePlanSha256': digest(parent),
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'methods': list(METHODS), 'rules': ADAPTIVE,
        'scope': ('Select each fresh screen from earlier fresh cycles on the current incumbent. '
                  'Keep the recency archive, search ceiling and qualification panel fixed.'),
    }
    return plan, original, data, gepa, fixed


def paired_deltas(passes, reference):
    offsets = [a - b for a, b in zip(passes, reference, strict=True)]
    return {'gains': sum(d > 0 for d in offsets), 'ties': offsets.count(0), 'losses': sum(d < 0 for d in offsets)}


def replay(plan, original, data, gepa, fixed):
    panels = {}
    for panel in data:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        methods, passes = {}, {}
        for method in METHODS:
            total, traces, choices = Counter(), [], []
            passes[method] = []
            for seed in original['seeds']:
                measured, trace, schedule = run_episode(matrix, held, seed, original, plan, method)
                wide = schedule.choices.count(WIDE)
                total.update(measured)
                total.update(wideFreshCycles=wide, wideEpisodes=int(wide > 0),
                             widePromotions=schedule.wide_promotions, freshCycles=len(schedule.choices))
                passes[method].append(measured['holdoutPasses'])
                traces.append(trace)
                choices.append(schedule.choices)
            methods[method] = {
                **total, 'paidLookups': total['searchPaid'] + total['qualificationPaid'],
                'callbackTraceSha256': digest(traces), 'screenChoicesSha256': digest(choices),
                'pairedPassesVsDeferred': paired_deltas(passes[method], passes[DEFERRED]),
            }
        for control in (DEFERRED, WIDE):
            current, expected = methods[control], fixed[name][control]
            fields = {'searchLogical': 'searchLookups', 'searchPaid': 'searchAfterReuse',
                      'qualificationPaid': 'qualificationAfterStop', 'holdoutPasses': 'holdoutPasses',
                      'paidLookups': 'paidLookups'}
            if (current['callbackTraceSha256'] != expected['callbackTraceSha256'] or
                    any(current[k] != expected['totals'][v] for k, v in fields.items())):
                raise ValueError(f'{name} {control} differs from the published control')
        controls = {mode: {k: result[k] for k in ('holdoutPasses', 'paidLookups')}
                    for mode, result in gepa[name]['reinvested'].items()}
        gates = {method: {mode: meets_gate(result, control) for mode, control in controls.items()}
                 for method, result in methods.items()}
        panels[name] = {'methods': methods, 'gepa': controls, 'gates': gates}
    qualified = {m: [name for name, row in panels.items() if all(row['gates'][m].values())] for m in METHODS}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels, 'panelsClearingBothGates': qualified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=archive.controls.reference.transfer.SOURCES, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current phase seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
