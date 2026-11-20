# Route training probes for prompt repair

Use `run_routed_repair_cycle` when training and validation inputs share categorical features that can help select informative training examples. The cycle screens a supplied opening pair, attempts up to two repairs, and evaluates one final nominee on independent qualification rows. [Package API](../cpo/routed_repair_cycle.py)

```python
from cpo import ProposalPair
from cpo.routed_repair_cycle import run_routed_repair_cycle


def input_features(row):
    case = cases[row.id]
    return {"request_type": case["request_type"], "urgent": case["urgent"]}


result = run_routed_repair_cycle(
    incumbent,
    training_rows,
    validation_rows,
    qualification_rows,
    evaluate,
    propose,
    input_features=input_features,
    opening_pair=ProposalPair(rewrite, repair),
    metric_limit=56,
    qualify=qualify,
    diagnostic_prompt=instruction_only,
)

next_incumbent = result.prompt
```

`input_features(row)` should return a mapping from string names to categorical strings, integers, or booleans based on the input alone. The cycle reads features only on training and validation rows when a repair can be funded. It ranks unused training rows by features overrepresented among validation failures. The seeded training order breaks ties. The optional `diagnostic_prompt` lets the evaluator run a variant without demonstrations on training. The proposer receives the complete parent and paid training observations and can return the same proposal types as the [one-repair cycle](opening-repair-cycle.md).

`metric_limit` covers search evaluations. Each repair reserves a full validation panel before looking up training observations. `max_training_probes` defaults to two per repair. The opening pair is supplied by the caller, so count its generation separately. `result.search.evaluations` counts search lookups, `result.search.reflections` counts later proposer calls, and each `routed-probes` event records the probe row IDs and disposition.

A repair must add exact validation passes and preserve critical passes and each family's score. A first repair that keeps every row's exact outcome and, with `field_credit=True`, preserves every row's matched-field count can serve as the second repair's parent. The last accepted nominee stays eligible for qualification. `qualification_limit` caps the separate proof. `result.prompt` returns the starting incumbent if qualification rejects the nominee or ends undecided.

## Reproduce the comparison

Clean source and an independently installed wheel reproduced the three sealed cohort traces across all 90 scripted policy panels. Each environment passed 14 focused tests with socket creation and DNS blocked. Wheel builds and installs used local tooling with the index disabled. The CLI rejected a stale seal and preserved an existing report. The 29.6 MB scratch directory was removed under the standing LAB exception after Storage Guard measured 4.5 GiB free. [Benchmark results](opening-repair-probe-routing.md) · [Replay artifact](routed-repair-api-replay-v1.json) · [Verification receipt](routed-repair-api-verification-v1.json)

The panels use one scripted rule generator. The replay measures neither live model quality nor provider costs. Use GEPA 0.1.4 and a fresh output path to reproduce the comparison.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.routed_repair_api_replay
PYTHONHASHSEED=0 python -B -m benchmarks.routed_repair_api_replay \
  --execute b0111989bb3b2294991eff508f08ed1f778b133680d5dc92fa5a4bbe4b0603cc \
  --out NEW_REPORT.json
```
