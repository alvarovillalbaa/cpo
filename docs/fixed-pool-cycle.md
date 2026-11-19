# Run a fixed-pool CPO cycle

`run_fixed_pool_cycle` takes a supplied set of prompt candidates, screens them on validation cases, and qualifies the certified challenger on a separate panel. It defaults to deferred first-gain. Pass `screen="bounded-two-reads"` to use bounded discovery.

```python
from cpo.fixed_pool_cycle import run_fixed_pool_cycle

result = run_fixed_pool_cycle(
    incumbent, challengers, validation_rows, qualification_rows, evaluate,
    metric_limit=52, qualify=qualify, qualification_limit=16, seed=17,
)
next_incumbent = result.prompt
```

The search callback `evaluate(prompt, row)` returns an `Observation` with an exact boolean outcome. The independent callback `qualify(prompt, row, repeat)` returns a boolean. The two panels must contain distinct, disjoint row IDs. Search maintains the logical lookup cap and protects critical incumbent passes. Promotion requires the requested qualification gain, no family regression, and preservation of every critical incumbent pass.

`result.search` reports the attempted finalist, the prompt that validation selected, and validation callback calls. `result.qualification` contains the observed prefix and gain bounds when a challenger reaches qualification. It is `None` when the search keeps the incumbent. Qualification stops at the first decisive reply. If the qualification cap is reached before a decision, the result reports `undecided`, keeps the incumbent, and exposes the replies observed so far. `result.qualification_evaluations` counts those callbacks.

For deterministic evidence reuse, scope your callback cache to one optimizer episode and include every input that determines the response. Keep qualification repeats distinct in the cache key. With an archive check, pass the remaining search budget to the cycle and account for any already observed qualification replies in the callback. The API counts callback calls. The transfer replay meters distinct underlying lookups separately. [Matched-cost transfer](bounded-transfer-matched-cost.md)

## Verify on the archived transfer

The replay uses the same frozen starts, schedules, archive nominations, and cohorts as the 32-panel matched-cost transfer. It calls the public cycle for fresh searches, reuses search outcomes in the validation callback, and charges only the qualification replies its callbacks read. It checks each archived search hash, promotion, final prompt, holdout score, and lookup total.

Source and wheel runs produced byte-identical results across 1,024 episodes per screen. They reproduced all 8,192 archived cycle decisions and the matched-cost totals. Deferred first-gain reproduced 21,023 holdout passes at 101,034 distinct paid lookups. Two-read reproduced 20,963 passes at 107,423 lookups. These are deterministic callback measurements from the archived cohorts. [Sealed replay results](fixed-pool-cycle-replay-results-v1.json)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.fixed_pool_cycle_replay --phase mmlu
```

Use pinned GEPA 0.1.4 for the archived verification. Preview each phase to obtain its seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`. The other phases are `bbh-lmentry` and `bbh-lmentry-stress`.
