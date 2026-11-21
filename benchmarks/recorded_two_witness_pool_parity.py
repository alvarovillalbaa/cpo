"""Check the public two-witness selector against the frozen archived policy."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_shortlist_model_transfer as transfer
from cpo import two_witness_pool
from cpo._contract import digest


screen = transfer.screen
shortlist = transfer.shortlist
TRANSFER_SHA256 = 'db9cc74e9577af343509cb9b0bc0b8fe99e88cab49991c05a1965d984bcf52b9'
AUDIT_FIELDS = {'screenLookups', 'completedShortlistSlots', 'finalistValidationLookups', 'skippableSecondWitnesses'}


def prepare():
    parent, groups, tuning, receipts = transfer.prepare()
    recorded = transfer.cost.prior.baseline.read_reference(
        'docs/recorded-shortlist-model-transfer-results-v1.json', TRANSFER_SHA256, parent)
    inputs = {
        'screening-study': [(panel, receipts[name][panel[0]]['panels'][f'{panel[1]}/{panel[2]}'])
                            for name, panels in tuning.items() for panel in panels],
        'model-transfer': [(panel, recorded['results'][name][panel[0]]['panelsAtOriginalCap'][f'{panel[1]}/{panel[2]}'])
                           for name, panels in groups.items() for panel in panels],
    }
    plan = {**{key: parent[key] for key in ('seeds', 'challengers', 'caseCounts', 'searchCap')},
            'protocol': 'recorded-two-witness-pool-parity-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': TRANSFER_SHA256,
            'selectorSha256': sha256(Path(two_witness_pool.__file__).read_bytes()).hexdigest(),
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Replace only the archived validation selector with the public API. Retain both paid '
                     'training and independent qualification gates and compare all archive paths, decisions, '
                     'held-out replies, and paid lookup counts.'}
    return plan, inputs


def use_frozen(incumbent, candidates, rows, training, observe, ledger, *, cap, keep_ties, audit):
    return screen.search(incumbent, candidates, rows, training, observe, ledger,
                         cap=cap, arm=screen.PAIRED, audit=audit)


def use_public(incumbent, candidates, rows, training, observe, ledger, *, cap, keep_ties, audit):
    if ledger:
        raise ValueError('The archived validation selector should start with a fresh search ledger')
    report = two_witness_pool.select_two_witness_pool((incumbent, *candidates), rows, observe,
                                                     metric_limit=cap - 2 * len(training))
    if report.evaluations != len(ledger):
        raise ValueError('The public selector must account for every paid validation callback')
    return report.prompt


def replay(plan, inputs):
    reports = {}
    for cohort, panels in inputs.items():
        counts = Counter()
        results = {}
        for (_, subject, model, matrix), recorded in panels:
            cells = {str(index): tuple((int(passed), None, False) for passed in vector)
                     for index, vector in enumerate(matrix)}
            totals, traces = Counter(), []
            for seed in plan['seeds']:
                start, roster, cases = transfer.transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
                args = (cells, start, roster, cases, seed, plan['searchCap'], screen.PAIRED)
                with patch.object(shortlist, 'shortlist', use_frozen):
                    old, trace, grades = shortlist.trial(*args)
                with patch.object(shortlist, 'shortlist', use_public):
                    public, public_trace, public_grades = shortlist.trial(*args)
                if (public != {key: value for key, value in old.items() if key not in AUDIT_FIELDS}
                        or trace != public_trace or grades != public_grades):
                    raise ValueError('The public selector changed an archived path, price, or outcome')
                totals.update(old)
                traces.append(trace)
                counts.update(trials=1, paidLookups=public['paidLookups'], holdoutPasses=public['holdoutPasses'])
            summary = {**totals, 'traceSha256': digest(traces)}
            if summary != recorded[screen.PAIRED]:
                raise ValueError('The frozen replay must still match its published panel')
            name = f'{subject}/{model}'
            results[name] = {key: summary[key] for key in ('paidLookups', 'holdoutPasses', 'traceSha256')}
        reports[cohort] = {'totals': counts, 'panels': results}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh output path')
    report = replay(plan, inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
