"""Require a paid paired repair before widening stalled first-gain validation."""

import argparse
from dataclasses import replace
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import first_gain_tail_paired_audit as audit
from benchmarks import first_gain_validation_tail as tail
from cpo._contract import digest


width = tail.previous
transfer = tail.transfer
REFERENCE = audit.REFERENCE
PRIMARY = 'first-gain/tail-with-repair'
POLICIES = {PRIMARY: 'repair', 'first-gain/tail-with-balanced-repair': 'balanced',
            'first-gain/tail-with-one-scout': 'scout'}
EXTRA = 6
_SHORT = width.screen
_GROUP = width.verify_group


class RetainAfterShortPanel(Exception):
    """A stalled short screen lacks a paid reason to continue."""


def has_repair(incumbent, challengers, *, balanced):
    for challenger in challengers:
        paired = [(incumbent[row], grade) for row, grade in challenger.items() if row in incumbent]
        wins = sum(not base and candidate for base, candidate in paired)
        losses = sum(base and not candidate for base, candidate in paired)
        if wins and (not balanced or wins >= losses):
            return True
    return False


def screen(policy, incumbent, candidates, rows, evaluate, cap, *, prepaid, read_limit):
    funded = len(tail.first_gain._schedule(len(candidates), rows, min(cap, tail.first_gain._UNIFORM_CAP), False))
    if funded <= tail.PREFIX:
        return _SHORT(tail.PREFIX, incumbent, candidates, rows, evaluate, cap,
                      prepaid=prepaid, read_limit=read_limit)

    def guarded_short(prefix, start, roster, panel, read, cap, *, prepaid, read_limit):
        observed = {prompt: {} for prompt in (start, *roster)}

        def track(prompt, row):
            reply = read(prompt, row)
            observed[prompt][row.id] = reply.passed
            return reply

        short, rates = _SHORT(prefix, start, roster, panel, track, cap, prepaid=prepaid, read_limit=read_limit)
        if short.finalist is not None:
            return short, rates
        base = observed[start]
        if has_repair(base, (observed[prompt] for prompt in roster), balanced=policy == 'balanced'):
            return short, rates

        paid = short.evaluations
        if policy == 'scout' and paid < min(cap, read_limit):
            target = next(((prompt, row) for row in panel[:prefix] if base.get(row.id) is False
                           for prompt in roster if row.id not in observed[prompt]), None)
            if target is not None:
                witness = track(*target).passed
                short = replace(short, evaluations=paid + 1)
                if witness:
                    return short, rates
        raise RetainAfterShortPanel(short)

    with patch.object(width, 'screen', guarded_short):
        try:
            return tail.screen(EXTRA - (policy == 'scout'), incumbent, candidates, rows, evaluate, cap,
                               prepaid=prepaid, read_limit=read_limit)
        except RetainAfterShortPanel as stopped:
            return stopped.args[0], None


def run(arm, incumbent, training, cycles, evaluate, *, probe, qualify):
    if arm not in POLICIES:
        return tail.run(arm, incumbent, training, cycles, evaluate, probe=probe, qualify=qualify)
    with patch.object(tail.first_gain, '_screen', partial(screen, POLICIES[arm])):
        return width.earlier.parity.packaged(18, incumbent, training, cycles, evaluate, probe=probe, qualify=qualify)


def prepare():
    parent, math, prompt, controls, comparison, _ = tail.prepare()
    reference = transfer.locked('docs/first-gain-validation-tail-v1.json', REFERENCE)
    if digest(parent) != reference['planSha256'] or digest(reference['plan']) != reference['planSha256']:
        raise ValueError('The published ungated widening study must reproduce')
    fingerprints = {str(path.relative_to(transfer.donor.ROOT)): sha256(path.read_bytes()).hexdigest()
                    for path in (Path(__file__), Path(audit.__file__))}
    plan = {
        'protocol': 'cpo-first-gain-tail-witness-v1', 'primary': PRIMARY, 'policies': POLICIES, 'extraReadCap': EXTRA,
        'previousReceiptSha256': REFERENCE, 'previousPlanSha256': reference['planSha256'],
        'sourceSha256': {**parent['sourceSha256'], **fingerprints},
        'promptolutionCorpusSha256': parent['promptolutionCorpusSha256'], 'draws': 4096, 'seed': 49017,
        'scope': ('Gate the six-read continuation after a stalled short panel on one paid matched repair, '
                  'a repair with at least as many paired wins as losses for that challenger, or a repair with '
                  'one optional scout read. '
                  'The scout reserves one of six reads. Widened nominations still need an exact full-panel '
                  'strict gain and independent qualification. Reproduce prior controls and compare against '
                  'fixed three-case and ungated six-read CPO with paired question resampling.'),
    }
    return plan, math, prompt, controls, comparison, reference


def measure(plan, config, layouts, matrix, prices, expected, controls, *, math):
    tracked = ('first-gain/validation-3', tail.PRIMARY, *POLICIES)
    held_by_episode = {(start, seed): held for start, _, held, seed in layouts}
    cases = sorted({case for held in held_by_episode.values() for case in held})
    indexes = {case: index for index, case in enumerate(cases)}
    vectors = {arm: [0] * len(cases) for arm in tracked}
    original = width.earlier.parity.measure

    def capture(runner, config, matrix, windows, seed, arm):
        result = original(runner, config, matrix, windows, seed, arm)
        if arm in tracked:
            (final, _, trace), _ = result
            width.earlier.parity.prompt_study.verify_deployment(matrix, windows, trace[1])
            for case in held_by_episode[transfer.donor.START, seed]:
                vectors[arm][indexes[case]] += int(matrix[final][case])
        return result

    with patch.object(width.earlier.parity, 'measure', capture):
        result = _GROUP(config, layouts, matrix, prices, expected, controls, math=math)
    if any(sum(vector) != result['arms'][arm]['totals']['holdoutPasses'] for arm, vector in vectors.items()):
        raise ValueError('Every tracked held-out appearance must contribute to its question')
    comparisons = {(policy, control): (policy, (control,)) for policy in POLICIES for control in tracked[:2]}
    paired = audit.paired({arm: tuple(vector) for arm, vector in vectors.items()}, comparisons,
                          draws=plan['draws'], seed=plan['seed'])
    return {**result, 'questions': len(cases),
            'paired': {policy: {control: paired[policy, control] for control in tracked[:2]} for policy in POLICIES}}


def replay(plan, math, prompt, controls, comparison, reference, corpus):
    modes = {**width.WIDTHS, **{name: name for name in (*tail.TAILS, *POLICIES)}}
    with patch.multiple(width, WIDTHS=modes, run=run, verify_group=partial(measure, plan)):
        results = width.replay(math, prompt, controls, comparison, corpus)
    pairs = [(results['math'][subject][group], original) for subject, groups in reference['math'].items()
             for group, original in groups.items()]
    pairs.extend((results['promptolution'][group], original) for group, original in reference['promptolution'].items())
    for current, original in pairs:
        if current['episodes'] != original['episodes'] or any(
                current['arms'][name] != arm for name, arm in original['arms'].items()):
            raise ValueError('Every ungated comparison must reproduce')
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute', metavar='PLAN_SHA256')
    cli.add_argument('--corpus', type=Path)
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if not (args.execute or args.out or args.corpus):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or args.corpus is None:
        cli.error('Use the current seal, pinned corpus and a fresh output path')
    corpus = transfer.donor.load_corpus(args.corpus.read_bytes())
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, **replay(plan, *inputs, corpus)}
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
