# Explain the validation switch's gains and losses

The [fixed switch](switch-validation-case-transfer.md) gained 30 passes on bounded LMentry and lost 20 on bounded BBH. It spent the remaining allowance on the second case when the incumbent failed both cases. This experiment tests whether some of the BBH loss came from abandoning the opening case. After two challenger failures and two incumbent misses, the new screens alternate cases for each unopened challenger. One screen checks the opening case first and the other checks the second case first. Both stop at the first observed repair, keep the nine-lookup validation cap, and use the existing independent qualification. [Screen](../cpo/interleaved_validation_cases.py) · [Attribution and replay](../benchmarks/interleaved_validation_transfer.py)

The discovery fit tests 125 tables across the three later qualification miss positions and preserves the incumbent-first action at the first position. The menu includes both interleavings, the fixed switch, the original quote and the two-challenger opening. All 70 discovery panels across 31 tasks exclude the target tasks. Under the original router budgets, 107 tables are feasible. The fit kept the bounded opening at 84,043 passes for 67,022 lookups. The fixed interleavings scored 83,986 at 67,932 lookups with the opening case first, and 83,997 at 67,933 with the second case first. [Frozen discovery fit](interleaved-validation-fit-v1.json)

## Why the fixed switch changed quality

For each of the 2,048 target episodes, the audit replaces one more leading cycle with the fixed switch. Every replacement compares the two choices from the same incumbent and runs the remaining suffix with the bounded opening. The pass and lookup changes sum exactly to the difference between the complete rollouts. A second-case repair appears in the attribution only when the challenger passes that case in the paid ledger and clears independent qualification. The attribution depends on the order of the cycle replacements.

| Deployed effect of one fixed-switch replacement | Bounded BBH cycles | Bounded BBH pass change | Bounded LMentry cycles | Bounded LMentry pass change |
| --- | ---: | ---: | ---: | ---: |
| New second-case repair | 8 | −14 | 3 | +24 |
| Second-case repair replaced an opening promotion | 4 | −6 | 0 | 0 |
| Opening promotion skipped | 4 | 0 | 3 | +6 |
| Same deployment | 1,136 | 0 | 1,146 | 0 |
| **Total** | **1,152** | **−20** | **1,152** | **+30** |

All 20 bounded BBH losses came from accepting new or substitute second-case repairs. Losing four opening promotions had zero net effect there. In bounded LMentry, three new second-case promotions explained 24 of the 30 added passes. Skipping three opening promotions accounted for the remaining six. Across all seven cohorts, 577 of the fixed switch's 593 additional lookups came from cycle replacements that deployed the same prompt.

## Interleaving results

Cells show final held-out passes and paid lookups. The fitted choice reproduces the bounded opening. The receipts also price common and task-tuned GEPA and simple controls at each new arm's realized spend.

| Cohort | Bounded opening and fit | Fixed switch | Opening case first | Second case first |
| --- | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,347 / 13,421 | 6,327 / 13,551 | 6,321 / 13,570 | 6,326 / 13,568 |
| Bounded LMentry | 6,338 / 15,636 | 6,368 / 15,648 | 6,355 / 15,658 | 6,362 / 15,666 |
| Bounded MMLU | 7,719 / 6,554 | 7,724 / 6,634 | 7,724 / 6,629 | 7,724 / 6,629 |
| Four-case MMLU | 22,369 / 10,591 | 22,369 / 10,739 | 22,369 / 10,735 | 22,369 / 10,734 |
| Tie BBH | 2,145 / 12,521 | 2,146 / 12,588 | 2,145 / 12,566 | 2,145 / 12,552 |
| Tie LMentry | 992 / 6,971 | 995 / 6,996 | 992 / 6,985 | 988 / 6,991 |
| Additional MMLU | 7,398 / 6,354 | 7,398 / 6,485 | 7,399 / 6,482 | 7,399 / 6,493 |

Both interleavings lost quality on bounded BBH and gave up part of the fixed switch's bounded LMentry gain. Their second-case promotions still explained the bounded BBH loss. The second-case-first variant gained five pooled passes for 585 more lookups than the bounded opening. The fixed switch gained 19 for 593 more. These pooled counts describe the archive because cohorts reuse tasks.

At its own spend, second-case-first exceeded the native GEPA upper bound in four cohorts and tied in two. It led the task-tuned simple point score only on bounded LMentry. The results support examining the qualification evidence for second-case nominees. Interleaving remains experimental and fresh live superiority remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview a plan seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.interleaved_validation_transfer --fit \
  --execute 43b7e3412d78972b4b8c141d76a682e6fab35c3b54d2229d3f3023fef4c2f2e2 \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.interleaved_validation_transfer \
  --cohort bounded-BBH --fitted NEW_FIT.json \
  --execute 0eeba395063f5cdb1a8b3cb2363d6b22c36174356df59ee10ab70c879335dac6 \
  --out NEW_REPORT.json
```

[Bounded BBH](interleaved-validation-transfer-bounded-bbh-v1.json) · [Bounded LMentry](interleaved-validation-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](interleaved-validation-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](interleaved-validation-transfer-four-case-mmlu-v1.json) · [Tie BBH](interleaved-validation-transfer-tie-bbh-v1.json) · [Tie LMentry](interleaved-validation-transfer-tie-lmentry-v1.json) · [Additional MMLU](interleaved-validation-transfer-additional-mmlu-v1.json)

Seventy-two targeted tests passed. Duplicate fits and target replays matched byte for byte with DNS and outbound sockets blocked. The replay reproduced all original bounded opening, fixed switch and router traces. Both endpoints and all per-cohort replacement sums reconciled for every treatment. No provider requests were made. Storage Guard measured 9.7 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_interleaved_validation.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
