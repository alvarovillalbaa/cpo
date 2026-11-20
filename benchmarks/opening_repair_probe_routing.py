"""Choose paid training probes from input features that predict validation errors."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_provisional_repair as earlier
from benchmarks.case_difficulty_allocation import checked_file
from cpo._contract import digest
from cpo.expected_cost_proposal_cycle import ExpectedCostProposalCycleResult
from cpo.opening_screen_cycle import run_opening_screen_cycle
from cpo.optimizer import balanced_order
from cpo.paired_qualification import certify_paired_qualification


REFERENCE = 'ff5f98c7dae5059ddd6775cbd2f416684f885a222b14b3e1f2fec5deb389df7b'
SOURCE = earlier.SOURCE
TYPED = SOURCE.typed
PRIMARY = 'routed-probes'
FRESH_SEEDS = (59107, 59141)


def select_probes(ordered, validation, features, count):
    """Rank training cases by features disproportionately present in failed validation."""
    failed, passed = Counter(), Counter()
    misses = 0
    for row_id, exact_pass in validation:
        (passed if exact_pass else failed).update(features[row_id])
        misses += not exact_pass
    successes = len(validation) - misses
    weights = {key: max(0, hits * successes - passed[key] * misses) for key, hits in failed.items()}
    if not any(weights.values()):
        weights = failed
    return sorted(ordered, key=lambda row: sum(weights.get(k, 0) for k in features[row.id]), reverse=True)[:count]


def repaired_cycle(features):
    def run(incumbent, train, validation, holdout, evaluate, propose, *, opening_pair, metric_limit,
            qualify, seed, field_credit, repeats, rounds, train_per_round):
        ledger = {}

        def observe(prompt, row):
            key = prompt, row.id
            if key not in ledger:
                if len(ledger) >= metric_limit:
                    raise ValueError('The routed repair exceeded the search ceiling')
                reply = evaluate(prompt, row)
                if type(reply.passed) is not bool:
                    raise ValueError('Search requires an exact boolean outcome')
                ledger[key] = reply
            return ledger[key]

        def deferred(*_):
            raise ValueError('Only the final nominee can qualify')

        opening = run_opening_screen_cycle(
            incumbent, train, validation, holdout, observe, opening_pair=opening_pair, metric_limit=metric_limit,
            qualify=deferred, seed=seed, field_credit=field_credit, repeats=repeats, qualification_limit=0)
        result = opening.search
        accepted = parent = result.prompt
        if accepted == incumbent:
            return opening

        events, used, reflections = list(result.events), set(), 0
        training = balanced_order(train, seed)
        for attempt in range(2):
            outcomes = [(row.id, ledger[parent, row.id].passed) for row in validation]
            if all(passed for _, passed in outcomes):
                break
            remaining = [row for row in training if row.id not in used]
            count = min(2, len(remaining), metric_limit - len(ledger) - len(validation))
            if count <= 0:
                break
            probes = select_probes(remaining, outcomes, features, count)
            used.update(row.id for row in probes)
            stripped = SOURCE.api.strip_demonstrations(parent)
            feedback = [(row, observe(stripped, row)) for row in probes]
            event = {'kind': PRIMARY, 'probeRows': [row.id for row in probes], 'status': 'no-training-error'}
            events.append(event)
            if all(reply.passed for _, reply in feedback):
                break
            repair = propose(parent, feedback, [], 1).rewrite
            reflections += 1
            if repair in (incumbent, parent, accepted):
                event['status'] = 'duplicate'
                break
            gains = Counter()
            critical_loss, row_preserving = False, True
            for row in validation:
                old, new = ledger[accepted, row.id], observe(repair, row)
                critical_loss |= row.critical and old.passed and not new.passed
                row_preserving &= old.passed == new.passed and new.matched_fields >= old.matched_fields
                gains[row.family] += new.passed - old.passed
            if not critical_loss and min(gains.values()) >= 0 and sum(gains.values()) > 0:
                event['status'] = 'accepted'
                accepted = parent = repair
            elif attempt == 0 and row_preserving:
                event['status'] = 'provisional'
                parent = repair
            else:
                event['status'] = 'rejected'
                break

        result = replace(result, prompt=accepted, evaluations=len(ledger), reflections=reflections, events=events)
        decision = certify_paired_qualification(incumbent, accepted, holdout, qualify, repeats=repeats, seed=seed)
        return ExpectedCostProposalCycleResult(result, decision)

    return run


def prepare():
    parent, cohorts, previous = earlier.prepare()
    control = checked_file('docs/opening-provisional-repair-results-v1.json', REFERENCE)
    if digest(parent) != control['designSha256']:
        raise ValueError('The earlier repair protocol changed')
    fresh = {f'{task}/{profile}/{seed}': SOURCE.make_panel(task, profile, seed)
             for task in SOURCE.TASKS for profile in SOURCE.PROFILES for seed in FRESH_SEEDS}
    cohorts = {**cohorts, 'probe-transfer': fresh}
    inputs = [row['input'] for panels in cohorts.values() for groups in panels.values()
              for split in groups.values() for row in split]
    if len(inputs) != len(set(inputs)):
        raise ValueError('The probe transfer overlaps earlier panel inputs')
    design = {'protocol': 'cpo-opening-repair-probe-routing-v1', 'referenceReportSha256': REFERENCE,
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'primary': PRIMARY, 'primaryCohort': 'probe-transfer', 'searchCap': parent['searchCap'],
              'newDatasetSha256': {key: digest(value) for key, value in fresh.items()},
              'gate': parent['gate'], 'gepaVersion': parent['gepaVersion'],
              'scope': ('Use paid binary validation outcomes and the input features they share with training '
                        'to choose training probes. Keep proposal feedback limited to training observations.')}
    return design, cohorts, previous, control['results']


def measure(panels, *, frozen=None, reference=None):
    trials = []
    summarize = TYPED.summary

    def capture(records):
        if len(records) == len(panels) and earlier.PRIMARY in records[0]['arms']:
            trials.extend(records)
        return summarize(records)

    with patch.object(TYPED, 'summary', capture):
        baseline = earlier.measure(panels, frozen=frozen)
    if reference is not None and baseline != reference:
        raise ValueError('The previous probe-routing control changed')
    for trial in trials:
        task, profile, seed = trial['task'], trial['profile'], trial['seed']
        groups = panels[f'{task}/{profile}/{seed}']
        keys = SOURCE.TASKS[task][0]
        features = {}
        for label in ('train', 'validation'):
            for row in groups[label]:
                inputs = TYPED.fixture.facts(row['input'])
                features[row['id']] = tuple((key, inputs[key]) for key in keys)
        with (patch.object(TYPED, 'FAMILY_FIELD', {key: item[0][0] for key, item in SOURCE.TASKS.items()}),
              patch.object(TYPED.fixture, 'respond', SOURCE.opening_response(profile)),
              patch.object(TYPED.programs, 'complete', SOURCE.complete),
              patch.object(TYPED.feedback, 'observed_repair', SOURCE.repair_response)):
            trial['arms'][PRIMARY] = SOURCE.diagnostic.rerun_repair(task, groups, seed, SOURCE.CAP,
                                                                  repaired_cycle(features))
    with (patch.object(TYPED, 'ARMS', (*baseline['totals'], PRIMARY)),
          patch.object(TYPED, 'CPO', (PRIMARY, 'cpo-adaptive'))):
        report = summarize(trials)
        report['profiles'] = {profile: summarize([trial for trial in trials if trial['profile'] == profile])
                              for profile in SOURCE.PROFILES}
    report['probeOutcomes'] = dict(Counter(event['status'] for t in trials for event in t['arms'][PRIMARY]['events']
                                          if event['kind'] == PRIMARY))
    report['traceSha256'] = digest(trials)
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, cohorts, previous, control = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        cli.error('Use GEPA 0.1.4')
    results = {name: measure(panels, frozen=previous if name == 'prior-panels' else None,
                             reference=control.get(name)) for name, panels in cohorts.items()}
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
