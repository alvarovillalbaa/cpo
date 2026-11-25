# Transfer stalled uniform validation to AIME and ARC-AGI

This replay transfers the stall-only policy from the language and Promptolution study without refitting. It runs one cycle on each of 760 recorded AIME and ARC-AGI episodes. It uses the archived splits, seeds, original and rotated starting prompts, and the first two challengers in the original shuffled roster order. All arms share the first six validation cases, first four reserved qualification cases, and the complete original holdout. Every deployment was checked against the four independent qualification grades for the chosen and starting prompts. [Frozen rule](validation-routed-tail.md) · [Archived split definitions](../benchmarks/recorded_math_validation_ties.py) · [Sealed receipt](validation-routed-tail-math-v1.json)

Each cell shows held-out passes and paid lookups. Root and rotated starts reuse the archive's question pools. The paired 95% ranges resample by question within each group.

| Archive and starts | Episodes | Settled CPO | Uncapped routed | Four-case cap | Stalled tail |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIME, original | 40 | 488 / 644 | 498 / 601 | 497 / 458 | 499 / 533 |
| AIME, rotated | 320 | 4,069 / 4,719 | 4,072 / 4,658 | 4,065 / 3,510 | 4,076 / 4,125 |
| ARC-AGI, original | 40 | 1,356 / 674 | 1,432 / 774 | 1,367 / 584 | 1,397 / 610 |
| ARC-AGI, rotated | 360 | 13,567 / 3,571 | 13,580 / 3,212 | 13,517 / 2,748 | 13,580 / 2,914 |

On rotated ARC-AGI starts, stall-only recovered all 63 passes lost by the four-case cap. It saved 298 lookups relative to uncapped routing, with a paired range of −14 to +13 passes. On the original start, it recovered 30 of 65 passes and saved 164 lookups. The paired range against uncapped routing was −54 to −14 passes. Historical evaluator charges fell from $416.67 to $380.11 on rotated starts and from $73.64 to $58.62 on the original start. These are sums of recorded prices on replayed decisions.

The benchmark matches actual costs against the same 11 sequential and batched native GEPA settings and five halving settings as the previous study, with retention available. It reselects the best affordable setting during each paired resample. On ARC-AGI, stall-only beat native GEPA by 204 passes on the original start and 169 on rotated starts. It beat halving by 70 and 164 passes. All four paired ranges had positive lower endpoints. The strongest controls were the same under lookup and historical-price matching. [Full comparisons](validation-routed-tail-math-v1.json)

On AIME, stall-only saved 68 and 533 lookups against uncapped routing and gained one and four passes. Both paired ranges included zero, as did the matched native GEPA and halving ranges. The archive shows transferable savings and an accuracy tradeoff on the original ARC-AGI start. Fresh proposal quality and live cost remain open.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Run the benchmark without arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.validation_routed_tail_math \
  --execute 1f18bbcb97fb5a27efda180898fb96613c3f6a75fa15247901e50f905c0d33ae \
  --out NEW_REPORT.json
```

Two socket-blocked replays produced identical receipts with SHA-256 `b4dde888bad47ebbf1df551cb68f2b818ea0b6ef1afd8dfff87415e8b1fd5ead`. All 43 focused tests and four subtests passed. The CLI refused a stale seal and an existing output path. Zero provider requests were sent. Storage Guard measured 8.6 GiB free. The isolated source export, wheel overlay, and publication worktree used 123 MiB under the standing LAB exception. [Runner](../benchmarks/validation_routed_tail_math.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
