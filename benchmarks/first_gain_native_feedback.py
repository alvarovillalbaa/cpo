"""Bind native GEPA's actual training minibatch to its reflection payload."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from benchmarks import first_gain_independent_proposals as previous
from benchmarks.gepa_disjoint_cases import CaseRows
from cpo._contract import digest


ROOT = previous.parent.ROOT
PRIOR_PLAN = '80b96150569d3be6927f3f6d171d56b0b3b986e1bb210ccfa5b185d2dcfd376f'
PRIOR_RECEIPT = '38b6bf4dd817e5e390ee8f06e32ccb85f1e8e9d53ec45594d25610de344fbc0e'
NATIVE_ARMS = previous.parent.witness.GEPA
_CYCLE = previous.cycle
SIDE_INFO = 'cpo_paid_case_feedback'


def native(start, train, validation, observe, draft, *, seed, batched, paid):
    """Preserve the pinned GEPA controls and forward their selected trajectories."""
    from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig, TrackingConfig, optimize_anything
    from gepa.strategies.proposal_sampling import SameParentSampling
    from gepa.utils.stop_condition import ScoreThresholdStopper

    width = 2 if batched else 1
    train_ids = {row['id'] for row in train}

    def metric(prompt, example):
        reply = observe(prompt, example)
        if reply.feedback['id'] != example['id']:
            raise ValueError('The paid native observation differs from its case')
        return float(reply.passed), {SIDE_INFO: reply.feedback}

    def propose(candidate, observations, components):
        component, = components
        source = candidate[component]
        feedback = [row[SIDE_INFO] for row in observations[component]]
        if not 0 < len(feedback) <= previous.PROBES or any(row['id'] not in train_ids for row in feedback):
            raise ValueError('Native reflection needs the selected training minibatch')
        return {component: draft(source, previous.grounded.UPDATE, feedback) or source}

    config = GEPAConfig(
        engine=EngineConfig(seed=seed, parallel=False, use_cloudpickle=False, cache_evaluation=True,
                            max_metric_calls=previous.GEPA_CAP, max_candidate_proposals=previous.DRAFT_CAP // width,
                            track_best_outputs=False, sampling_strategy=SameParentSampling(width) if batched else None),
        reflection=ReflectionConfig(reflection_lm=None, custom_candidate_proposer=propose,
                                    reflection_minibatch_size=previous.PROBES),
        tracking=TrackingConfig(logger=previous.grounded.GepaLogger()),
        stop_callbacks=[ScoreThresholdStopper(1.0),
                        lambda _: len(paid) + width * (2 * previous.PROBES + len(validation)) > previous.GEPA_CAP],
    )
    return optimize_anything(start, evaluator=metric, dataset=CaseRows(train), valset=CaseRows(validation),
                             config=config).best_candidate


def cycle(use_sampled, trace, task, arm, incumbent, train, validation, admission, dispatch, journal, seen, seed):
    if arm not in NATIVE_ARMS:
        return _CYCLE(task, arm, incumbent, train, validation, admission, dispatch, journal, seen, seed)

    selected_feedback = None

    def run_native(start, train, validation, observe, draft, **settings):
        def reflect(source, instruction, feedback):
            nonlocal selected_feedback
            selected_feedback = source, feedback
            try:
                return draft(source, instruction)
            finally:
                selected_feedback = None

        return native(start, train, validation, observe, reflect, **settings)

    def send(owner, role, prompt, payload, **settings):
        if role == 'reflection':
            if selected_feedback is None or selected_feedback[0] != payload['current']:
                raise ValueError('Native reflection must use the selected parent and its training feedback')
            _, feedback = selected_feedback
            previous_feedback = payload['recentFeedback']
            if use_sampled:
                payload = {**payload, 'recentFeedback': feedback}
            trace.append({'task': task, 'arm': arm, 'cycleSeed': seed,
                          'sampled': [row['id'] for row in feedback],
                          'sent': [row['id'] for row in payload['recentFeedback']],
                          'recentlyPaid': [row['id'] for row in previous_feedback]})
        return dispatch(owner, role, prompt, payload, **settings)

    with patch.object(previous, 'native', run_native):
        return _CYCLE(task, arm, incumbent, train, validation, admission, send, journal, seen, seed)


def prepare():
    tasks, base = previous.prepare()
    lock = previous.shared.prior.prior.locked
    declared = lock('first-gain-independent-proposals-plan-v1.json', PRIOR_PLAN)
    receipt = lock('first-gain-independent-proposals-rehearsal-v1.json', PRIOR_RECEIPT)
    seal = declared.pop('planSha256')
    if digest(base) != seal or digest(declared) != seal or receipt['planSha256'] != seal:
        raise ValueError('The published independent-proposal baseline must reproduce')
    source = Path(__file__)
    plan = {**base, 'protocol': 'cpo-first-gain-independent-sampled-feedback-v1', 'previousPlanSha256': seal,
            'previousRehearsalSha256': PRIOR_RECEIPT,
            'sourceSha256': {**base['sourceSha256'], source.relative_to(ROOT).as_posix():
                             sha256(source.read_bytes()).hexdigest()},
            'nativeFeedbackRule': ('Give each native reflection its own GEPA-selected paid training trajectories, '
                                   'in their GEPA order, including cached observations and repeated rows. '
                                   'Preserve the labels, original parents, cases, budgets, and graders.')}
    return tasks, base, plan, receipt


def run_fixture(tasks, plan, output, *, use_sampled):
    trace = []
    with (previous.configured(tasks, plan), patch.object(previous, 'cycle', partial(cycle, use_sampled, trace))):
        result = previous.parent.run(digest(plan), output, previous.fixture(tasks), delivery='fixture')
    previous.staged.save(output / previous.AUDIT, previous.audit(tasks, result, output))
    return result, trace


def comparable_wire(directory):
    events = (directory / 'wire.jsonl').read_bytes().splitlines()
    for line in events:
        event = previous.grounded.load_json(line)
        if event.get('arm') in NATIVE_ARMS and event['request']['role'] == 'reflection':
            event['request']['input'].pop('recentFeedback')
        yield event


def verify(tasks, original, plan, expected, work):
    old, new = work / 'published', work / 'sampled'
    prior, before = run_fixture(tasks, original, old, use_sampled=False)
    fixed, after = run_fixture(tasks, plan, new, use_sampled=True)
    archive = {name: sha256((new / name).read_bytes()).hexdigest() for name in expected['archiveSha256']}
    if any(sha256((old / name).read_bytes()).hexdigest() != value for name, value in expected['archiveSha256'].items()):
        raise ValueError('The original fixture must reproduce byte for byte')
    if ({**fixed, 'planSha256': prior['planSha256']} != prior
            or list(comparable_wire(old)) != list(comparable_wire(new))):
        raise ValueError('Feedback correction changed a replay field outside the native reflection payloads')
    counts = {arm: Counter() for arm in NATIVE_ARMS}
    changes = []
    for original, corrected in zip(before, after, strict=True):
        if {**corrected, 'sent': original['sent']} != original or corrected['sent'] != original['sampled']:
            raise ValueError('The corrected payload must match the sampled training traces in order')
        counts[original['arm']]['reflections'] += 1
        if original['sampled'] != original['sent']:
            counts[original['arm']]['mismatchedFeedback'] += 1
            counts[original['arm']]['mismatchedMembership'] += Counter(original['sampled']) != Counter(original['sent'])
            changes.append(original)
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'originalFixtureMatched': True,
            'nativeFeedback': counts, 'changedReflections': changes, 'correctedArchiveSha256': archive,
            'physicalRequestsByRole': fixed['physicalCallsByRole'], 'searchCosts': fixed['searchCosts'],
            'qualifiedOnBothMeasures': fixed['qualifiedOnBothMeasures']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--fixture', metavar='PLAN_SHA256')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    tasks, base, plan, prior = prepare()
    seal = digest(plan)
    if not (args.fixture or args.out):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.fixture != seal or args.out is None or args.out.exists():
        cli.error('Use the current fixture seal and a fresh output path')
    with TemporaryDirectory(prefix='cpo-native-feedback-') as scratch:
        report = verify(tasks, base, plan, prior, Path(scratch))
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
