# Qualify proposals with an exact early stop

`cpo.expected_cost_proposal_cycle.run_expected_cost_proposal_cycle` runs the existing proposal search and independently qualifies the selected challenger. The proposer receives the normal training feedback and candidate history. Paid validation replies supply the pass counts that order the qualification check. Actual qualification replies determine the result. [Package API](../cpo/expected_cost_proposal_cycle.py) · [Qualification algorithm](family-qualification-order.md)

```python
from cpo.expected_cost_proposal_cycle import run_expected_cost_proposal_cycle

result = run_expected_cost_proposal_cycle(
    incumbent,
    training_rows,
    validation_rows,
    qualification_rows,
    evaluate,
    propose,
    metric_limit=104,
    rounds=4,
    train_per_round=2,
    qualify=qualify,
)
```

Use distinct, disjoint row IDs throughout. `evaluate(prompt, row)` returns a CPO `Observation` with an exact boolean pass value. Set `field_credit=True` to use matched fields in search, and pass `opening_pair` when a rewrite and repair are already available. The qualification callback `qualify(prompt, row, repeat)` returns an exact boolean. `metric_limit` covers search and `qualification_limit` separately caps qualification.

Use `result.prompt` for the deployment, `result.search` for the existing search result, and `result.qualification` for the decision and exact replies observed in callback order. If search retains the incumbent, qualification is skipped. An undecided proof also retains the incumbent. The expected-cost scheduler applies to one repeat on at most eight rows in one or two families without critical cases. Other panels, and caps below the full paired panel size, use the seeded exact certificate. The early stop assumes each prompt and case returns the same outcome regardless of evaluation order. [Fixed-pool API](expected-cost-cycle.md) · [Paired certificate](paired-qualification.md)

## Results

The new cycle preserved all 7,680 search journals and deployments across the 12 archived panels and five search caps. At cap 171 it reduced qualification lookups from **20,800 to 17,945**. The seeded early stop used 19,450. This reduced total CPO lookups at that cap by 1.1%.

| Method on the eight transfer panels | Holdout passes | Total lookups | Joint paired 95% range against GEPA |
| --- | ---: | ---: | ---: |
| Proposal CPO, cap 72 | 10,237 | 66,831 | −77 to +21 |
| Proposal CPO, cap 88 | 10,210 | 87,087 | −109 to −1 |
| Proposal CPO, cap 104 | 10,238 | 107,121 | −87 to +33 |
| Proposal CPO, cap 128 | 10,251 | 130,957 | −76 to +50 |
| Proposal CPO, cap 171 | 10,270 | 172,444 | −62 to +73 |
| Sequential GEPA | 10,236 | 91,649 | |
| Batched GEPA | 10,263 | 88,226 | |

At cap 72 CPO saved 21,395 lookups relative to batched GEPA and finished 26 passes lower. At cap 171 it finished seven passes ahead and used 84,218 more lookups. None of the tested budgets matched or exceeded both GEPA scores within both lookup totals. The paired ranges resample held-out cases within subjects with both models and all episodes kept together. [Archived results](expected-cost-proposal-replay-results-v1.json)

In the typed fixture, all three tasks preserved their search and reflection journals and promoted the same prompts. Qualification took 205 calls across ticket, warehouse, and outage, down from 216. Those panels use repeated critical-case qualification, so this saving comes from the seeded exact certificate. Real provider proposal quality remains unverified. [Typed fixture](model-backed-validation.md#portable-grounded-fixture)

## Reproduce offline

The benchmark reuses the published four-cycle PromptEval schedules and freezes CPO search caps of 72, 88, 104, 128, and 171. It checks every CPO search journal and deployment against the full qualification path at the same cap. It also measures the seeded early stop and reproduces both original GEPA control totals. A separate typed fixture generates proposals from labeled training examples and compares field-aware search, reflection inputs, and promotion. [Archived protocol](prompteval-continuous.md) · [Runner](../benchmarks/expected_cost_proposal_replay.py)

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.expected_cost_proposal_replay
PYTHONHASHSEED=0 python -B -m benchmarks.expected_cost_proposal_replay \
  --execute aab4b682b5d1a3d0165905f15bb2abbf0e7c9227117abad2b25bc65738ad211a \
  --out NEW_REPORT.json
```

The clean source export and separately installed wheel produced byte-identical reports with sockets and DNS blocked. They reproduced 36 published panel totals. Twenty-two installed-wheel tests passed, including search feedback, precomputed openings, repeated critical cases, and qualification caps. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 10.5 GiB free. The 26.6 MB scratch overlay was removed under the standing LAB exception. [Verification receipt](expected-cost-proposal-replay-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
