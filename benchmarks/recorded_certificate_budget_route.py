"""Route certificate screening by affordable best-case proof count."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_sequential_certificate_screen as published
from cpo import prechecked_certificate_cycle as reserved
from cpo import sequential_certificate_cycle as sequential
from cpo import threshold_prechecked_cycle as threshold
from cpo._contract import digest


frontier = published.prior
ARCHIVE = 'benchmarks/data/shortlist-model-transfer-v1.json'
ARCHIVE_SHA256 = 'de2369fce95132c95fea9d84f5b4d3b80b96b484bcf0f9ae0f0602081c535859'
REFERENCE = 'docs/sequential-certificate-cycle-results-v1.json'
REFERENCE_SHA256 = '9ff2aa90229bdcbe805de1a75644c18161641a572f16e198ce30cbbd9be6df9b'
ROOT = frontier.cost.transfer.ROOT
RETAIN = published.RETAIN
POLICIES = {gain: f'two-funded-certificates/gain-{gain}' for gain in published.POLICIES}
BATCH_SCREEN = reserved._screen


def target_groups(entries, development):
    panels = frontier.anchors.language.load_panels(entries)
    targets = {}
    for family, group in panels.items():
        seen_tasks = {subject for subject, _, _ in development[family]}
        seen_models = {model for _, model, _ in development[family]}
        for subject, model, matrix in group:
            if model in seen_models:
                raise ValueError('The transfer requires checkpoints absent from the source language replay')
            scope = 'seen-task' if subject in seen_tasks else 'new-task'
            targets.setdefault(f'{family}/{scope}', []).append((subject, model, matrix))
    if set(targets) != {f'{family}/{scope}' for family in panels for scope in ('seen-task', 'new-task')}:
        raise ValueError('Each language family needs both kinds of task transfer')
    return targets


def prepare():
    parent, development, _, original = published.prepare()
    reference = frontier.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, parent)
    archive = (ROOT / ARCHIVE).read_bytes()
    if sha256(archive).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Use the sealed Flan and Minotaur matrices')
    transfer = target_groups(json.loads(archive)['panels'], development)
    sources = (Path(__file__), Path(reserved.__file__), Path(sequential.__file__),
               Path(threshold.__file__), Path(published.__file__), Path(frontier.anchors.language.__file__))
    plan = {**parent, 'protocol': 'recorded-certificate-budget-route-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': REFERENCE_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in sources},
            'targetArchiveSha256': ARCHIVE_SHA256,
            'targetPanels': {name: [panel[:2] for panel in panels] for name, panels in transfer.items()},
            'route': 'Use immediate certification when remaining validation reads cover two certificates '
                     'in the best case, each costing incumbent passes plus one. Otherwise use the reserved '
                     'probe batch. Reuse every incumbent validation reply and keep both qualification margins.',
            'gate': 'Within each cohort use at most the cheaper fixed policy’s paid lookups and retain '
                    'a nonnegative paired 95% lower endpoint against both fixed policies at the same gain.',
            'scope': 'Replay the two published fixed screens and the frozen routing rule on the original '
                     'panels. Transfer every rule unchanged to the separate archived checkpoint panels. '
                     'Separate tasks seen by those fixed screen studies from new task identities.'}
    return plan, {**development, **transfer}, reference['results'], original


def route_screen(incumbent, candidates, rows, evaluate, metric_limit, record):
    prefix = {row.id: evaluate(incumbent, row) for row in rows}
    if any(type(reply.passed) is not bool for reply in prefix.values()):
        raise ValueError('Routing needs paid boolean incumbent observations')
    accepted = sum(reply.passed for reply in prefix.values())
    immediate = metric_limit - len(prefix) >= 2 * (accepted + 1)
    record.append(immediate)
    screen = sequential._screen if immediate else BATCH_SCREEN

    def reuse(prompt, row):
        if prompt == incumbent:
            return prefix[row.id]
        return evaluate(prompt, row)

    return screen(incumbent, candidates, rows, reuse, metric_limit)


def measure_panel(subject, matrix, plan, controls=None):
    cells = {str(index): tuple((int(grade), None, False) for grade in row) for index, row in enumerate(matrix)}
    totals, vectors, paths, stats = {}, {}, {}, {}

    def tally(label, measured, grades, path=None):
        totals.setdefault(label, Counter()).update(measured)
        frontier.transfer.fitted.prior.add_vector(vectors.setdefault(label, [0] * len(grades)), grades)
        if path is not None:
            paths.setdefault(label, []).append(path)

    for seed in plan['seeds']:
        start, roster, cohorts = frontier.transfer.archive.transfer.schedule(
            subject, len(matrix[0]), len(matrix), seed, plan,
        )
        args = cells, start, roster, cohorts, seed
        held = tuple(cells[start][case][0] for case in cohorts[-1])
        tally(RETAIN, {'holdoutPasses': sum(held), 'paidLookups': 0}, held)
        for gain, label in POLICIES.items():
            batch = published.episode(args, plan['screenCap'], gain, threshold.run_threshold_prechecked_cycle)
            early = published.episode(args, plan['screenCap'], gain, sequential.run_sequential_certificate_cycle)
            seen = []

            def route(*args):
                return route_screen(*args, seen)

            with patch.object(reserved if gain == 1 else threshold, '_screen', route):
                routed = published.episode(args, plan['screenCap'], gain, threshold.run_threshold_prechecked_cycle)
            if len(seen) > 1 or routed != (early if seen == [True] else batch):
                raise ValueError('The route must reproduce the paid callbacks, result and grades of one fixed screen')
            tally(frontier.POLICIES[gain], *batch[:3])
            tally(published.POLICIES[gain], *early[:3])
            tally(label, *routed[:3])
            arm = 'immediate' if seen == [True] else 'reserved' if seen else 'no-validation'
            stats.setdefault(label, {}).setdefault(arm, Counter()).update(
                paths=1, immediateMinusReservedPasses=early[0]['holdoutPasses'] - batch[0]['holdoutPasses'],
                immediateMinusReservedLookups=early[0]['paidLookups'] - batch[0]['paidLookups'],
                differentDeployments=int(early[3].prompt != batch[3].prompt),
            )
    fingerprints = {label: digest(path) for label, path in paths.items()}
    if controls and any(fingerprints[label] != path for label, path in controls.items()):
        raise ValueError('Every original fixed-policy callback path must reproduce')
    return totals, vectors, fingerprints, stats


def measure_cohort(panels, plan, parent=None, original=None):
    totals, subjects, fingerprints, strata = {}, {}, {}, {}
    for subject, model, matrix in panels:
        panel = f'{subject}/{model}'
        control = ({**parent['panelPathHashes'][panel], **original['panelPathHashes'][panel]} if parent else None)
        points, vectors, fingerprints[panel], stats = measure_panel(subject, matrix, plan, control)
        scores = subjects.setdefault(subject, {})
        for label, point in points.items():
            totals.setdefault(label, Counter()).update(point)
            frontier.transfer.fitted.prior.add_vector(scores.setdefault(label, [0] * len(vectors[label])), vectors[label])
        for label, paths in stats.items():
            for arm, change in paths.items():
                strata.setdefault(label, {}).setdefault(arm, Counter()).update(change)
    if parent and any(totals[label] != point for label, point in parent['totals'].items()):
        raise ValueError('The original fixed-policy totals must reproduce')
    comparisons = {}
    for gain, label in POLICIES.items():
        batch, early = frontier.POLICIES[gain], published.POLICIES[gain]
        paired = {control: published.paired_effect(subjects, label, control, plan) for control in (batch, early)}
        paths = strata[label].get('immediate', Counter())
        totals_delta = {'immediateMinusReservedPasses': totals[label]['holdoutPasses'] - totals[batch]['holdoutPasses'],
                        'immediateMinusReservedLookups': totals[label]['paidLookups'] - totals[batch]['paidLookups']}
        if any(paths[key] != value for key, value in totals_delta.items()):
            raise ValueError('Changes must occur only on paths that route to immediate certification')
        if any(rows['holdoutPassDifference'] != totals[label]['holdoutPasses'] - totals[control]['holdoutPasses']
               for control, rows in paired.items()):
            raise ValueError('The paired case totals must reconcile with the observed margins')
        comparisons[label] = {'pairedAgainstFixed': paired,
                              'passedGate': totals[label]['paidLookups'] <= min(totals[batch]['paidLookups'],
                                                                                totals[early]['paidLookups'])
                              and all(point['pairedRange95'][0] >= 0 for point in paired.values())}
    return {'totals': totals, 'strata': strata, 'comparisons': comparisons, 'panelPathHashes': fingerprints}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, reference, original = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh output path')
    outcomes = {name: measure_cohort(panels, plan, reference.get(name), original.get(name))
                for name, panels in groups.items()}
    with args.out.open('x') as destination:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': outcomes},
                  destination, indent=2, sort_keys=True)
        destination.write('\n')


if __name__ == '__main__':
    main()
