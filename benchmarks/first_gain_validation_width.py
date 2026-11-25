"""Replay shorter validation panels with the original independent qualification."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import first_gain_precheck_stopping as prior
from cpo._contract import digest
from cpo.single_finalist import FinalistResult


earlier = prior.earlier
first_gain = earlier.first_gain
transfer = earlier.transfer
BASE = earlier.BASE
PRECHECK = 'stop-correlated-12'
PRIMARY = 'first-gain/validation-2'
WIDTHS = {f'first-gain/validation-{width}': width for width in (1, 2, 3)}
REFERENCE = '528b3704411f969432c186ae811c5545960b615ebcc29950dcbd31dbe3770b38'
_SCREEN = first_gain._screen


def screen(width, incumbent, candidates, rows, evaluate, cap, *, prepaid, read_limit):
    """Use a fixed prefix as the full uniform validation panel."""
    if len(rows) < 3 or cap < 9:
        return _SCREEN(incumbent, candidates, rows, evaluate, cap, prepaid=prepaid, read_limit=read_limit)
    if width == 3:
        return _SCREEN(incumbent, candidates, rows[:width], evaluate, cap,
                       prepaid=prepaid, read_limit=read_limit)

    panel = rows[:width]
    prompts = (incumbent, *candidates)
    state = ((0, 0),) * len(prompts)
    seen = ({}, {}, {})

    def observe(side, row):
        nonlocal state
        grade = evaluate(prompts[side], row).passed
        if type(grade) is not bool:
            raise ValueError('A validation certificate requires an exact Boolean grade')
        seen[side][row.id] = grade
        state = first_gain._advance(state, side, grade)

    for row in panel:
        if row.id in prepaid:
            observe(0, row)
    spent = sum(map(len, seen))
    limit = min(read_limit, width * len(prompts), cap)
    while True:
        winner = first_gain._strict_winner(width, state)
        if winner is not None:
            nominee = prompts[winner]
            rates = tuple((state[side][0], sum(state[side])) for side in (0, winner))
            return FinalistResult(nominee, nominee, spent), rates
        _, _, side = first_gain._choose_read(width, state, limit - spent)
        if side is None:
            return FinalistResult(incumbent, None, spent), None
        pending = (row for row in panel if row.id not in seen[side])
        row = min(pending, key=lambda row: seen[0].get(row.id) is not False) if side else next(pending)
        observe(side, row)
        spent += 1


def run(width, incumbent, training, cycles, evaluate, *, probe, qualify):
    with patch.object(first_gain, '_screen', partial(screen, width)):
        return earlier.parity.packaged(18, incumbent, training, cycles, evaluate, probe=probe, qualify=qualify)


def prepare():
    plan, math, prompt, controls, _ = prior.prepare()
    reference = transfer.locked('docs/first-gain-precheck-stopping-v1.json', REFERENCE)
    if digest(plan) != reference['planSha256'] or digest(reference['plan']) != reference['planSha256']:
        raise ValueError('Use the published terminal stopping plan and results')
    source = Path(__file__)
    return {
        'protocol': 'cpo-first-gain-validation-width-v1', 'primary': PRIMARY, 'uniformWidths': WIDTHS,
        'controls': (BASE, PRECHECK), 'previousReceiptSha256': REFERENCE,
        'previousPlanSha256': reference['planSha256'], 'promptolutionCorpusSha256': plan['promptolutionCorpusSha256'],
        'sourceSha256': {**plan['sourceSha256'], str(source.relative_to(transfer.donor.ROOT)):
                         sha256(source.read_bytes()).hexdigest()},
        'scope': ('Use the first one, two or three cases of the existing three-to-six-case uniform screen as '
                  'its full validation panel. '
                  'Keep the opening probes, other schedules, original candidate rosters, admission cases and '
                  'holdouts. Compare realized costs and holdout passes across all groups. Preserve the prior '
                  'cost and score totals for the packaged baseline and best aggregate terminal rule.'),
    }, math, prompt, controls, reference


def verify_group(config, layouts, matrix, prices, expected, controls, *, math):
    runners = {BASE: partial(earlier.parity.packaged, 18), PRECHECK: partial(prior.run, PRECHECK),
               **{name: partial(run, width) for name, width in WIDTHS.items()}}
    totals = {name: Counter() for name in runners}
    changes = {name: Counter() for name in runners if name != BASE}
    metrics = ('paidLookups', earlier.sweep.math.PRICE) if prices is not None else ('paidLookups',)
    for start, windows, held, seed in layouts:
        with patch.object(transfer.donor, 'START', start):
            measured = {name: earlier.parity.measure(runner, config, matrix, windows, seed, name)[0]
                        for name, runner in runners.items()}
            base_prompt, _, _ = measured[BASE]
            base_score = sum(int(matrix[base_prompt][case]) for case in held)
            for name, (prompt, cost, (_, _, ledger)) in measured.items():
                score = sum(int(matrix[prompt][case]) for case in held)
                totals[name].update(cost, holdoutPasses=score)
                if math:
                    totals[name]['promotions'] += prompt != start
                if prices is not None:
                    totals[name][metrics[1]] += sum(prices[entry][case] for (_, entry, case), _ in ledger)
                if name != BASE:
                    changes[name].update(changedDeployment=int(prompt != base_prompt), morePasses=int(score > base_score),
                                         fewerPasses=int(score < base_score))
    if totals[BASE] != expected['totals'][BASE]:
        raise ValueError('The packaged baseline must reproduce')
    published = controls['totals']
    native = tuple(name for name in published if name.startswith('gepa-'))
    halving = tuple(name for name in published if name.startswith('halving/'))
    results = {}
    for name, stats in totals.items():
        results[name] = {'totals': stats, 'matchedPoints': {
            metric: {'nativeGepa': earlier.best_affordable(published, stats[metric], metric, (*native, transfer.BASE)),
                     'halving': earlier.best_affordable(published, stats[metric], metric, (*halving, transfer.BASE))}
            for metric in metrics}}
        if name != BASE:
            results[name]['relativeToPackagedDeployment'] = changes[name]
    return {'episodes': len(layouts), 'arms': results}


def replay(math, prompt, controls, reference, corpus):
    with patch.object(earlier, 'verify_group', verify_group):
        results = {'math': earlier.math_replay(math, controls['math']),
                   'promptolution': earlier.prompt_replay(prompt, controls['promptolution']['tasks'], corpus)}
    pairs = [(results['math'][subject][group], original) for subject, groups in reference['math'].items()
             for group, original in groups.items()]
    pairs.extend((results['promptolution'][group], original) for group, original in reference['promptolution'].items())
    for comparison, original in pairs:
        if comparison['episodes'] != original['episodes']:
            raise ValueError('The full archive must reproduce')
        for name in (BASE, PRECHECK):
            arm = comparison['arms'][name]
            if any(arm[key] != original['arms'][name][key] for key in ('totals', 'matchedPoints')):
                raise ValueError(f'The published {name} control must reproduce')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if not (args.execute or args.out or args.corpus):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or args.corpus is None:
        parser.error('Use the current seal, pinned corpus and a fresh output path')
    corpus = transfer.donor.load_corpus(args.corpus.read_bytes())
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, **replay(*inputs, corpus)}
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
