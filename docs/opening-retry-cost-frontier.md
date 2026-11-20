# Compare overlapping-rule repair at realized call cost

The [residual retry confirmation](opening-residual-retry.md) reached 648 of 648 holdout passes in both fault modes. Batched GEPA spent four and 41 fewer calls at the shared search ceiling of 56. This replay asks how many passes native GEPA can reach at CPO’s actual call cost across a ladder of search ceilings.

Official sequential and batched GEPA 0.1.4 use ceilings of 32, 40, 48, 56, 64, 80, 96, 112, and 128 on the same 36 scripted input panels. The shared opening, training proposer, cap accounting, and independent family qualification are unchanged from the confirmation. Every cap-56 GEPA request trace and both CPO totals reproduced. The cost includes search lookups, qualification lookups, and proposal calls. [Runner](../benchmarks/opening_retry_cost_frontier.py)

The fixed comparison uses one GEPA method and ceiling across all panels. A second calculation gives GEPA hindsight access to the holdout scores and lets it pick a method and ceiling separately for each panel under the pooled CPO cost. It can also keep the starting prompt at zero search cost. The allocation maximizes exact passes under that budget. It has no critical-case preservation requirement, so it gives the comparator a favorable bound over the measured choices.

| Fault mode | CPO passes / calls | Best fixed GEPA within cost | GEPA with a hindsight choice per panel |
| --- | ---: | ---: | ---: |
| Original | 648 / 2,286 | 546 / 2,201 | 573 / 2,281 |
| Shifted | 648 / 2,324 | 539 / 2,209 | 572 / 2,318 |

CPO led the per-panel hindsight allocation by 75 and 76 passes at its recorded cost. Sequential GEPA at cap 48 supplied both best fixed affordable points. Across all measured fixed settings, sequential GEPA at cap 96 scored the most passes under original faults, 600 in 2,912 calls. At cap 80 it reached the highest shifted-fault score, 589 in 2,790 calls. The original fixed-ceiling batched GEPA cost gate still failed. This comparison describes a measured menu on the same scripted panels. Fresh model qualification remains pending. [Sealed points and allocations](opening-retry-cost-frontier-results-v1.json)

## Reproduce offline

Use source from commit `2942fa9484f74d81031566adc01d49f15849cd69`, GEPA 0.1.4, and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_retry_cost_frontier
PYTHONHASHSEED=0 python -B -m benchmarks.opening_retry_cost_frontier \
  --execute fe0259ce27de3d9ea880c34a856bf467991d5790632cbb03c46b8d6a32899635 \
  --out NEW_REPORT.json
```

Two offline replays matched byte for byte. Each swept 1,296 native GEPA paths and reproduced the retry control through its normal benchmark route. All 24 focused tests passed. The runner refused an altered seal and preserved an existing report. Storage Guard measured 4.6 GiB free and the 29.7 MB scratch export was removed under the standing LAB exception. [Verification receipt](opening-retry-cost-frontier-verification-v1.json)
