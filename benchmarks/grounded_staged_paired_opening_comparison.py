"""Add the packaged paired opening to the sealed staged comparison."""

import argparse
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from benchmarks import grounded_staged_charge_comparison as baseline
from benchmarks import grounded_staged_policy_comparison as comparison
from cpo._contract import digest
from cpo.paired_opening import run_paired_opening_cycle


ARM = 'paired-opening'
ARMS = (*baseline.ARMS, ARM)
BASE_SEAL = '1c3fddb7fb18f56d23fee4b8a80a76dd8c1c1eda17044135acc36010efa4f375'
PROTOCOL = 'portable-grounded-staged-paired-opening-v1'
ARCHIVE_FILES = baseline.ARCHIVE_FILES
PricedReply = baseline.PricedReply
_prepare = baseline.prepare
_run = baseline.run
_replay = baseline.replay
_grade = baseline.grade
_choose = comparison.staged.choose


def prepare(development=None, **_):
    groups, base, _ = _prepare()
    if digest(base) != BASE_SEAL:
        raise ValueError('Use the exact sealed v6 portable baseline')
    tasks, repeats = len(groups), base['repeats']
    splits = comparison.staged.SPLITS
    limits = {'evaluation': tasks * 3 * splits['validation'],
              'admission': tasks * 2 * splits['admission'] * repeats,
              'qualification': tasks * splits['holdout'] * repeats}
    root = comparison.staged.ROOT
    files = ('benchmarks/grounded_staged_paired_opening_comparison.py', 'cpo/paired_opening/__init__.py',
             'cpo/family_qualification.py')
    plan = {**base, 'protocol': PROTOCOL, 'arms': list(ARMS), 'parentPlanSha256': BASE_SEAL,
            'scope': 'Original v6 comparison plus the packaged, exact paired opening and independent admission.',
            'sourceSha256': {**base['sourceSha256'], **{
                name: sha256((root / name).read_bytes()).hexdigest() for name in files}},
            'pairedOpening': {'selection': 'first exact validated gain with family and critical protection',
                              'proposalOrder': ['shared rewrite', 'shared repair'], 'laterProposals': 0,
                              'evaluationLimitPerTask': 3 * splits['validation'],
                              'confirmationRequires': ARM}}
    for key in ('logicalLimitsByRole', 'physicalLimitsByRole'):
        plan[key] = {role: count + limits.get(role, 0) for role, count in base[key].items()}
    plan['developmentRequestCeiling'] = sum(plan['physicalLimitsByRole'].values())
    if development is None:
        return groups, plan, None

    source = comparison.archive_bytes(development)
    with TemporaryDirectory(prefix='cpo-paired-opening-bind-') as scratch:
        prior = replay(development, Path(scratch) / 'verified')
    if comparison.archive_bytes(development) != source:
        raise ValueError('The development archive changed during confirmation binding')
    if ARM not in prior['outcome']['qualifyingPolicies']:
        raise ValueError('Independent confirmation requires the paired opening to pass development')
    # The two paired rewrite arms share the cached GEPA holdout and confirmation replies.
    count = tasks * (1 + len(ARMS) - 2) * splits['confirmation'] * repeats
    bound = {**plan, 'protocol': PROTOCOL + '-confirmation', 'gate': comparison.PANEL_GATE,
             'developmentPlanSha256': prior['planSha256'], 'developmentDelivery': prior['delivery'],
             'developmentArchiveSha256': {key: sha256(raw).hexdigest() for key, raw in source.items()},
             'developmentQualifyingPolicies': [ARM], 'promptsSha256': digest(prior['selected']),
             'logicalLimitsByRole': {'qualification': count}, 'physicalLimitsByRole': {'qualification': count},
             'confirmationRequestCeiling': count}
    del bound['developmentRequestCeiling']
    return groups, bound, prior


class Journal(comparison.Journal):
    def send(self, arm, request):
        if arm == ARM and request['role'] == 'reflection':
            return super().send('opening-only', request)
        if arm == ARM and request['role'] == 'evaluation':
            cap = 3 * comparison.staged.SPLITS['validation']
            if self.by_arm[request['task'], arm, 'evaluation'] >= cap:
                raise ValueError('The paired opening exceeded its sealed validation cap')
        return super().send(arm, request)


def select_opening(incumbent, _train, validation, admission, evaluate, *, opening_pair, qualify, repeats, seed, **_):
    # The shared opening adapter runs the same independent admission once for every arm.
    return run_paired_opening_cycle(incumbent, validation, admission, evaluate, opening_pair=opening_pair,
                                    metric_limit=3 * len(validation), qualify=qualify, qualification_limit=0,
                                    repeats=repeats, seed=seed)


def choose(task, groups, dispatch, **options):
    selected, decisions = _choose(task, groups, dispatch, **options)

    def respond(request):
        return dispatch(ARM, request['role'], request['instruction'], request['input'], repeat=request.get('repeat'))

    with patch.object(comparison.opening, 'run_opening_screen_cycle', select_opening):
        prompt, counts, status = comparison.opening.opening_only(task, groups, respond)
    selected[ARM] = prompt
    decisions[ARM] = {'admission': status, 'admissionLookups': counts['admission']}
    return selected, decisions


def grade(heldout, costs, gate, **_):
    outcomes = _grade(heldout, costs, gate)
    rows = {task: [{**row, 'passes': {**row['passes'], 'cpo': row['passes'][ARM]}} for row in panel]
            for task, panel in heldout.items()}
    verdict = comparison.staged.grade(rows, {**costs, 'cpo': costs[ARM]}, gate, controls=comparison.CONTROLS)
    verdict['passesByTask'][ARM] = verdict['passesByTask'].pop('cpo')
    outcomes['byPolicy'][ARM] = verdict
    if verdict['qualified']:
        outcomes['qualifyingPolicies'].append(ARM)
    return outcomes


def run(seal, directory, respond, *, delivery, development=None, **_):
    with (patch.multiple(comparison, prepare=prepare, grade=grade, Journal=Journal),
          patch.object(comparison.staged, 'choose', choose)):
        return _run(seal, directory, respond, delivery=delivery, development=development)


def replay(directory, fresh, *, development=None):
    with patch.object(comparison, 'run', run):
        return _replay(directory, fresh, development=development)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--fixture')
    mode.add_argument('--replay', type=Path)
    parser.add_argument('--development', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--profile', choices=comparison.opening.PROFILES, default='all-rewrites-faulted')
    args = parser.parse_args()
    if bool(args.fixture or args.replay) != bool(args.out):
        parser.error('Fixture and replay require a fresh output directory')
    if args.replay:
        result = replay(args.replay, args.out, development=args.development)
    elif args.fixture:
        respond = comparison.opening.PROFILES[args.profile]
        result = run(args.fixture, args.out, respond, delivery='fixture', development=args.development)
    else:
        _, frozen, _ = prepare(args.development)
        result = {**frozen, 'planSha256': digest(frozen)}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
