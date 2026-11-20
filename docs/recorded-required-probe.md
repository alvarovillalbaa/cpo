# Probe a case only when the coverage gate requires it

The shared-probe screen improved on recorded outage replies. On ARC-AGI and AIME, many viable challengers failed the shared probe and the gains did not transfer. This follow-up uses a probe only when an incumbent miss is the sole validation case in a critical stratum. A challenger that fails that case cannot meet the existing coverage gate. [Outage window](recorded-coverage-window.md) · [Math transfer](recorded-window-transfer.md)

The **required window** uses the existing four-candidate screen on those panels. **Required first** checks the mandatory case on one challenger at a time in the original roster order. It stops that candidate on a miss and reuses the reply for exact confirmation on a pass. Both policies use the original ordered race when no such case exists. Each confirmation can still afford a complete exact score under the original budget. The independent qualification and incumbent precheck stay in place. [Runner](../benchmarks/recorded_required_probe.py)

## Results

The incumbent precheck admitted 164 of the 220 outage splits. Of those, 85 had a missed case that was the only witness for its critical group. None of the 27 admitted warehouse splits had a required probe and ticket admitted no searches. The table shows outage holdout passes out of 660 and paid lookups.

| Search cap | Ordered CPO | Binary window | Required window | Required first |
| --- | ---: | ---: | ---: | ---: |
| 24 | 457 / 3,324 | 483 / 3,314 | 476 / 3,330 | 476 / 3,245 |
| 36 | 485 / 4,059 | 515 / 3,784 | 510 / 3,843 | 510 / 3,723 |
| 48 | 512 / 4,313 | 518 / 3,855 | 518 / 3,895 | 518 / 3,772 |

At cap 48, required-first matched the binary window's 518 passes and saved 83 lookups with zero matched critical losses. It added six passes and saved 541 lookups against the ordered race, also with zero matched critical losses. Against sequential GEPA at cap 32, the fixed reference from the earlier frontier, it gained 108 passes, saved 244 lookups, and lost none of the reference's critical passes. Batched GEPA at cap 36 cost 3,684 lookups and retained one critical pass that CPO missed. At caps 24 and 36 the required-first policy gave up binary-window passes while saving lookups. These are repeated splits of 12 stored outage cases. The critical comparison and fresh-model superiority remain open. [Full results](recorded-required-probe-results-v1.json)

## Use the opt-in selector

```python
from cpo.required_probe import select_required_covered_pool

selection = select_required_covered_pool(
    (incumbent, *challengers),
    validation_rows,
    evaluate,
    metric_limit=48,
    critical_strata=validation_strata,
)
```

The inputs and result follow the coverage-aware selector. Supply disjoint cases for the subsequent paired qualification. Callers with no missed singleton use the same ordered race and read each incumbent case once. [Qualification example](covered-pool.md)

## Reproduce

Use the intact GEPA research and Open Evals archives with pinned GEPA 0.1.4.

```sh
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_required_probe
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_required_probe \
  --execute 922008f07eb693c22ac2f98da15bbc17baef3d5a9c58ed2aa9539ea9f4f19e79 \
  --out NEW_REPORT.json
```

Both source-export replays matched byte for byte with sockets and DNS blocked. The packaged selector reproduced the prototype's complete results and paid lookup counts. Fifteen focused tests passed, including exact fallback order and reuse of a paid probe. A fresh wheel installation passed the public API check. The CLI rejected an incorrect seal and an existing output path. Storage Guard measured 13.3 GiB free. The 30.2 MB temporary source, wheel, and environment scratch was removed under the standing LAB exception. [Verification receipt](recorded-required-probe-verification-v1.json)
