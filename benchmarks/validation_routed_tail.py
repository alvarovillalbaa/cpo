"""Test a paid four-case prefix with a conditional uniform validation tail."""

import argparse
from dataclasses import replace
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import validation_routed_depth as prior
from cpo._contract import digest
from cpo.full_roster_precheck import fixed_opening
from cpo.full_roster_precheck.validation_routing import run_validation_routed_episode
from cpo.ordered_uniform_validation import MISSES, screen as ordered_screen
from cpo.quoted_shared_validation_cycle import _schedule
from cpo.settled_episode import _MAX_VALIDATION_READS
from cpo.two_sided_certificate_cycle import _run


PARENT_RECEIPT = '15d7875e8f32e2f20144e1f11993c643dfc733fd7caec7bad744f297bbc4aac4'
TAILS = {'stalled-uniform-tail': False, 'close-uniform-tail': True}
PREFIX = 4
UNIFORM_CAP = 18


def screen(incumbent, candidates, rows, evaluate, cap, *, extend_one_pass):
    cap = min(cap, UNIFORM_CAP)
    funded = tuple(row for row, _ in _schedule(len(candidates), rows, cap, False))
    if len(candidates) != 2 or len(funded) <= PREFIX or any(row.critical for row in rows):
        return ordered_screen(incumbent, candidates, rows, evaluate, cap, order=MISSES)

    paid = {prompt: {} for prompt in (incumbent, *candidates)}

    def read(prompt, row):
        known = paid[prompt]
        if row.id not in known:
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Conditional validation requires exact boolean replies')
            known[row.id] = reply
        return known[row.id]

    def race(panel):
        result, scores = ordered_screen(incumbent, candidates, panel, read, cap, order=MISSES)
        return replace(result, evaluations=sum(map(len, paid.values()))), scores

    short, scores = race(funded[:PREFIX])
    if short.finalist is not None:
        if extend_one_pass and scores[1][0] - scores[0][0] == 1:
            return race(funded)
        return short, scores

    incumbent_score = sum(reply.passed for reply in paid[incumbent].values())
    rival_upper = len(funded) - min(sum(not reply.passed for reply in paid[prompt].values())
                                  for prompt in candidates)
    for row in funded[PREFIX:]:
        if incumbent_score >= rival_upper:
            break
        incumbent_score += read(incumbent, row).passed
    if incumbent_score >= rival_upper:
        return replace(short, evaluations=sum(map(len, paid.values()))), None
    return race(funded)


def run_tail(extend_one_pass, incumbent, _training, cycles, evaluate, *, probe, qualify):
    original = fixed_opening._cycle

    def adaptive(schedule, start, cycle, read, proof):
        if (schedule != prior.language.OPENING or len(cycle.candidates) != 2
                or len(cycle.validation) <= PREFIX or any(row.critical for row in cycle.validation)):
            return original(schedule, start, cycle, read, proof)
        return _run(start, cycle.candidates, cycle.validation, cycle.qualification, read,
                    metric_limit=_MAX_VALIDATION_READS, qualify=proof, seed=cycle.seed,
                    screen=partial(screen, extend_one_pass=extend_one_pass))

    with patch.object(fixed_opening, '_cycle', adaptive):
        return run_validation_routed_episode(incumbent, cycles, evaluate, qualify=qualify)


RUNNERS = {**prior.RUNNERS, **{name: partial(run_tail, extend) for name, extend in TAILS.items()}}


def prepare():
    baseline, width, prompt = prior.prepare()
    reference = prior.transfer.locked('docs/validation-routed-depth-v1.json', PARENT_RECEIPT)
    if digest(baseline) != reference['planSha256'] or digest(reference['plan']) != digest(baseline):
        raise ValueError('The fixed-depth comparison must match its archived seal')
    relative = 'benchmarks/validation_routed_tail.py'
    plan = {**baseline, 'protocol': 'cpo-validation-routed-tail-v1', 'arms': tuple(RUNNERS),
            'parentReceiptSha256': PARENT_RECEIPT, 'prefixRows': PREFIX, 'tailExtendsOnePass': TAILS,
            'sourceSha256': {**baseline['sourceSha256'], relative: sha256(Path(__file__).read_bytes()).hexdigest()},
            'scope': ('Use an exact four-case decision before extending uniform validation on narrow rosters. '
                      'When the short race retains, probe the incumbent tail until no rival can win or until '
                      'a full race is needed. The second variant also extends one-pass nominees. Reuse every '
                      'paid reply and keep the original funded panel, other schedules and independent gate.')}
    return plan, width, prompt, reference


def verify_totals(current, reference):
    if current.keys() != reference.keys():
        raise ValueError('Use the exact fixed-depth task and cohort roster')
    for name, row in reference.items():
        totals = current[name]['totals']
        if any(totals[arm] != stats for arm, stats in row['totals'].items()):
            raise ValueError(f'The fixed-depth control totals must reproduce for {name}')


def replay(plan, width, prompt, reference, archive):
    prompt_plan, *_ = prior.prompt.prepare()
    policies = {**prior.DEPTHS, **TAILS}
    with patch.multiple(prior, RUNNERS=RUNNERS, DEPTHS=policies):
        with patch.dict(prior.prompt.RUNNERS, {name: RUNNERS[name] for name in policies}):
            promptolution = prior.prompt_replay(prompt_plan, prompt, archive)
        language = prior.language_replay(plan, width)
    verify_totals(promptolution['tasks'], reference['promptolution']['tasks'])
    verify_totals(language, reference['language'])
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'language': language, 'promptolution': promptolution}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, width, prompt, reference = prepare()
    seal = digest(plan)
    if not (args.execute or args.out or args.corpus):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if (args.execute != seal or not args.out or args.out.exists() or not args.corpus
            or version('gepa') != plan['gepaVersion']):
        parser.error('Replay requires the pinned corpus, current seal, pinned GEPA and a fresh output path')
    archive = prior.transfer.donor.load_corpus(args.corpus.read_bytes())
    result = replay(plan, width, prompt, reference, archive)
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
