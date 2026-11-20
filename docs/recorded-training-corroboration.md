# Corroborate archived promotions on reserved training cases

On AIME with rotated incumbents and eight challengers, strict CPO lost 38 of 320 paired trials to sequential GEPA. In 20 of those trials, sequential GEPA kept the start while CPO promoted a challenger. Those 20 trials accounted for 73 of the 119 gross lost passes. Against batched GEPA, retaining the start accounted for 83 of 121 gross lost passes. This follow-up tests whether a second source of evidence can veto those moves. [Original ARC and AIME replay](recorded-math-validation-ties.md)

## Protocol

The candidate race and original independent qualification run first. If qualification passes, the experimental policies may compare the same challenger and incumbent on the reserved training cases. Failing this check keeps the incumbent. The same nominee and qualification cases carry through every CPO arm. Every record read counts toward the original search allowance and any recorded ARC evaluator cost.

The full-panel policies require a nonnegative training gain or a strict training gain. They apply to every promotion or only to a challenger that gained exactly one pass in validation. Another policy waits for a proven one-pass gain in independent qualification. The half-panel policies check all qualified changes using five training cases on AIME or nine on ARC. The complementary half checks how sensitive the strict-gain rule is to the sampled cases. The checker uses lower and upper paired margins and stops once the replies determine its decision. The original strict CPO, both GEPA modes, and retaining the start are controls. Every arm keeps the previous case splits, candidate rosters, and held-out scoring. [Replay runner](../benchmarks/recorded_training_corroboration.py)

## Results

The table shows the eight-challenger rotation settings. Each cell reports holdout passes / paid lookups.

| Policy | AIME | ARC-AGI |
| --- | ---: | ---: |
| Retain start | 4,056 / 0 | 12,944 / 0 |
| Strict CPO | 4,002 / 11,166 | 13,932 / 10,383 |
| Nonloss across all training | 4,040 / 12,368 | 13,898 / 13,226 |
| Strict gain across all training | 4,053 / 12,361 | 13,886 / 13,336 |
| Strict training gain on a one-pass qualification gain | 4,013 / 11,716 | 13,913 / 11,346 |
| Strict gain on first training half | 4,062 / 11,749 | 13,818 / 11,886 |
| Strict gain on second training half | 4,042 / 11,758 | 13,856 / 11,885 |
| Batched GEPA | 4,055 / 13,640 | 13,781 / 13,023 |
| Sequential GEPA | 4,074 / 14,016 | 13,785 / 14,790 |

On AIME, the first-half check recovered **65 of the 73** gross passes lost when sequential GEPA kept the start. It gained **60 passes** over strict CPO for 583 additional lookups, with a paired range of **+16 to +102**. Its score was seven passes higher than batched GEPA and 12 lower than sequential GEPA, with 13.9% and 16.2% fewer lookups, respectively. The joint range against both controls was −41 to +15 and the archived gate was inconclusive. The check finished six passes above retaining the start.

The second-half check gained 40 passes over strict CPO, with a range of −15 to +97. It vetoed 50 of 66 independently qualified changes, compared with 41 for the first half. The two halves differed by 20 passes at similar cost. With four challengers, the first-half check scored two passes ahead of batched GEPA and ten behind sequential GEPA. Its lookup savings against batched GEPA fell below the 10% gate. Retaining the original AIME root scored 500 passes and exceeded all guarded root settings. [Full policy totals and paired ranges](recorded-training-corroboration-results-v1.json)

Both half-panel checks lost holdout passes and added lookups on the ARC rotation that strict CPO had already cleared. The first-half setting was selected retrospectively on AIME. The results identify a way to reduce harmful promotions on this archive and show that its effect varies by task and training sample. Fresh-model superiority and actual provider costs remain unverified.

The follow-up gives the veto one validation-proven backup and measures the cost of an incumbent qualification precheck applied equally to CPO and GEPA. [Training backup replay](recorded-training-backup.md)

A later replay tests whether a stronger qualification gain can substitute for the training check, and measures both proof orders under that rule. [Qualification waiver replay](recorded-margin-corroboration.md)

## Reproduce

Use pinned GEPA 0.1.4 and the bundled score snapshot. Preview the seal, then run to a fresh report path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_training_corroboration
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_training_corroboration \
  --execute d5ad7152811926070359bcef204bd883e3793e8dd94f7d55fff06f4e823a6d8c \
  --out NEW_REPORT.json
```

Two source-export replays matched byte for byte with sockets and DNS blocked. They reproduced 32 published control traces and the associated scores and lookup costs. Four focused tests passed, including exhaustive checks of 64 binary training panels under both thresholds and two read orders. The CLI rejected a wrong seal and preserved an existing result. Storage Guard measured 16.4 GiB free. The 15.1 MB scratch overlay was removed under the standing LAB exception. [Focused tests](../tests/unit/test_recorded_training_corroboration.py)
