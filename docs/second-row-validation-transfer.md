# Test a second validation case within the original search cap

The [quoted first-reply policy](quoted-schedule-discovery-transfer.md) funds one shared validation row on its broad halving branch. A passing incumbent ends that search after one lookup even though the cap is nine. This experiment uses part of that unused allowance to buy the next incumbent validation reply. A second pass closes search. On a miss, the **repair** screen can nominate the first challenger that passes the missed case. The **preservation** screen requires that challenger to pass both cases. Both variants use the same ordered roster of up to six challengers and retain the nine-lookup validation cap. The first case is never read twice. A first-row miss or a critical validation panel follows the original screen. Any nominee still needs to pass independent qualification. [Screen implementation](../cpo/second_row_validation.py)

The discovery fit evaluates all 27 tables across the three later first-miss positions in the paid incumbent qualification prefix. Each position can keep the original screen, add the repair screen, or add the preservation screen. A qualification miss on the first case keeps the original incumbent-first action in every table. The fit reuses 70 model-and-task panels from 31 tasks, excluding every target task. Each discovery cohort retains the original router's lookup allowance. The selectors use no additional qualification replies.

## Discovery results

Only three tables fit every discovery budget. The original schedule scored 84,037 passes at 67,684 lookups. The two feasible alternatives enable a second row only at the fourth qualification miss position. Each lost one pass and used at least 657 more lookups. The best table ignoring the per-cohort constraints gained 60 passes with 3,985 more lookups. It exceeded the LMentry and LMentry/seen-task allowances by 202 and 141 lookups, respectively. The fitted replay kept the original schedule and reproduced its paid paths. [Frozen fit and all 27 points](second-row-validation-fit-v1.json)

## Transfer results

Cells give final held-out passes and paid lookups over the same 2,048 archived episodes. Both fixed second-row variants enable the extra case at all three eligible positions. For the repair variant, the last columns show the full-grid GEPA upper bound and task-tuned simple control at the repair variant's realized spend. The simple portfolio uses target holdout grades to choose affordable settings. The replay receipts contain the full GEPA brackets and the preservation variant's matched comparisons.

| Cohort | Original and fitted | Fixed repair | Fixed preservation | Router lookups | Repair GEPA upper bound | Repair task-tuned simple |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,347 / 13,501 | 6,376 / 14,551 | 6,370 / 14,558 | 13,797 | 6,361 | 6,404 / 14,333 |
| Bounded LMentry | 6,338 / 15,666 | 6,399 / 16,461 | 6,394 / 16,431 | 15,711 | 6,070 | 6,399 / 16,323 |
| Bounded MMLU | 7,719 / 6,630 | 7,718 / 7,295 | 7,718 / 7,302 | 7,696 | 7,717 | 7,732 / 6,001 |
| Four-case MMLU | 22,369 / 10,728 | 22,369 / 11,550 | 22,369 / 11,553 | 12,145 | 22,369 | 22,409 / 10,430 |
| Tie BBH | 2,145 / 12,541 | 2,154 / 12,882 | 2,147 / 12,829 | 13,130 | 2,126 | 2,172 / 12,620 |
| Tie LMentry | 992 / 6,976 | 992 / 7,053 | 992 / 7,046 | 7,195 | 919 | 1,013 / 6,884 |
| Additional MMLU | 7,399 / 6,468 | 7,399 / 7,190 | 7,399 / 7,203 | 7,257 | 7,399 | 7,407 / 6,611 |

Fixed repair gained 98 passes for 4,472 more lookups across the archive. Fixed preservation gained 80 for 4,412 more. The fixed repair gains on bounded BBH and bounded LMentry were +29 and +61, with paired 95% ranges of +2 to +55 and +29 to +95. Both variants exceeded the existing router's spend on those two cohorts. The three MMLU cohorts together used 2,209 additional repair lookups and lost one pass. The pooled figures are descriptive because cohorts reuse some tasks.

Fixed repair exceeded the native GEPA upper bound in five cohorts and tied it in two at its higher spend. It matched the task-tuned simple score on bounded LMentry using 138 more lookups and scored below it in the other six cohorts. The fixed controls show that an extra witness sometimes recovers a useful challenger. Selecting where to spend those lookups under the original cohort budgets remains open. The fitted policy stays on the original schedule. Live quality remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview the seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.second_row_validation_transfer --fit \
  --execute c7dc8e98663d39444289187c5eda14474e065826cc152b9e649fe7e25df34257 \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.second_row_validation_transfer \
  --cohort bounded-LMentry --fitted NEW_FIT.json \
  --execute 27f35b79feb0dd0b5d732a7e38e5aac5ab79ada5833492ed7dde7203efe21ac1 \
  --out NEW_REPORT.json
```

[Bounded BBH](second-row-validation-transfer-bounded-bbh-v1.json) · [Bounded LMentry](second-row-validation-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](second-row-validation-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](second-row-validation-transfer-four-case-mmlu-v1.json) · [Tie BBH](second-row-validation-transfer-tie-bbh-v1.json) · [Tie LMentry](second-row-validation-transfer-tie-lmentry-v1.json) · [Additional MMLU](second-row-validation-transfer-additional-mmlu-v1.json)

Thirty-three targeted tests passed. Two fits and two replays for each cohort matched byte for byte. The verification checked source hashes, all qualification and search accounting boundaries exercised by the replay, and the exact original paid trajectories. DNS and outbound sockets were blocked, and no provider requests were made. Storage Guard measured 9.8 GiB free. The export, GEPA wheel overlay and publication checkout fit the standing LAB 0.2 GiB exception. [Targeted tests](../tests/unit/test_second_row_validation.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
