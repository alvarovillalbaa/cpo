"""T2 integration check against the bundled archived PromptEval fixture."""

from collections import Counter
from hashlib import sha256
from unittest.mock import patch

from benchmarks import prompteval_rotating_witness_transfer as transfer
from cpo import Observation, Row
from cpo._contract import digest
from cpo.rotating_witness import _nominate


RECEIPT = transfer.ROOT / 'docs/prompteval-rotating-witness-transfer-results-v1.json'
RECEIPT_SHA = 'e234c20ec178745ca55ff2e01aabf9f75e69377997690302fc615d7d8b6cc5ac'


def test_package_nomination_reproduces_all_archived_transfer_traces():
    raw = RECEIPT.read_bytes()
    assert sha256(raw).hexdigest() == RECEIPT_SHA
    receipt = transfer.dataset.read_json(raw)
    design = transfer.frozen_design()
    assert receipt['design'] == design
    raw_corpus = transfer.DATA.read_bytes()
    assert sha256(raw_corpus).hexdigest() == receipt['corpusSha256']
    panels = transfer.dataset.read_json(raw_corpus)['panels']
    selector, cap = transfer.CANDIDATE, design['searchCaps'][transfer.CANDIDATE]
    active = {**design['schedule'], 'evaluationLookupLimit': cap}

    def packaged_selection(_method, incumbent, layout, observe, plan):
        rows = [Row(str(case), 'task') for case in layout['validation']]

        def evaluate(prompt, row):
            return Observation(observe(prompt, int(row.id)), {})

        return _nominate(incumbent, layout['alternatives'], rows, evaluate,
                         metric_limit=plan['evaluationLookupLimit'], seed=layout['seed']).prompt

    with patch.object(transfer.replay, 'search', packaged_selection):
        for panel in panels:
            subject, model, matrix = panel['subject'], panel['model'], panel['correctness']
            expected = receipt['panels'][f'{subject}/{model}']['methods'][selector]
            holdout = transfer.replay.transfer.holdout(subject, len(matrix[0]))
            totals, trace = Counter(), []
            for seed in active['seeds']:
                start, layouts = transfer.replay.schedule(len(matrix[0]), len(matrix), holdout, seed, active)
                final, counts, trace_hash = transfer.replay.run_arm(
                    matrix, holdout, start, layouts, active, selector, design['qualificationBank'],
                )
                totals.update(counts)
                trace.append((seed, final, trace_hash))
            actual = {**totals, 'traceSha256': digest(trace)}
            assert actual == expected, f'Package replay differs for {subject}/{model}'
