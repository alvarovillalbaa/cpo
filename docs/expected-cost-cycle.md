# Use expected-cost qualification in a fixed-pool cycle

`cpo.expected_cost_cycle.run_expected_cost_fixed_pool_cycle` searches a supplied prompt pool, then certifies the result on separate qualification rows. It collects pass counts from the distinct validation replies paid for by the existing screen. The counts guide evaluation order. The qualification replies determine promotion. [Package API](../cpo/expected_cost_cycle.py) · [Qualification algorithm](family-qualification-order.md)

```python
from cpo.expected_cost_cycle import run_expected_cost_fixed_pool_cycle

result = run_expected_cost_fixed_pool_cycle(
    incumbent,
    candidates,
    validation_rows,
    qualification_rows,
    evaluate,
    metric_limit=52,
    qualify=qualify,
)
```

`evaluate(prompt, row)` returns a CPO `Observation` with an exact boolean `passed` field. `qualify(prompt, row, repeat)` returns a boolean on a qualification row. Keep the two sets nonempty, with distinct and disjoint row IDs. The default screen is `deferred-first-gain`. Pass `screen="bounded-two-reads"` to use the other existing fixed-pool screen. [Existing screen policies](fixed-pool.md)

The result uses the existing `FixedPoolCycleResult` type. Read `result.prompt` for the selected prompt, `result.search.evaluations` for the validation count, and `result.qualification_evaluations` for the qualification count. `result.qualification.observations` lists the exact replies in callback order when search nominates a challenger. If search retains the incumbent, `result.qualification` is `None`.

Expected-cost ordering applies to eight or fewer qualification rows in one or two families, with one repeat and no critical rows. Larger panels, more families, repeats, and critical rows use the original seeded certificate. A `qualification_limit` below the size of a complete paired panel also uses the seeded certificate so it retains the same decision and callback prefix at that cap. An undecided certificate keeps the incumbent. Proof equivalence assumes that a given prompt, row, and repeat produce the same outcome in either evaluation order.

## Reproduce offline

The archived replay substitutes the new public cycle into the published CPO route and checks every panel's decision trace, holdout score, and lookup total. Preview the seal, then run it with a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.expected_cost_cycle_replay
PYTHONHASHSEED=0 python -B -m benchmarks.expected_cost_cycle_replay \
  --execute 4ee7b94813db35c5fd52e99ba97cf7a6baec814d0a3c1c44a3b32522da4e8aca \
  --out NEW_REPORT.json
```

The clean source replay and a separately installed wheel produced byte-identical reports across 88 archived panels and 11,264 cycle paths. The installed cycle reproduced 18,376 holdout passes and 163,285 total lookups on the BBH and LMentry transfer. The MMLU replays also matched the original search and qualification lookup counts. Both runs blocked sockets and DNS. Nineteen focused tests passed, including partial caps, critical rows, and repeated qualification replies. The runner rejected a stale seal and preserved an existing report. Storage Guard measured 10.2 GiB free. The 25.5 MB scratch overlay was removed under the standing LAB exception. [Replay results](expected-cost-cycle-replay-results-v1.json) · [Verification receipt](expected-cost-cycle-replay-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
