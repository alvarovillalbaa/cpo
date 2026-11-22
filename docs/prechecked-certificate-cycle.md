# Run the prechecked certificate cycle

`run_prechecked_certificate_cycle` exposes the cap-13 screen and its independent qualification as a fixed-pool API. The caller supplies candidate prompts and two disjoint panels. The cycle first pays for incumbent qualification replies through its first miss. A perfect incumbent ends the cycle before validation. [Public API](../cpo/prechecked_certificate_cycle.py)

```python
from cpo.prechecked_certificate_cycle import run_prechecked_certificate_cycle

result = run_prechecked_certificate_cycle(
    incumbent,
    candidates,
    validation_rows,
    qualification_rows,
    evaluate,
    metric_limit=13,
    qualify=qualify,
    minimum_gain=1,
)
```

`evaluate(prompt, row)` returns a CPO `Observation` with an exact boolean `passed` value. `qualify(prompt, row, repeat)` returns a boolean and receives repeat zero. Both panels need distinct, disjoint row IDs. The roster must contain distinct challengers and exclude the incumbent. The validation cap must cover the incumbent’s validation panel.

The screen buys a shared probe on the first validation case the incumbent missed. It reserves enough to finish one finalist’s panel, considers probe passes first, and retains roster order on ties. The first candidate that proves a strict validation gain and preserves the incumbent’s critical passes gets independent qualification.

Expected-cost ordering applies to up to eight noncritical qualification rows in one family. It uses the paid validation counts to order replies and credits the incumbent precheck. Other panels use the seeded certificate with the same prefix credit, preserving its family and critical-case checks. The cycle buys at most two qualification replies per case, including the precheck. A proof that cannot pass retains the incumbent.

Read `result.prompt` for deployment, `result.search.prompt` for the validation nominee or retained incumbent, and `result.search.evaluations` and `result.qualification_evaluations` for paid counts. `result.qualification.observations` includes the real callback order within qualification, including the incumbent precheck.

The archived BBH and LMentry comparisons favored one gain. The stronger two-gain variant helped the two archived MMLU cohorts relative to the same screen. The API uses the caller’s explicit `minimum_gain` setting. Fresh-model performance remains unverified. [BBH and LMentry evidence](recorded-qualification-margin-language-transfer.md) · [MMLU evidence](recorded-matched-qualification-margin.md)

## Reproduce the archived paths

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prechecked_certificate_cycle_replay
PYTHONHASHSEED=0 python -B -m benchmarks.prechecked_certificate_cycle_replay \
  --execute c5d4d1b64a090185f77fc36060dd0b67044d5b7b3ebb0d22aa794a3d62245af0 \
  --out NEW_REPORT.json
```

The clean source and independently installed wheel reproduced all 6,528 archived paths across 102 model panels. Both matched the paid callback order, nominees, deployments, scores, and lookup counts for each fixed margin. The installed replay placed the sealed benchmark sources and inputs beside the installed package so the inherited path checks used the original layout. The reports matched byte for byte at SHA-256 `37ce185700edd9a7ee3bd0d8dbf2a05bf6586e64f31c1e877ebd441a0cb2fe77`.

The source suite passed 31 tests and 21 subtests. All four public API tests also passed against the installed wheel. DNS and sockets were blocked during the replays. The CLI rejected the predecessor seal. Storage Guard measured 3.9 GiB free. The build, install, source export, and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Parity results](prechecked-certificate-cycle-replay-results-v1.json) · [API tests](../tests/test_prechecked_certificate_cycle.py)
