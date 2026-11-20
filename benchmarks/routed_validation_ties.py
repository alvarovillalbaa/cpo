"""Use a certified validation tie only when strict search has no nominee."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import independent_mmlu_cost_frontier as frontier
from benchmarks import routed_model_cost_frontier as costs
from benchmarks import routed_start_model_confirmation as confirmation
from benchmarks import routed_start_protection as prior
from benchmarks import routed_witness_split as split
from benchmarks.four_case_qualification_transfer import interval
from cpo._contract import digest
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
CONFIRMATION_SHA = '7ff00010def728bee00dbe67b672b4e304807c68770c5310ce92fe4e958d10f0'
START_SHA = confirmation.PARENT_SHA256
PHASES = ('confirmation', *split.PHASES)
METHODS = {
    'strict': (None, 'ordinary'),
    'paid-tie': (0, 'ordinary'),
    'finish-two': (2, 'ordinary'),
    'finish-four': (4, 'ordinary'),
    'finish-four-two-gains': (4, 'two-gains'),
    'finish-four-split': (4, 'split'),
}
BASELINE = f'{confirmation.ROUTE}/{confirmation.CANDIDATE}'
FIELDS = frontier.FIELDS
AUDITED = 'finish-four'
PRIMARY = confirmation.PRIMARY


def certified_tie(incumbent, candidates, rows, ledger, observe, *, extra, metric_limit):
    """Finish a witnessed contender only when its optimistic total equals the incumbent."""
    if any((incumbent, row.id) not in ledger for row in rows):
        return None
    baseline = {row.id: ledger[incumbent, row.id].passed for row in rows}
    target = sum(baseline.values())
    protected = {row.id for row in rows if row.critical and baseline[row.id]}
    eligible = []
    for prompt in candidates:
        known = {row.id: ledger[prompt, row.id].passed for row in rows if (prompt, row.id) in ledger}
        if (any(known.get(case) is False for case in protected)
                or not any(passed and not baseline[case] for case, passed in known.items())):
            continue
        pending = [row for row in rows if row.id not in known]
        if len(pending) <= extra and sum(known.values()) + len(pending) == target:
            eligible.append((prompt, pending))
    limit = min(metric_limit, len(ledger) + extra)
    for prompt, pending in sorted(eligible, key=lambda item: len(item[1])):
        if len(ledger) + len(pending) > limit:
            continue
        ordered = sorted(pending, key=lambda row: row.id not in protected)
        if all(observe(prompt, row).passed for row in ordered):
            return prompt
    return None


def run(matrix, held, seed, plan, start, method):
    extra, qualification = METHODS[method]
    if extra is None:
        return prior.run(matrix, held, seed, plan, confirmation.ROUTE, confirmation.CANDIDATE, start)
    original_screen = split.routed_selection
    original_nominate = prior.archive.archive.nominate
    original_qualify = prior.certify_paired_qualification
    ties, audit = set(), Counter()

    def screen(incumbent, candidates, rows, evaluate, *, metric_limit, **kwargs):
        candidates, rows = tuple(candidates), tuple(rows)
        ledger = {}

        def observe(prompt, row):
            key = (prompt, row.id)
            if key not in ledger:
                if len(ledger) >= metric_limit:
                    raise ValueError('A validation tie exceeded the original search limit')
                reply = evaluate(prompt, row)
                if type(reply.passed) is not bool:
                    raise ValueError('A validation tie requires exact binary replies')
                ledger[key] = reply
            return ledger[key]

        original = original_screen(incumbent, candidates, rows, observe, metric_limit=metric_limit, **kwargs)
        if len(ledger) != original.evaluations:
            raise ValueError('The strict search and paid journal disagree')
        if original.prompt != incumbent:
            return original
        before = len(ledger)
        candidate = certified_tie(incumbent, candidates, rows, ledger, observe, extra=extra,
                                  metric_limit=metric_limit)
        audit.update(tieSearchLookups=len(ledger) - before)
        if candidate is None:
            return FinalistResult(incumbent, original.finalist, len(ledger))
        ties.add(candidate)
        audit.update(tieNominations=1)
        return FinalistResult(candidate, candidate, len(ledger))

    def nominate(incumbent, history, attempted, policy):
        rejected = {(incumbent, row['challenger']) for row in history
                    if row['incumbent'] == row['selected'] and row['challenger'] in ties}
        return original_nominate(incumbent, history, attempted | rejected, policy)

    def qualify(incumbent, challenger, rows, evaluate, *, minimum_gain, **kwargs):
        if challenger in ties:
            if qualification == 'split':
                rows = prior.halves(rows)
            elif qualification == 'two-gains':
                minimum_gain = 2
        return original_qualify(incumbent, challenger, rows, evaluate, minimum_gain=minimum_gain, **kwargs)

    with (patch.object(split, 'routed_selection', screen),
          patch.object(prior.archive.archive, 'nominate', nominate),
          patch.object(prior, 'certify_paired_qualification', qualify)):
        total, trace = prior.run(matrix, held, seed, plan, confirmation.ROUTE, confirmation.CANDIDATE, start)
    rejected = set()
    for row in trace:
        step = row['decision']
        if step['archiveNominee'] in rejected:
            raise ValueError('An independently rejected tie entered the archive')
        if (step['challenger'] in ties and step['challenger'] != step['incumbent']
                and not step['archivePromoted']):
            if step['selected'] == step['challenger']:
                audit.update(tiePromotions=1)
            else:
                rejected.add(step['challenger'])
    total.update(audit)
    return total, trace


def prepare(phase):
    base = {'gepa-sequential.runner-up/52': ('gepa-sequential.runner-up', 52),
            'gepa-batched.runner-up/52': ('gepa-batched.runner-up', 52)}
    if phase == 'confirmation':
        original = confirmation.dataset.read_json(confirmation.DESIGN.read_bytes())
        parent = confirmation.design(original['design']['objects'])
        published = prior.checked_report('routed-start-model-confirmation', CONFIRMATION_SHA)
        raw = (ROOT / 'benchmarks/data/routed-start-model-confirmation-v1.json').read_bytes()
        if sha256(raw).hexdigest() != published['corpusSha256'] or digest(parent) != published['planSha256']:
            raise ValueError('The confirmation snapshot differs from its published receipt')
        snapshot = confirmation.dataset.read_json(raw)
        confirmation.check_snapshot(snapshot, parent)
        panels = snapshot['panels']
        expected = {name: row['cpo'][confirmation.CANDIDATE] for name, row in published['panels'].items()}
        controls = {**base, 'gepa-batched.runner-up/47': ('gepa-batched.runner-up', 47)}
        references = {name: {label: row['gepa'][mode][str(cap)] for label, (mode, cap) in controls.items()}
                      for name, row in published['panels'].items()}
    else:
        parent, panels, refs, _, _ = prior.prepare(phase)
        published = prior.checked_report('routed-start-protection', START_SHA)[phase]
        if digest(parent) != published['planSha256']:
            raise ValueError('The published starting-prompt protocol differs')
        expected = {name: row['methods'][BASELINE] for name, row in published['panels'].items()}
        references = {name: dict(zip(base, (row['gepaSequential'], row['gepaBatched']), strict=True))
                      for name, row in refs.items()}
        controls = {}
    sources = ('benchmarks/routed_validation_ties.py', 'benchmarks/routed_start_model_confirmation.py',
               'benchmarks/routed_start_protection.py', 'benchmarks/routed_model_cost_frontier.py',
               'cpo/paired_qualification.py')
    plan = {**{k: parent[k] for k in ('schedule', 'gepaVersion', 'validationRows', 'searchCap')},
            'protocol': 'cpo-routed-validation-ties-v1', 'phase': phase, 'parentPlanSha256': digest(parent),
            'sourceReportSha256': CONFIRMATION_SHA if phase == 'confirmation' else START_SHA,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in sources},
            'methods': METHODS, 'replayedControls': controls,
            'caseSensitivity': {'candidate': AUDITED, 'draws': 4096, 'seed': 20261125},
            'scope': ('After strict search returns the incumbent, admit a certified validation tie with '
                      'a previously observed gain on an incumbent miss. Buy at most the allowed few replies '
                      'under the original cap. Keep ordinary independent qualification.')}
    return plan, panels, expected, references


def case_ranges(subjects, plan):
    settings = plan['caseSensitivity']
    rng = Random(settings['seed'])
    samples = {label: [] for label in ('strict', *PRIMARY, 'joint-cap-52')}
    for _ in range(settings['draws']):
        totals = Counter()
        for subject in sorted(subjects):
            vectors = subjects[subject]
            size = len(vectors['strict'])
            cases = rng.choices(range(size), k=size)
            totals.update({label: sum(values[case] for case in cases) for label, values in vectors.items()})
        totals['joint-cap-52'] = min(totals[label] for label in PRIMARY)
        for label, values in samples.items():
            values.append(totals[label])
    return {label: interval(values) for label, values in samples.items()}


def replay(plan, panels, expected, references):
    results, totals, losses, subjects = {}, {}, {}, {}
    for panel in panels:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        name, held = f'{subject}/{model}', confirmation.holdout(subject, len(matrix[0]))
        starts = costs.retained_prompts(matrix, held, plan['schedule'])
        counts = {m: Counter() for m in METHODS}
        journals = {m: [] for m in METHODS}
        for seed, start in zip(plan['schedule']['seeds'], starts, strict=True):
            strict_passes = None
            for method in METHODS:
                count, trace = run(matrix, held, seed, plan, str(start), method)
                counts[method].update(count)
                journals[method].append(trace)
                if method == 'strict':
                    strict_passes = count['holdoutPasses']
                else:
                    delta = count['holdoutPasses'] - strict_passes
                    counts[method].update(episodesGaining=int(delta > 0), episodesLosing=int(delta < 0),
                                          grossGain=max(0, delta), grossLoss=max(0, -delta))
        points = {method: dict(values, paidLookups=values['searchPaid'] + values['qualificationPaid'],
                              traceSha256=digest(journals[method])) for method, values in counts.items()}
        frontier.expect_reference(points['strict'], expected[name])
        comparisons = {}
        for label, (mode, cap) in plan['replayedControls'].items():
            winners, observed = confirmation.uncertainty.final_prompts(
                matrix, held, plan['schedule'], plan, mode, cap)
            frontier.expect_reference(observed, references[name][label])
            report = costs.audit_losses(matrix, held, plan['schedule'], plan['validationRows'],
                                       journals['strict'], winners)
            accumulated = losses.setdefault(label, {k: Counter() for k in report})
            for field, values in report.items():
                accumulated[field].update(values)
            if label in PRIMARY:
                comparisons[label] = winners
        if comparisons:
            for label in ('strict', AUDITED):
                comparisons[label] = [int(trace[-1]['decision']['selected']) for trace in journals[label]]
            vectors = {label: confirmation.uncertainty.case_totals(matrix, held, finals)
                       for label, finals in comparisons.items()}
            if sum(vectors[AUDITED].values()) != points[AUDITED]['holdoutPasses']:
                raise ValueError('The paired candidate holdout totals differ from the evaluation')
            combined = subjects.setdefault(subject, {label: [0] * len(held) for label in ('strict', *PRIMARY)})
            for label, dest in combined.items():
                for i, case in enumerate(held):
                    dest[i] += vectors[AUDITED][case] - vectors[label][case]
        points.update({label: {key: point[key] for key in FIELDS} for label, point in references[name].items()})
        for label, point in points.items():
            totals.setdefault(label, Counter()).update({k: v for k, v in point.items() if type(v) is int})
        results[name] = points
    return {'plan': plan, 'planSha256': digest(plan), 'totals': totals, 'panels': results, 'lossAudit': losses,
            'caseSensitivityRanges': case_ranges(subjects, plan) if subjects else {}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=PHASES, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current phase seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
