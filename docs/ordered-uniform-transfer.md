# Use paid incumbent grades to order uniform challenger reads

The [uniform score-bound screen](bounded-uniform-refit.md) proves the exact quoted winner using the shortest per-candidate prefixes for a fixed case order. This experiment changes that order. The original quote still fixes the roster and the funded validation cases. After grading the incumbent on those cases in their original order, the screen can check incumbent misses first, check incumbent passes first, or preserve the original order. No new probe is required. The winner, exact scores and independent qualification remain the same. Critical cases retain the original strict screen. [Implementation](../cpo/ordered_uniform_validation.py)

Uniform aggregation allows case order to change while holding the final score fixed. An earlier challenger miss can lower its upper bound sooner. If challenger failures occur on different cases from the incumbent's failures, the same ordering can increase cost. The replay records both effects.

Use `run_ordered_uniform_cycle` from `cpo.ordered_uniform_validation`. It accepts `order='original'`, `order='miss-first'`, or `order='pass-first'`. The quoted roster, roles, and independent qualification arguments stay the same.

## Task-disjoint fit

The fit uses the original 70 panels from 31 discovery tasks, excluding all target tasks. For each fixed eight-challenger depth, it chooses one order by total actual lookups and favors the original order on exact ties. Misses-first wins at both depths and lowers cost in every discovery cohort. All choices preserve the complete nomination and qualification receipts. [Fit and replay runner](../benchmarks/ordered_uniform_transfer.py) · [Frozen fit](ordered-uniform-fit-v1.json)

| Funded rows | Original order | Misses first | Passes first |
| --- | ---: | ---: | ---: |
| Two | 72,127 | 67,124 | 76,878 |
| Three | 107,703 | 94,573 | 118,532 |

## Target transfer

Cells show actual lookup counts before and after applying the fitted misses-first order. Scores are identical across all three orders. The comparison retains the same task, model, seed, and case geometry in each cohort and replays the original two-case score and prices from the bounded uniform audit.

| Cohort | Two-row passes | Two-row lookups | Three-row passes | Three-row lookups | Bounded opening budget |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,358 | 13,550 → 12,960 | 6,364 | 20,161 → 18,716 | 13,421 |
| Bounded LMentry | 6,529 | 13,831 → 13,593 | 6,584 | 19,792 → 19,179 | 15,636 |
| Bounded MMLU | 7,714 | 7,700 → 6,903 | 7,723 | 11,684 → 9,675 | 6,554 |
| Four-case MMLU | 22,365 | 12,644 → 11,294 | 22,401 | 19,206 → 15,655 | 10,591 |
| Tie BBH | 2,118 | 11,983 → 11,751 | 2,135 | 17,905 → 17,315 | 12,521 |
| Tie LMentry | 1,018 | 6,275 → 6,210 | 1,059 | 8,909 → 8,812 | 6,971 |
| Additional MMLU | 7,394 | 7,818 → 6,954 | 7,399 | 11,503 → 9,672 | 6,354 |
| **Pooled** | **53,496** | **73,801 → 69,665** | **53,665** | **109,160 → 99,024** | **72,048** |

The two-row schedule saves 4,136 lookups across 2,048 episodes. It reads less on 792 cycles and more on 75. The three-row schedule saves 10,136 lookups, with 1,631 cheaper cycles and 185 dearer cycles. Both lower aggregate cost in all seven cohorts. Selecting the cheapest of the three orders in hindsight each cycle would save another 309 and 705 lookups, respectively. Pooled counts describe the archive because some tasks recur.

The two-row schedule now fits four of seven bounded opening budgets. The added cohort is bounded BBH, where it moves from 129 lookups over to 461 under. Its score of 6,358 is 11 ahead of the bounded opening, eight ahead of the native GEPA upper bound at its realized cost, and 34 below the affordable task-tuned simple point score. The two-row schedule exceeds the native GEPA upper bound in three cohorts and the affordable task-tuned simple point score in both LMentry cohorts. The three-row schedule still exceeds all seven bounded opening budgets.

The receipt verifies affordable native GEPA anchors at the fitted order's actual spend. Five three-row comparisons lack an upper bound from the archived native cost grid at that price. The replay establishes a lower cost for these fixed uniform decisions. Schedule selection across tasks and fresh live superiority remain open.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview a seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.ordered_uniform_transfer --fit \
  --execute d1b59e96ebb29e9a0dc2098e2f1f22926413945a80bd7467c431db51c0554126 \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.ordered_uniform_transfer \
  --cohort bounded-BBH --fitted NEW_FIT.json \
  --execute 207bd678751ec28a67d05c0f8c2239a7a31704ff6e33b2a0cf579e83d75c3997 \
  --out NEW_REPORT.json
```

[Bounded BBH](ordered-uniform-transfer-bounded-bbh-v1.json) · [Bounded LMentry](ordered-uniform-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](ordered-uniform-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](ordered-uniform-transfer-four-case-mmlu-v1.json) · [Tie BBH](ordered-uniform-transfer-tie-bbh-v1.json) · [Tie LMentry](ordered-uniform-transfer-tie-lmentry-v1.json) · [Additional MMLU](ordered-uniform-transfer-additional-mmlu-v1.json)

Forty-eight targeted tests passed, including exhaustive three-case panels and both directions of the trade-off in paid reads. Duplicate fits and target replays matched byte for byte with DNS and outbound sockets blocked. No provider requests were made. Storage Guard measured 9.7 GiB free. The source export, dependency overlay, and publication checkout fit the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_ordered_uniform_validation.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
