"""Measure lossless validation savings on the frozen episode schedules."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import episode_admission_transfer as admission
from cpo._contract import digest
from cpo.perfect_challenger_screen import screen
from cpo.two_sided_certificate_cycle import _run


previous, frontier, discovery = admission.previous, admission.frontier, admission.discovery
native, parent, transfer, depth = admission.native, admission.parent, admission.transfer, admission.depth
BOUNDED, BOTH, SCHEDULE, RETAIN = admission.BOUNDED, admission.BOTH, admission.SCHEDULE, admission.RETAIN
COMMON = 'common-hindsight-schedule'
FIT_SHA = '3c6bcae203c01317b48cf5702ba6cb3e8f0d78d3dd78610528f16381f87d9617'
LOCKS = dict(zip(discovery.COHORTS, (
    '0a668dc7ed69e5e5f22f4c176bc46680a021024a4d54e7e2e7739d8f57e2b85c',
    '0b049d1b72395b6c72ef7cb3e3344c4b588cb01bc8c81c0d65ac4011129f20ed',
    'fd03730070efa733d2d5939dc45bcd40a3657338f270986c179d0da60c7f780a',
    '52b3fa507a2212352bb7668e276ea8a5ec281bbb7a5fb9eaa1982f01277c517d',
    'd82a6dbef1e4af92ece7ef9becf57a6f1d44c3ed7fe69a036d9c0b9441c8e2de',
    'c6afe422f1a6f63aa7fe8be4b4dc59f0788f621c586dd7c03b8318f1ea681bac',
    'efdd1fb551813b58c691edb5ace0cceb3c3ab69794bf884b13e17262b1c6a3e4',
), strict=True))


def prepare(cohort):
    inherited, probe_plan, _, probe_fit = admission.contract()
    trained = json.loads(transfer.read_locked('docs/episode-admission-fit-v1.json', FIT_SHA))
    original, inputs = admission.target(cohort, inherited, probe_plan, probe_fit, trained)
    lock = LOCKS[cohort]
    receipt = json.loads(transfer.read_locked(f'docs/episode-admission-transfer-{cohort.lower()}-v1.json', lock))
    if receipt['planSha256'] != digest(original):
        raise ValueError('The episode admission replay must reproduce its sealed plan')
    frontier_results = inputs[-2]
    common = tuple(frontier_results['frontiers'][frontier.COMMON]['selectedActions'])
    if len(common) != 1:
        raise ValueError('The archived common policy must use one original setting')
    root = transfer.ROOT
    files = (Path(__file__).resolve(), root / 'cpo/perfect_challenger_screen.py')
    plan = {**original, 'protocol': 'perfect-challenger-transfer-v1', 'admissionFitSha256': FIT_SHA,
            'admissionTransferSha256': lock, 'commonSetting': common[0],
            'sourceSha256': {**original['sourceSha256'],
                             **{str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest() for file in files}},
            'scope': 'Keep the existing episode routing and search schedules. Replace quoted search only '
                     'when the incumbent score means a challenger must be perfect. Verify every original '
                     'nomination, qualification decision, deployment and paid lookup subset. Reprice the '
                     'combined episode rule, wider-search control and original common hindsight schedule.'}
    return plan, (*inputs[:-1], receipt['results'])


def limit(incumbent, candidates, rows, evaluate, cap, *, width, maximum, halve):
    return screen(incumbent, candidates[:width], rows, evaluate, min(cap, maximum), halve=halve)


def variants(plan):
    return {name: partial(_run, screen=partial(limit, width=width, maximum=cap, halve=mode == 'successive-halving'))
            for name, mode, width, cap in plan['controls']}


def compare_cycle(before, after, cells, start, stage, cap):
    seed, roster, roles = stage
    run = native.paired.cycle.execute_path
    original, paid = run(before, cells, start, roster, roles, seed, cap, 1)
    candidate, kept = run(after, cells, start, roster, roles, seed, cap, 1)
    if ((original.search.finalist, original.search.prompt, original.qualification)
            != (candidate.search.finalist, candidate.search.prompt, candidate.qualification)):
        raise ValueError('Validation ordering must preserve the original nomination and exact qualification')
    if not kept.items() <= paid.items() or len(paid) - len(kept) != original.search.evaluations - candidate.search.evaluations:
        raise ValueError('The new order must read only original grades and save only validation lookups')
    depth.continuous.routing.verify_qualification(cells, start, roles, candidate, kept, 1)
    return candidate.prompt, len(paid), len(kept)


def measure(plan, panels, models, static, gepa, simple, frontier_results, original):
    fixed, _ = frontier.engines(plan, models, static)
    alternate = variants(plan)
    cap = max(limit for _, _, _, limit in plan['controls'])
    names = (BOTH, SCHEDULE, COMMON)
    outcomes = {name: Counter() for name in names}
    effects = {name: Counter() for name in names}
    vectors = {}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for subject, _, _, cells, stages, start in previous.episodes(plan, panels):
        branches = admission.actions(plan, cells, stages, start)
        choices = {name: branches[name] for name in (BOTH, SCHEDULE)}
        choices[COMMON] = plan['commonSetting'], ()
        held = stages[0][2][-1]
        grades = vectors.setdefault(subject, {})
        for name, (setting, ledger) in choices.items():
            current = start
            before, after = len(ledger), len(ledger)
            if setting != RETAIN:
                for stage in stages:
                    current, paid, kept = compare_cycle(fixed[setting], alternate.get(setting, fixed[setting]),
                                                        cells, current, stage, cap)
                    before += paid
                    after += kept
                    effects[name].update(eligibleCycles=int(setting in alternate), savingCycles=int(paid > kept))
            audit = [cells[current][case] for case in held]
            outcomes[name].update(holdoutPasses=sum(audit), oldLookups=before, paidLookups=after)
            add(grades.setdefault(name, [0] * len(held)), audit)
    reference = {BOTH: original['policies'][BOTH], SCHEDULE: original['policies'][SCHEDULE],
                 COMMON: frontier_results['frontiers'][frontier.COMMON]}
    budget = frontier_results['budget']
    comparisons = {}
    for name, totals in outcomes.items():
        expected = reference[name]
        if totals['holdoutPasses'] != expected['holdoutPasses'] or totals['oldLookups'] != expected['paidLookups']:
            raise ValueError('Every original policy must reproduce its archived scores and charges')
        pool = {subject: dict(scores) for subject, scores in vectors.items()}
        spend = totals['paidLookups']
        controls = parent.compare_simple(plan, panels, simple, spend, pool)
        bounds, _ = parent.compare_native(plan, panels, gepa, spend,
                                           simple['settingsTotals'][RETAIN]['holdoutPasses'], pool)
        comparisons[name] = {'savedValidationLookups': totals['oldLookups'] - spend, 'withinBoundedBudget': spend <= budget,
                             'nativeBoundsAtBudget': bounds, 'simpleAtBudget': controls, **effects[name]}
    return {'episodes': len(panels) * len(plan['seeds']), 'boundedBudget': budget, 'policies': outcomes,
            'comparisons': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=discovery.COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, inputs = prepare(args.cohort)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    receipt = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': measure(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
