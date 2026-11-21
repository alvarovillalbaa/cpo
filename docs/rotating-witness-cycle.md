# Rotating-witness prompt cycle

Use this cycle when you already have an ordered pool of candidate prompts and a limited evaluation budget. The seed changes the validation case order. The screen finds an incumbent miss and, when available, an incumbent pass. A candidate must repair the sampled miss and preserve the sampled pass. Up to two eligible candidates can be ranked on one additional validation case. Proposal order breaks ties.

```python
from cpo.rotating_witness import run_rotating_witness_cycle

result = run_rotating_witness_cycle(
    incumbent,
    candidates,
    validation_rows,
    qualification_rows,
    evaluate,
    metric_limit=56,
    qualify=qualify,
    qualification_limit=16,
    seed=cycle_index,
)
incumbent = result.prompt
```

Supply distinct candidate prompts and disjoint `cpo.Row` IDs for validation and qualification. `evaluate(prompt, row)` returns a `cpo.Observation` with an exact boolean `passed`. `qualify(prompt, row, repeat)` returns a boolean. The search cap covers every validation callback, including checks that preserve the incumbent's critical passes. If the preferred finalist loses a critical pass, the other eligible finalist can advance when the cap can still verify it. An unverified critical pass keeps the candidate out of qualification.

The witness screen nominates a challenger from sampled evidence. A separate paired qualification checks minimum gain, critical passes, and task-family regressions before promotion. A rejected or unfinished qualification keeps the incumbent. Read the two charges from `result.search.evaluations` and `result.qualification_evaluations`. Use a new seed and fresh qualification rows in the next cycle.

## Recorded verification

The package's nomination and per-cycle search traces reproduce the published PromptEval transfer result across 576 episodes and 2,304 cycles. The trace comparison uses the transfer protocol's original qualification bank. The package cycle uses its own independent paired cohort on each call. Tests exercise promotion, critical validation and qualification regressions, exact callback accounting, and exhausted caps through the public entry point. [Transfer results](prompteval-rotating-witness-transfer.md) · [Archived trace check](../tests/integration/test_rotating_witness_transfer_parity.py) · [Cycle tests](../tests/unit/test_rotating_witness_cycle.py)

The archived rule used 26.4% fewer paid lookups and gained 41 held-out passes against batched GEPA at cap 88. Wider GEPA settings attained higher scores at greater cost. Fresh provider inference and proposal generation cost remain unmeasured for this cycle. The historical design and execution seals reproduce with the new package in place.

A source export and wheel check used network-blocked Python. Storage Guard measured 8.0 GiB free. The standing LAB exception approved on November 17 covered a disposable build and replay allocation bounded at 0.2 GiB.
