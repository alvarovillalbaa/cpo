"""Test whether the witness gate detects a position-sensitive shared error."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks import grounded, grounded_fixture, grounded_witness_ordered_futility as ordered
from benchmarks import witness_regime_coverage as coverage
from cpo._contract import digest


PARENT_SEAL = 'ce048ab5da16f4b3a4162ddc67097a6e16717826afb2236170b08a6b63a866dc'
CANDIDATE = ordered.parent.CANDIDATE


def permute(task, inputs):
    separator = '. ' if task == 'ticket' else '; '
    first, *rest = inputs.removesuffix('.').split(separator)
    changed = separator.join([*rest, first]) + '.'
    if changed == inputs or len(changed.encode()) != len(inputs.encode()) or (
            grounded_fixture.facts(changed) != grounded_fixture.facts(inputs)):
        raise ValueError('A field-order change must retain the exact facts and input size')
    return changed


def confirmation_panels(groups):
    shifted, probes = {}, {}
    for task, regions in groups.items():
        rows = regions['confirmation']
        critical = [row['id'] for row in rows if row['critical']]
        ordinary = [row['id'] for row in rows if not row['critical']]
        ids = {*critical[:2], *ordinary[:2]}
        if len(ids) != 4 or len(rows) != 8:
            raise ValueError('Use two critical and two ordinary probes in the eight-case confirmation panel')
        original = {row['input'] for panel in regions.values() for row in panel}
        probes[task] = [row['id'] for row in rows if row['id'] in ids]
        panel = []
        for row in rows:
            if row['id'] in ids:
                inputs = permute(task, row['input'])
                if inputs in original:
                    raise ValueError('A reordered input must be distinct from every original case')
                original.add(inputs)
                row = {**row, 'input': inputs}
            panel.append(row)
        shifted[task] = {**regions, 'confirmation': panel}
    return shifted, probes


def prepare():
    groups, parent, _ = ordered.prepare()
    if digest(parent) != PARENT_SEAL:
        raise ValueError('Use the exact published ordered development plan')
    shifted, probes = confirmation_panels(groups)
    sources = (Path(__file__).resolve(), Path(coverage.__file__).resolve())
    plan = {'protocol': 'witness-confirmation-field-order-v1', 'parentPlanSha256': PARENT_SEAL,
            'sourceSha256': {file.relative_to(ordered.original.ROOT).as_posix(): sha256(file.read_bytes()).hexdigest()
                             for file in sources},
            'confirmationDatasetSha256': digest({task: regions['confirmation'] for task, regions in shifted.items()}),
            'probeIdsByTask': probes, 'minimumExactPassesPerProbe': 1,
            'rule': 'Move the first fact field to the end for the first two critical and first two ordinary '
                    'confirmation cases per task. Preserve their labels, IDs, repeat count, and byte lengths.',
            'scenarios': ['order-agnostic', 'one-shared-wrong-reply-per-probe', 'persistent-shared-error-on-each-probe',
                          'persistent-shared-error-on-all-probes']}
    return groups, shifted, plan


def absolute_verdict(probes, observed, minimum):
    if observed is None:
        return {'status': 'unmeasured'}
    counts = {task: dict.fromkeys(ids, 0) for task, ids in probes.items()}
    for task, rows in observed.items():
        for row in rows:
            if row['id'] in counts[task]:
                counts[task][row['id']] += row['passes'][CANDIDATE]
    failed = {task: [case for case, count in cases.items() if count < minimum] for task, cases in counts.items()}
    return {'status': 'rejected' if any(failed.values()) else 'qualified', 'passesByCase': counts, 'failedCases': failed}


def sample_key(sample):
    return (sample.request['task'], sample.case['id'], sample.request['repeat'], sample.arms)


def measure(plan, groups, shifted, directory):
    respond = ordered.fixture_responder(groups, 'qualifying')
    ordered.run(PARENT_SEAL, directory, respond, delivery='fixture')
    _, inherited, prior = ordered.prepare(directory)
    old = ordered.study.order(ordered.original.scoring_schedule(groups, prior['selected'], 'confirmation'),
                              ordered.study.GATE)
    new = ordered.study.order(ordered.original.scoring_schedule(shifted, prior['selected'], 'confirmation'),
                              ordered.study.GATE)
    if len(new) != inherited['requestCeiling'] or [sample_key(sample) for sample in new] != list(map(sample_key, old)):
        raise ValueError('Only facts in the selected confirmation requests may change')
    originals = {sample_key(sample): sample for sample in old}
    for before, after in zip(old, new, strict=True):
        if ({**before.request, 'input': after.request['input']} != after.request or
                {**before.case, 'input': after.case['input']} != after.case):
            raise ValueError('Field order may change only the input in each request and case')
    baseline = ordered.run(digest(inherited), directory.with_name('confirmation'), respond,
                           delivery='fixture', development=directory)
    probes = plan['probeIdsByTask']
    probe_ids = {case for ids in probes.values() for case in ids}

    def run(faulty, repeats):
        def grade(sample):
            task, case = sample.request['task'], sample.case
            if case['id'] in faulty and sample.request['repeat'] in repeats:
                answer = json.dumps(coverage.mutation(task, case['expected']), sort_keys=True)
            else:
                answer = respond(originals[sample_key(sample)].request)
            return grounded.score(answer, case['expected'])[0]

        scoring, outcome = ordered.original.score_until_rejected(new, inherited, prior['searchCosts'], grade)
        absolute = absolute_verdict(probes, outcome.get('holdout'), plan['minimumExactPassesPerProbe'])
        paired = scoring['status'] == 'qualified'
        return {'pairedQualified': paired, 'absolute': absolute, 'qualified': paired and absolute['status'] == 'qualified',
                'scoring': scoring, 'scoringEvidenceSha256': digest(outcome)}

    control = run(set(), set())
    if not control['qualified'] or control['scoringEvidenceSha256'] != digest({
            'holdout': baseline['holdout'], 'verdicts': baseline['verdicts']}):
        raise ValueError('Order-agnostic replies must reproduce the original confirmation verdict and grades')
    repeats = range(grounded.REPEATS)
    cases = {case: run({case}, repeats) for case in sorted(probe_ids)}
    snapshot = ordered.archive_bytes(directory)
    return {'parentConfirmationPlanSha256': digest(inherited), 'scheduledRequests': len(new),
            'changedRequests': sum(before.request != after.request for before, after in zip(old, new, strict=True)),
            'originalScheduleSha256': inherited['scoringScheduleSha256'],
            'developmentArchiveSha256': {name: sha256(raw).hexdigest() for name, raw in snapshot.items()},
            'probeCases': {task: [{'canonical': before, 'reordered': after['input']}
                                  for before, after in zip(groups[task]['confirmation'], regions['confirmation'], strict=True)
                                  if before['id'] in probe_ids] for task, regions in shifted.items()},
            'orderAgnostic': control, 'oneMissPerProbe': run(probe_ids, {0}),
            'persistentSharedErrorByCase': cases, 'allProbesFail': run(probe_ids, repeats)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    groups, shifted, plan = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    with TemporaryDirectory(prefix='cpo-confirmation-field-order-') as scratch:
        detail = measure(plan, groups, shifted, Path(scratch) / 'development')
    with args.out.open('x') as report:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, **detail}, report, indent=2, sort_keys=True)
        report.write('\n')


if __name__ == '__main__':
    main()
