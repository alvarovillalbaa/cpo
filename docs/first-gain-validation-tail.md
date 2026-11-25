# Widen first-gain validation after a short panel stalls

The three-case panel lowered search cost and missed some of the promotions found by the original first-gain policy. This replay begins with the same three-case screen. If it nominates a challenger, that challenger proceeds to the original independent qualification. If the screen retains, a bounded search can continue on the full originally funded panel. It starts with every paid grade, including prepaid opening grades, and stops if no strict gain is possible within the remaining allowance. A new nominee requires a strict gain on the full panel and faces the same independent qualification. The opening route and other schedules carry over. [Fixed-width comparison](first-gain-validation-width.md) · [Earlier exact-nominee tail study](validation-routed-tail-math.md) · [Runner](../benchmarks/first_gain_validation_tail.py)

## Archived results

Each cell shows held-out passes and paid lookups, including qualification. The primary policy can buy up to six additional validation grades per stalled screen, within the original search cap. The other policies allow three or nine. All prior fixed-width controls and case layouts reproduced across 824 episodes.

| Archive | Fixed three cases | Three extra reads | Six extra reads | Nine extra reads | Prior terminal rule |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIME original | 498 / 379 | 498 / 379 | 498 / 424 | 500 / 470 | 499 / 497 |
| AIME rotated | 4,069 / 2,771 | 4,069 / 2,771 | 4,073 / 3,298 | 4,080 / 3,688 | 4,080 / 3,808 |
| ARC-AGI original | 1,338 / 433 | 1,338 / 433 | 1,370 / 451 | 1,373 / 465 | 1,439 / 622 |
| ARC-AGI rotated | 13,491 / 2,374 | 13,491 / 2,374 | 13,515 / 2,499 | 13,545 / 2,677 | 13,578 / 2,775 |
| Promptolution GSM8K | 2,379 / 653 | 2,379 / 653 | 2,404 / 682 | 2,436 / 725 | 2,436 / 796 |
| Promptolution SST-5 | 1,440 / 949 | 1,440 / 949 | 1,413 / 1,069 | 1,424 / 1,183 | 1,441 / 1,340 |
| **Total** | **23,215 / 7,559** | **23,215 / 7,559** | **23,273 / 8,423** | **23,358 / 9,208** | **23,473 / 9,838** |

The three-read extension reproduced the short panel's results. The six-read extension gained 32 passes for 18 additional lookups on original ARC-AGI. It led the highest-scoring affordable native GEPA and halving points by 225 and 142 passes at its 451-lookup ceiling. The nine-read extension matched the prior terminal rule on rotated AIME and GSM8K while saving 120 and 71 lookups, respectively. Original AIME still favored native GEPA at 501 passes and 175 lookups, and SST-5 favored the fixed three-case screen among the tested short-panel policies.

Across the archive mix, the nine-read policy recovered 143 of the 258 passes that separated the fixed three-case panel from the prior terminal rule. It still cost 630 fewer lookups than the terminal rule. The lower-cost and higher-quality settings describe different points on this archive's tradeoff. The GEPA and halving comparisons use published observed control points at each realized budget. The experiment shares archived prompt proposals and supplies no fresh-model or independent live result. [Sealed results](first-gain-validation-tail-v1.json)

## Reproduce offline

Use Python 3.12, the hash-pinned GEPA 0.1.4 wheel, and the reduced Promptolution corpus bound by the receipt. Run without arguments to print the plan seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.first_gain_validation_tail \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute 4d6d5bb6db7a8fc01fd7db872167c15283918bd97104cc1b9125cf9b25252c2c \
  --out NEW_REPORT.json
```

Two runs with sockets and DNS blocked produced byte-identical receipts at SHA-256 `28dee539034a95a4a59f38f6d5d2fed3132c2062983519de55eb4ce0a8db1a19`. All 34 focused tests passed. The new tests exhaust the Boolean four-case boards at each allowance to check grade reuse, full-panel nomination, and the incremental read cap. The CLI refused a stale seal, an occupied output path, and a changed corpus. Storage Guard measured 8.2 GiB free. The source export, wheel overlay, and publication worktree fit within 0.15 GiB under the standing LAB exception. Zero provider requests were sent. [Tests](../tests/unit/test_first_gain_validation_tail.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
