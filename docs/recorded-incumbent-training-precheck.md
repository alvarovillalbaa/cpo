# Checking training headroom before validation

The qualification-first CPO policy already stops when the incumbent passes every independent qualification case. This replay asks whether a second incumbent check can save more. A challenger also needs a strict gain on the existing training half, so a perfect incumbent there rules out promotion. One schedule checks that training half immediately after the qualification precheck. The other checks for a validation miss first. Each precheck stops at the first miss, and the original race reuses every prepaid reply it needs. Both schedules keep the original search cap and run only when the cap can cover the fixed roster and the original training reserve. [Previous proof order](recorded-expected-training-order.md) · [Replay runner](../benchmarks/recorded_incumbent_training_precheck.py)

Both schedules preserved all deployments and held-out grades across 1,520 trials each. When no precheck ruled out promotion, the original nominee and qualification lookup count also matched. Neither schedule reduced total lookups in any setting.

| Archive and roster | Original paid lookups | Training first | Validation first |
| --- | ---: | ---: | ---: |
| AIME, original, four challengers | 1,160 | 1,211 | 1,211 |
| AIME, original, eight challengers | 1,604 | 1,647 | 1,647 |
| AIME, rotated, four challengers | 8,536 | 8,806 | 8,808 |
| AIME, rotated, eight challengers | 12,115 | 12,268 | 12,270 |
| ARC-AGI, original, four challengers | 1,844 | 1,844 | 1,844 |
| ARC-AGI, original, eight challengers | 2,041 | 2,041 | 2,041 |
| ARC-AGI, rotated, four challengers | 8,277 | 8,628 | 8,539 |
| ARC-AGI, rotated, eight challengers | 9,703 | 9,924 | 9,835 |

On the eight-challenger ARC-AGI rotation, training first found 17 perfect incumbents. It saved lookups on 12 trials and added lookups on 142, for 221 extra lookups and $27.37 at historical evaluator prices. Validation first found 38 perfect validation incumbents and another 12 on training. It still added 132 lookups and $15.24. Against the best affordable GEPA settings, its case-resampled 95% margins were −8 to +101 passes by lookups and −13 to +87 by historical cost. The added incumbent reads did not pay for themselves. [Sealed results](recorded-incumbent-training-precheck-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With sockets and DNS blocked, two full replays matched byte for byte, including one from a clean source export. The 36 targeted checks passed from that export, including exhaustive two-case prechecks and cap boundaries. The replay reproduced the original GEPA cost frontiers, and the public selector parity receipt and ordered live-plan preview matched their sealed originals. The CLI rejected a stale seal. Storage Guard measured 3.6 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_incumbent_training_precheck
python -B -m benchmarks.recorded_incumbent_training_precheck \
  --execute 1c30893e7860a6497b4220a576d5af30af72aee4419a1645ea7cf4afcc96a635 \
  --out NEW_REPORT.json
```
