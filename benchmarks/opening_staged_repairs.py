"""Test training-only repair chains before one full validation and qualification."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_interaction_transfer as previous
from benchmarks.case_difficulty_allocation import checked_file
from benchmarks.opening_probe_robustness import paired
from cpo._contract import digest
from cpo.expected_cost_proposal_cycle import ExpectedCostProposalCycleResult
from cpo.opening_repair_cycle import _first_proposal
from cpo.opening_screen_cycle import run_opening_screen_cycle
from cpo.optimizer import balanced_order
from cpo.paired_qualification import certify_paired_qualification
from cpo.routed_repair_cycle import _categorical_features, _fallback_probes, _rank_probes


REFERENCE = 'da194cb6b5d3e85803515667654cc5d085c41b6eaf4c546720cddc467c3c3aaa'
PRIMARY = 'staged-repairs'
FRESH_SEEDS = (63029, 63059, 63067, 63103)
MAX_REPAIRS = 3
OPENING_FALLBACK = 12


def cycle(features, *, opening_witness_only=False, validation_probe_limit=0):
    def run(incumbent, train, validation, holdout, evaluate, propose, *, opening_pair, metric_limit, qualify,
            seed, field_credit, repeats, rounds, train_per_round):
        train, validation, holdout = tuple(train), tuple(validation), tuple(holdout)
        ledger, vectors = {}, {}

        def observe(prompt, row):
            key = prompt, row.id
            if key not in ledger:
                if len(ledger) >= metric_limit:
                    raise RuntimeError('The staged repair search exceeded its budget')
                ledger[key] = evaluate(prompt, row)
            return ledger[key]

        def vector(row):
            if row.id not in vectors:
                vectors[row.id] = _categorical_features(row, lambda case: features[case.id])
            return vectors[row.id]

        def deferred(*_):
            raise RuntimeError('Only the final nominee can enter qualification')

        opening = run_opening_screen_cycle(
            incumbent, train, validation, holdout, observe, opening_pair=opening_pair,
            metric_limit=metric_limit, qualify=deferred, repeats=repeats, seed=seed, field_credit=field_credit,
            qualification_limit=0,
        )
        result = opening.search
        anchor = parent = result.prompt
        if anchor == incumbent:
            return opening

        passed = [ledger[anchor, row.id].passed for row in validation]
        training = balanced_order(train, seed)
        event = {'kind': PRIMARY, 'stages': [], 'status': 'opening-retained'}
        reflections = 0
        if not all(passed) and len(ledger) + len(validation) < metric_limit:
            ranked = _rank_probes(training, validation, passed, vector)
            used, witnesses = set(), []
            proposed = {anchor, incumbent}
            for step in range(MAX_REPAIRS):
                capacity = metric_limit - len(ledger) - len(validation)
                if capacity <= 0:
                    break
                available = [row for row in ranked if row.id not in used]
                # Recheck witnesses on the new instruction. Its remaining errors
                # on these rows can reveal a second interacting rule.
                candidates = [*witnesses, *available][:min(train_per_round, capacity)]
                if validation_probe_limit and step > 0:
                    remaining_miss = None
                    checked = event.setdefault('residualChecks', [])
                    for row, anchor_passed in zip(validation, passed, strict=True):
                        if anchor_passed:
                            continue
                        if len(ledger) + len(validation) >= metric_limit:
                            break
                        current_passed = observe(parent, row).passed
                        checked.append((step, row.id, current_passed))
                        if not current_passed:
                            remaining_miss = row
                            break
                    if remaining_miss is None:
                        break
                    spare = metric_limit - len(ledger) - len(validation)
                    candidates = _rank_probes([*witnesses, *available], (remaining_miss,), (False,), vector)
                    candidates = candidates[:min(validation_probe_limit, spare)]
                diagnostic_prompt = previous.repair_api.strip_demonstrations(parent)
                feedback = []
                stop_at_failure = opening_witness_only if step == 0 else validation_probe_limit > 0
                for row in candidates:
                    reply = observe(diagnostic_prompt, row)
                    feedback.append((row, reply))
                    used.add(row.id)
                    if stop_at_failure and not reply.passed:
                        break
                if step == 0 and all(reply.passed for _, reply in feedback):
                    remaining = metric_limit - len(ledger) - len(validation)
                    for row in _fallback_probes(training, used, vector, min(OPENING_FALLBACK, remaining)):
                        reply = observe(diagnostic_prompt, row)
                        used.add(row.id)
                        feedback.append((row, reply))
                        if not reply.passed:
                            break
                witnesses = [row for row, reply in feedback if not reply.passed]
                event['stages'].append({'rows': [row.id for row, _ in feedback],
                                        'failedRows': [row.id for row in witnesses]})
                if not witnesses:
                    break
                candidate = _first_proposal(propose(parent, feedback, [], 1))
                reflections += 1
                if not isinstance(candidate, str) or not candidate.strip() or candidate in proposed:
                    break
                parent = candidate
                proposed.add(parent)

        if parent != anchor:
            gains = Counter()
            critical_loss = False
            for row in validation:
                before, after = ledger[anchor, row.id].passed, observe(parent, row).passed
                gains[row.family] += after - before
                critical_loss |= row.critical and before and not after
            if not critical_loss and min(gains.values()) >= 0 and sum(gains.values()) > 0:
                anchor = parent
                event['status'] = 'accepted'
            else:
                event['status'] = 'rejected'

        search = replace(result, prompt=anchor, evaluations=len(ledger), reflections=reflections,
                         events=[*result.events, event])
        decision = certify_paired_qualification(incumbent, anchor, holdout, qualify, repeats=repeats, seed=seed)
        return ExpectedCostProposalCycleResult(search, decision)

    return run


def prepare():
    upstream, development = previous.prepare()
    reference = checked_file('docs/opening-interaction-transfer-results-v1.json', REFERENCE)
    if digest(upstream) != reference['designSha256']:
        raise ValueError('The interaction reference changed')
    panels = {f'{task}/{profile}/{seed}': previous.panel(task, profile, seed)
              for task in previous.TASKS for profile in previous.FAULTS for seed in FRESH_SEEDS}
    rows = [row['input'] for groups in (*development.values(), *panels.values())
            for cases in groups.values() for row in cases]
    if len(set(rows)) != len(rows):
        raise ValueError('The transfer must use disjoint inputs')
    design = {'protocol': 'cpo-opening-staged-repairs-v1', 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'referenceReportSha256': REFERENCE, 'referenceDesignSha256': digest(upstream),
              'gepaVersion': upstream['gepaVersion'], 'searchCap': upstream['searchCap'], 'freshSeeds': FRESH_SEEDS,
              'maxRepairs': MAX_REPAIRS, 'openingFallback': OPENING_FALLBACK, 'gepaGate': upstream['gate'],
              'datasetSha256': {name: digest(groups) for name, groups in panels.items()}}
    return design, {'development': development, 'transfer': panels}, reference['results']


def compare(task, profile, seed, groups):
    baseline = previous.compare(task, profile, seed, groups)
    typed = previous.typed
    with (patch.object(typed, 'FAMILY_FIELD', {key: value[0][0] for key, value in previous.TASKS.items()}),
          patch.object(typed.fixture, 'respond', lambda request: previous.opening(profile, request)),
          patch.object(typed.programs, 'complete', previous.complete), patch.object(typed.feedback, 'observed_repair', previous.repair)):
        features = previous.feature_map(task, groups, True)
        baseline['arms'][PRIMARY] = previous.diagnostic.rerun_repair(task, groups, seed, previous.CAP, cycle(features))
    return baseline


def measure(cohorts, reference):
    phases = {}
    typed = previous.typed
    for phase, panels in cohorts.items():
        trials = []
        for name, groups in panels.items():
            task, fault, seed = name.split('/')
            trials.append(compare(task, fault, int(seed), groups))
        with (patch.object(typed, 'ARMS', (*typed.ARMS, previous.ATOMIC, previous.PRIMARY, PRIMARY)),
              patch.object(typed, 'CPO', (PRIMARY, 'cpo-adaptive'))):
            outcome = typed.summary(trials)
            outcome['profiles'] = {fault: typed.summary([trial for trial in trials if trial['profile'] == fault])
                                   for fault in previous.FAULTS}
        if phase == 'development' and any(outcome['totals'][key] != value for key, value in reference['totals'].items()):
            raise ValueError('A frozen development control changed')
        outcome['vsRouted'] = paired(trials, PRIMARY, previous.PRIMARY)
        outcome['traceSha256'] = digest(trials)
        outcome['stagedStatuses'] = dict(Counter(event['status'] for trial in trials
                                               for event in trial['arms'][PRIMARY]['events'] if event['kind'] == PRIMARY))
        outcome['callsPerPanel'] = {f"{t['task']}/{t['profile']}/{t['seed']}": {
            'stagedProposalCalls': t['arms'][PRIMARY]['proposalCalls'],
            'stagedPasses': sum(t['arms'][PRIMARY]['holdout'].values()),
            'routedPasses': sum(t['arms'][previous.PRIMARY]['holdout'].values())} for t in trials}
        phases[phase] = outcome
    return phases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    design, cohorts, reference = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        parser.error('Use GEPA 0.1.4')
    result = measure(cohorts, reference)
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': result}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
