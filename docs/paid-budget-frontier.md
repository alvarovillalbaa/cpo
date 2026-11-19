# Compare CPO and GEPA at realized lookup cost

A shared search ceiling lets methods spend different numbers of paid lookups. This replay compares deferred first-gain CPO with official sequential and batched GEPA 0.1.4 across a fixed ladder of ceilings. It holds the 32 archived panels, proposal streams, archive nomination, qualification, and episode-local search reuse fixed. The 52-ceiling point reproduces every archived decision trace and lookup total. [Existing paid-cap comparison](gepa-paid-cap-transfer.md)

GEPA uses ceilings of 28, 36, 40, 44, 48, 52, 60, and 68. It reserves a full proposal round and enforces the paid limit at the evaluator. CPO uses 28, 36, 40, 44, and 52. It keeps its existing logical reserve for the incumbent and finalist. From 44 onward, the complete roster fits after the maximum archive charge. Each realized cost charges cache misses and qualification through the decisive reply, including earlier archive checks.

For each CPO point, the first comparison gives GEPA the best observed score from any single method and cap within CPO's aggregate lookup cost. A separate hindsight bound lets GEPA choose a different method and cap for each task, with the same choice for both models on that task. It solves that allocation exactly under CPO's total lookup budget. Both comparisons can inspect the held-out scores, so they describe the best recorded GEPA outcomes available at that cost. They do not estimate how well a deployable cap selector would choose on a new task. [Replay runner](../benchmarks/paid_budget_frontier.py)

## Results

Each cell shows holdout passes and paid lookups pooled across all 32 panels.

| CPO ceiling | Deferred first-gain CPO | Best fixed GEPA within CPO cost | Task-specific GEPA hindsight bound |
| --- | ---: | ---: | ---: |
| 28 | 20,471 / 68,675 | 19,394 / 62,857 | 20,625 / 68,495 |
| 36 | 21,004 / 98,194 | 20,315 / 91,363 | 21,161 / 98,192 |
| 40 | 21,015 / 100,469 | 20,315 / 91,363 | 21,179 / 100,436 |
| 44 or 52 | 21,023 / 101,034 | 20,315 / 91,363 | 21,182 / 100,995 |

At the published CPO point, the best affordable fixed GEPA setting was batched with ceiling 44. It finished 708 passes lower. The lowest-cost fixed GEPA run to reach CPO's score used ceiling 68 and needed 177,991 lookups. Choosing a separate GEPA setting for each task with hindsight gained 159 passes at 39 fewer lookups than CPO. This bound exceeded every tested CPO point and identifies task-specific budget choice as an open source of improvement.

Reducing the CPO ceiling from 52 to 36 saved 2,840 lookups and lost 19 passes. At the published point, CPO had higher accuracy on 16 panels, tied on one, and had lower accuracy on 15 against the best affordable GEPA setting chosen separately per panel. All counts describe recorded outcomes with holdout cases repeated across seeds. Both offline runs reproduced the same report byte for byte. [Sealed points and task allocations](paid-budget-frontier-results-v1.json)

## Reproduce

Use pinned GEPA 0.1.4. Preview to get the seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.paid_budget_frontier
```
