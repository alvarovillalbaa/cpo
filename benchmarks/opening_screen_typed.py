"""Compare the published opening screen on deterministic typed policy tasks."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import alternative_controls as programs
from benchmarks import feedback_budget as feedback
from benchmarks import grounded, grounded_fixture as fixture, typed_policy
from cpo import Observation, ProposalPair, Row
from cpo._contract import digest
from cpo.expected_cost_proposal_cycle import run_expected_cost_proposal_cycle
from cpo.opening_screen_cycle import run_opening_screen_cycle
from cpo.paired_qualification import certify_paired_qualification


ROOT = Path(__file__).resolve().parents[1]
CPO = ('opening-screen', 'cpo-adaptive')
GEPA = ('gepa-sequential', 'gepa-batched')
ARMS = ('retain-start', *CPO, *GEPA)
FAMILY_FIELD = {'ticket': 'Channel', 'warehouse': 'Site', 'outage': 'Plan'}


def gepa_select(initial, bank, groups, evaluate, reflect, *, cap, seed, width, reserve_round_reads=True):
    from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig, TrackingConfig, optimize_anything
    from gepa.strategies.proposal_sampling import SameParentSampling
    from gepa.utils.stop_condition import ScoreThresholdStopper

    train, validation = groups['train'], groups['validation']
    fields = len(train[0]['expected'])
    weight = 1 << (max(len(train), len(validation)) * fields).bit_length()
    opening = iter(bank)
    requests = 0

    def metric(prompt, example):
        nonlocal requests
        requests += 1
        reply = evaluate(prompt, example['id'])
        score = (reply.passed * weight + reply.matched_fields) / (weight + fields)
        return score, reply.feedback

    def propose(candidate, observations, components):
        component, = components
        parent = candidate[component]
        supplied = next(opening, None)
        return {component: supplied if supplied is not None else reflect(parent, observations)}

    probes = grounded.MINIBATCH
    stop_callbacks = [ScoreThresholdStopper(1.0)]
    if reserve_round_reads:
        stop_callbacks.append(lambda _: requests + width * (2 * probes + len(validation)) > cap)
    config = GEPAConfig(
        engine=EngineConfig(seed=seed, parallel=False, use_cloudpickle=False, cache_evaluation=True,
                            max_metric_calls=cap, max_candidate_proposals=grounded.REFLECTION_LIMIT // width,
                            track_best_outputs=False, sampling_strategy=SameParentSampling(width) if width > 1 else None),
        reflection=ReflectionConfig(reflection_lm=None, custom_candidate_proposer=propose,
                                    reflection_minibatch_size=probes),
        tracking=TrackingConfig(logger=grounded.GepaLogger()),
        stop_callbacks=stop_callbacks,
    )
    return optimize_anything(initial, evaluator=metric, dataset=train, valset=validation,
                             config=config).best_candidate


def trial(task, groups, seed, cap):
    training = groups['train']
    demos = tuple(sorted(Random(seed).sample(range(len(training)), programs.DEMO_COUNT)))
    request = {'role': 'reflection', 'task': task, 'instruction': grounded.OPENING,
               'input': {'current': grounded.BASELINE, 'labeledTraining': training}}
    opening = grounded.proposals(fixture.respond(request), grounded.BASELINE, ('rewrite', 'repair'))
    if len(opening) != 2:
        raise ValueError('The typed fixture must supply two distinct opening instructions')
    bank = tuple(programs.encode(prompt, demos) for prompt in opening)
    incumbent = programs.encode(grounded.BASELINE)

    def vector(split):
        return [Row(row['id'], fixture.facts(row['input'])[FAMILY_FIELD[task]],
                    row['critical'], len(row['expected'])) for row in groups[split]]

    train_rows, validation, qualification = map(vector, ('train', 'validation', 'confirmation'))
    search_rows = {row['id']: row for key in ('train', 'validation') for row in groups[key]}
    proof_rows = {row['id']: row for row in groups['confirmation']}

    def grade(prompt, example):
        raw = programs.complete(task, prompt, example['input'], training)
        passed, fields = grounded.score(raw, example['expected'])
        return Observation(passed, {'id': example['id'], 'observed': raw}, fields)

    def score_arm(arm):
        search_log, proof, reflections = {}, {}, []

        def evaluate(prompt, row_id):
            key = prompt, row_id
            if key not in search_log:
                if len(search_log) >= cap:
                    raise ValueError('The typed comparison exceeded its hard search ceiling')
                search_log[key] = grade(prompt, search_rows[row_id])
            return search_log[key]

        def qualify(prompt, row, repeat):
            key = prompt, row.id, repeat
            if key in proof:
                raise ValueError('Qualification repeated the same typed reply')
            passed = grade(prompt, proof_rows[row.id]).passed
            proof[key] = passed
            return passed

        def reflect(parent, recent_feedback):
            if 1 + len(reflections) >= grounded.REFLECTION_LIMIT:
                raise ValueError('The typed comparison exceeded its hard proposal ceiling')
            instruction = grounded.load_json(parent)['instruction']
            request = {'role': 'reflection', 'task': task, 'instruction': grounded.UPDATE,
                       'input': {'current': instruction, 'labeledTraining': training, 'recentFeedback': recent_feedback}}
            updated = grounded.load_json(feedback.observed_repair(request))['instruction']
            reflections.append((digest(request), digest(updated)))
            return programs.encode(updated, grounded.load_json(parent)['demos'])

        def propose(parent, samples, _history, _width):
            updated = reflect(parent, [reply.feedback for _, reply in samples])
            return ProposalPair(updated, programs.encode(grounded.load_json(updated)['instruction']))

        selected = incumbent
        nominee = incumbent
        events = []
        if arm in CPO:
            settings = dict(metric_limit=cap, opening_pair=ProposalPair(*bank), seed=seed,
                            field_credit=True, qualify=qualify, repeats=grounded.REPEATS)
            args = (incumbent, train_rows, validation, qualification, lambda prompt, row: evaluate(prompt, row.id))
            if arm == 'opening-screen':
                result = run_opening_screen_cycle(*args, **settings)
            else:
                result = run_expected_cost_proposal_cycle(
                    *args, propose, rounds=grounded.REFLECTION_LIMIT, train_per_round=grounded.MINIBATCH, **settings)
            selected, nominee, events = result.prompt, result.search.prompt, result.search.events
            if (result.search.evaluations, result.qualification_evaluations, result.search.reflections) != (
                    len(search_log), len(proof), len(reflections)):
                raise ValueError('The API disagreed with the typed callback counts')
        elif arm in GEPA:
            nominee = gepa_select(incumbent, bank, groups, evaluate, reflect,
                                  cap=cap, seed=seed, width=1 if arm == GEPA[0] else 2)
            if nominee != incumbent:
                selected = certify_paired_qualification(
                    incumbent, nominee, qualification, qualify, repeats=grounded.REPEATS, seed=seed).prompt

        held = {row['id']: grade(selected, row).passed for row in groups['holdout']}
        return {'selectedSha256': digest(selected), 'nominated': nominee != incumbent,
                'promoted': selected != incumbent, 'searchLookups': len(search_log),
                'qualificationLookups': len(proof), 'proposalCalls': int(arm != 'retain-start') + len(reflections),
                'holdout': held, 'events': events,
                'journalSha256': digest(([(p, i, r.passed, r.matched_fields) for (p, i), r in search_log.items()],
                                         [(*key, value) for key, value in proof.items()], reflections))}

    return {'task': task, 'seed': seed, 'cap': cap,
            'criticalHoldoutIDs': [row['id'] for row in groups['holdout'] if row['critical']],
            'arms': {arm: score_arm(arm) for arm in ARMS}}


def summary(trials):
    total = {}
    for arm in ARMS:
        rows = [t['arms'][arm] for t in trials]
        counts = Counter(holdoutPasses=sum(sum(r['holdout'].values()) for r in rows))
        for r in rows:
            counts.update({key: r[key] for key in
                           ('searchLookups', 'qualificationLookups', 'proposalCalls', 'nominated', 'promoted')})
        counts['countedCalls'] = sum(counts[key] for key in ('searchLookups', 'qualificationLookups', 'proposalCalls'))
        total[arm] = dict(counts)
    primary = CPO[0]
    minimum = min(sum(t['arms'][primary]['holdout'].values()) for t in trials)
    comparisons = {}
    for arm in (*GEPA, CPO[1]):
        critical_losses, panel_losses = 0, 0
        for t in trials:
            a, b = t['arms'][primary]['holdout'], t['arms'][arm]['holdout']
            critical_losses += sum(b[key] and not a[key] for key in t['criticalHoldoutIDs'])
            panel_losses += int(sum(a.values()) < sum(b.values()))
        gain = total[primary]['holdoutPasses'] - total[arm]['holdoutPasses']
        cost, control = total[primary]['countedCalls'], total[arm]['countedCalls']
        comparisons[arm] = {'passDelta': gain, 'callDelta': cost - control, 'criticalLosses': critical_losses,
                            'panelsWithLoss': panel_losses, 'passed': (
                                not critical_losses and not panel_losses and minimum >= 14
                                and ((gain >= 8 and cost <= control) or 10 * cost <= 9 * control))}
    return {'totals': total, 'comparisons': comparisons}


def prepare():
    cohorts = {seed: typed_policy.cohorts(seed) for seed in feedback.SEEDS}
    files = ('benchmarks/opening_screen_typed.py', 'benchmarks/alternative_controls.py',
             'benchmarks/feedback_budget.py', 'benchmarks/grounded.py', 'benchmarks/grounded_fixture.py',
             'benchmarks/typed_policy.py', 'cpo/opening_screen_cycle.py', 'cpo/expected_cost_proposal_cycle.py',
             'cpo/paired_qualification.py', 'cpo/optimizer.py', 'cpo/_contract.py')
    design = {'protocol': 'cpo-opening-screen-typed-v1', 'gepaVersion': '0.1.4', 'searchCaps': feedback.BUDGETS,
              'primaryCap': feedback.BUDGETS[-1], 'cohortsSha256': {str(s): digest(p) for s, p in cohorts.items()},
              'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
              'qualificationRepeats': grounded.REPEATS, 'methods': ARMS, 'familyFields': FAMILY_FIELD,
              'gate': ('Preserve every panel and matched critical pass with at least 14 exact passes per panel. '
                       'Gain eight aggregate passes at no added calls or save at least ten percent of calls.')}
    return design, cohorts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    design, cohorts = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        parser.error('Use GEPA 0.1.4')
    results = {}
    for cap in design['searchCaps']:
        trials = [trial(task, groups, seed, cap) for seed, tasks in cohorts.items() for task, groups in tasks.items()]
        results[str(cap)] = {**summary(trials), 'trials': trials}
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
