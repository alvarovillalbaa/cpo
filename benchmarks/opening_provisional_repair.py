"""Allow an exactly tied repair to provide context for one more proposal."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_second_repair as earlier
from benchmarks.case_difficulty_allocation import checked_file
from cpo._contract import digest
from cpo.expected_cost_proposal_cycle import ExpectedCostProposalCycleResult
from cpo.opening_repair_cycle import run_opening_repair_cycle
from cpo.optimizer import balanced_order
from cpo.paired_qualification import certify_paired_qualification


REFERENCE = '978f8c682b10a038d2331525ba1d22a32fdeaa2711f44e554dc540bb52123a16'
SOURCE = earlier.source
TYPED = SOURCE.typed
PRIMARY = 'provisional-repair'
FRESH_SEEDS = (58211, 58229)
PROBES = earlier.PROBES


def cycle(incumbent, train, validation, holdout, evaluate, propose, *, opening_pair, metric_limit,
          qualify, seed, field_credit, repeats, rounds, train_per_round):
    ledger = {}

    def observe(prompt, row):
        key = prompt, row.id
        if key not in ledger:
            if len(ledger) >= metric_limit:
                raise ValueError('The provisional repair exceeded the search ceiling')
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Search requires an exact boolean outcome')
            ledger[key] = reply
        return ledger[key]

    proposals = []

    def first_proposal(*args):
        options = propose(*args)
        proposals.append(options.rewrite)
        return options

    def deferred(*_):
        raise ValueError('Only the final nominee can qualify')

    once = run_opening_repair_cycle(
        incumbent, train, validation, holdout, observe, first_proposal, opening_pair=opening_pair,
        metric_limit=metric_limit, qualify=deferred, diagnostic_prompt=SOURCE.api.strip_demonstrations,
        max_training_probes=PROBES, seed=seed, field_credit=field_credit, repeats=repeats, qualification_limit=0,
    )
    result = once.search
    accepted = result.prompt
    if accepted == incumbent:
        return once
    first = result.events[-1]
    parent, candidate, calls = accepted, accepted, result.reflections
    parent_kind, status = 'accepted', 'first-repair-not-eligible'

    if first['status'] == 'rejected':
        (rejected,) = proposals
        paired = [(ledger[accepted, row.id], ledger[rejected, row.id]) for row in validation]
        if all(old.passed == new.passed and new.matched_fields >= old.matched_fields for old, new in paired):
            parent, parent_kind = rejected, 'provisional'
    if first['status'] == 'accepted' or parent_kind == 'provisional':
        status = 'validation-complete'
        if any(not ledger[accepted, row.id].passed for row in validation):
            used = {probe['row_id'] for probe in first['probes']}
            remaining = [row for row in balanced_order(train, seed) if row.id not in used]
            funded = min(PROBES, len(remaining), metric_limit - len(ledger) - len(validation))
            status = 'unfunded'
            if funded > 0:
                prompt = SOURCE.api.strip_demonstrations(parent)
                feedback = [(row, observe(prompt, row)) for row in remaining[:funded]]
                status = 'no-training-error'
                if any(not reply.passed for _, reply in feedback):
                    repair = propose(parent, feedback, [], 1).rewrite
                    calls += 1
                    status = 'duplicate'
                    if repair not in (incumbent, parent, accepted):
                        gains = Counter()
                        critical_loss = False
                        for row in validation:
                            old = ledger[accepted, row.id].passed
                            new = observe(repair, row).passed
                            critical_loss |= row.critical and old and not new
                            gains[row.family] += new - old
                        if not critical_loss and min(gains.values()) >= 0 and sum(gains.values()) > 0:
                            candidate, status = repair, 'accepted'
                        else:
                            status = 'rejected'

    event = {'kind': PRIMARY, 'status': status, 'parentKind': parent_kind,
             'addedLookups': len(ledger) - result.evaluations}
    result = replace(result, prompt=candidate, evaluations=len(ledger), reflections=calls,
                     events=[*result.events, event])
    decision = certify_paired_qualification(incumbent, candidate, holdout, qualify, repeats=repeats, seed=seed)
    return ExpectedCostProposalCycleResult(result, decision)


def prepare():
    parent, prior, _ = earlier.prepare()
    frozen = checked_file('docs/opening-second-repair-results-v1.json', REFERENCE)
    if digest(parent) != frozen['designSha256'] or set(FRESH_SEEDS).intersection(SOURCE.SEEDS):
        raise ValueError('The second-repair plan changed or its seeds overlap')
    fresh = {f'{task}/{profile}/{seed}': SOURCE.make_panel(task, profile, seed)
             for task in SOURCE.TASKS for profile in SOURCE.PROFILES for seed in FRESH_SEEDS}
    cohorts = {'prior-panels': prior, 'new-panels': fresh}
    inputs = [row['input'] for panels in cohorts.values() for groups in panels.values()
              for split in groups.values() for row in split]
    if len(set(inputs)) != len(inputs):
        raise ValueError('Policy transfer requires disjoint inputs across panels')
    design = {'protocol': 'cpo-opening-provisional-repair-v1', 'referenceReportSha256': REFERENCE,
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'primary': PRIMARY,
              'primaryCohort': 'new-panels', 'searchCap': parent['searchCap'], 'gepaVersion': parent['gepaVersion'],
              'newDatasetSha256': {name: digest(rows) for name, rows in fresh.items()}, 'gate': parent['gate'],
              'scope': ('A rejected repair can be a proposal parent when its validation pass pattern is identical '
                        'and it preserves field counts on each row. Only a strict improvement over the last '
                        'accepted candidate can replace it as the qualification nominee.')}
    return design, cohorts, frozen['results']


def measure(panels, frozen=None):
    baseline = []
    if frozen is not None:
        summarize = TYPED.summary

        def capture(trials):
            if len(trials) == len(panels) and earlier.PRIMARY in trials[0]['arms']:
                baseline.extend(trials)
            return summarize(trials)

        with patch.object(TYPED, 'summary', capture):
            if earlier.measure(panels, source_report()) != frozen:
                raise ValueError('The published second-repair benchmark changed')

    known = {(t['task'], t['profile'], t['seed']): t for t in baseline}
    trials = []
    for name, groups in panels.items():
        task, profile, suffix = name.split('/')
        seed = int(suffix)
        with (patch.object(TYPED, 'FAMILY_FIELD', {key: item[0][0] for key, item in SOURCE.TASKS.items()}),
              patch.object(TYPED.fixture, 'respond', SOURCE.opening_response(profile)),
              patch.object(TYPED.programs, 'complete', SOURCE.complete),
              patch.object(TYPED.feedback, 'observed_repair', SOURCE.repair_response)):
            def run(operation):
                return SOURCE.diagnostic.rerun_repair(task, groups, seed, SOURCE.CAP, operation)

            point = known.get((task, profile, seed))
            if point is None:
                point = TYPED.trial(task, groups, seed, SOURCE.CAP)
                point['profile'] = profile
                point['arms']['repair-two'] = run(SOURCE.staged.staged_cycle(2))
                point['arms'][SOURCE.PRIMARY] = run(SOURCE.api.packaged_cycle)
                point['arms'][earlier.PRIMARY] = run(earlier.second_repair_cycle)
            point['arms'][PRIMARY] = run(cycle)
        trials.append(point)
    with (patch.object(TYPED, 'ARMS', (*TYPED.ARMS, 'repair-two', SOURCE.PRIMARY, earlier.PRIMARY, PRIMARY)),
          patch.object(TYPED, 'CPO', (PRIMARY, 'cpo-adaptive'))):
        report = TYPED.summary(trials)
        report['profiles'] = {profile: TYPED.summary([t for t in trials if t['profile'] == profile])
                              for profile in SOURCE.PROFILES}
    report['provisionalOutcomes'] = dict(Counter(
        event['status'] for t in trials for event in t['arms'][PRIMARY]['events']
        if event['kind'] == PRIMARY and event['parentKind'] == 'provisional'))
    report['traceSha256'] = digest(trials)
    return report


def source_report():
    return checked_file('docs/opening-repair-policy-transfer-results-v1.json', earlier.REFERENCE)['results']


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, cohorts, previous = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        cli.error('Use GEPA 0.1.4')
    results = {name: measure(panels, frozen=previous if name == 'prior-panels' else None)
               for name, panels in cohorts.items()}
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
