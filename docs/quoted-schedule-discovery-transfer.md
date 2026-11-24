# Fit quoted CPO schedules on separate discovery tasks

The [prior audit](reinvested-halving-gap-attribution.md) established that quoted validation can reproduce eager decisions at lower cost. Its strongest schedules were chosen on archived evaluation cases. This study freezes the schedule before target scoring. The discovery set contains 70 model-and-task panels across 31 tasks. Every target task is excluded from discovery, while the original seven target cohorts, 32 seeds, disjoint case roles, and three-cycle layouts are preserved. [Fit and replay runner](../benchmarks/quoted_schedule_discovery_transfer.py)

The paired fits use the same discovery cohorts, original CPO router budget for each cohort, and action menu. Uniform and successive-halving actions use quoted validation in one fit and eager validation in the other. The other screens keep their earlier implementations. The fixed fit chooses one action for every cycle. The prefix fit chooses an action from the first already-paid incumbent qualification reply. The same rule applies in all three cycles. Each fit maximizes total discovery passes with ties broken by lower cost and then action name. No target grades enter that selection.

The target replay verifies the old router's original paid paths. It replays the two old eager selections and also executes the new choices with eager accounting, so the effect of changing the schedule can be distinguished from the effect of skipping reads. At each quoted policy's actual spend, the study directly verifies the affordable simple controls and the feasible native GEPA anchors. The full-grid native receipt provides upper bounds when the archived prices bracket the new budget. Task-tuned simple controls still select schedules using target holdout grades.

## Frozen discovery choices

| Fit | First incumbent reply fails | First incumbent reply passes | Discovery passes / lookups |
| --- | --- | --- | ---: |
| Quoted prefix | Incumbent-first | Halving, eight challengers, cap 9 | 84,037 / 67,684 |
| Quoted fixed | Halving, four challengers, cap 10 | Same action | 83,661 / 59,534 |
| Eager prefix | Incumbent-first | Retain after precheck | 83,807 / 58,505 |
| Eager fixed | Halving, four challengers, cap 8 | Same action | 83,539 / 62,505 |

Both quoted selections fit the original per-cohort discovery budgets. The frozen discovery router scored 84,194 passes across 73,806 lookups. The quoted prefix's wide action buys one validation row across all eight challengers under its nominal cap. The quoted fixed action can fund three shared rows. [Original eager fit](adaptive-archive-search-fit-v1.json)

## Target results

Cells give final held-out passes and total paid lookups. The last two columns price the controls at the quoted prefix's realized budget. The replay receipt also contains controls priced at the quoted fixed policy's budget.

| Cohort | Quoted prefix | Quoted fixed | Existing router | Task-tuned GEPA upper bound | Task-tuned simple |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,347 / 13,501 | 6,341 / 12,374 | 6,389 / 13,797 | 6,350 | 6,396 / 13,484 |
| Bounded LMentry | 6,338 / 15,666 | 5,843 / 12,672 | 6,321 / 15,711 | 5,931 | 6,349 / 15,660 |
| Bounded MMLU | 7,719 / 6,630 | 7,719 / 6,503 | 7,725 / 7,696 | 7,717 | 7,732 / 6,001 |
| Four-case MMLU | 22,369 / 10,728 | 22,389 / 9,624 | 22,381 / 12,145 | 22,369 | 22,409 / 10,430 |
| Tie BBH | 2,145 / 12,541 | 2,116 / 9,173 | 2,204 / 13,130 | 2,126 | 2,169 / 12,460 |
| Tie LMentry | 992 / 6,976 | 954 / 4,533 | 1,028 / 7,195 | 919 | 1,013 / 6,884 |
| Additional MMLU | 7,399 / 6,468 | 7,394 / 6,380 | 7,384 / 7,257 | 7,399 | 7,405 / 5,354 |

The quoted prefix exceeded the GEPA upper bound in four cohorts, matched it in two, and fell three passes short in bounded BBH. Both quoted policies stayed within the existing router's spend in all seven cohorts. The prefix improved on the router by 17 passes at 45 fewer lookups on bounded LMentry and 15 passes at 789 fewer lookups on additional MMLU. Their paired 95% ranges were −16 to +50 and +5 to +26. The prefix also gained 89 passes over the older eager prefix on bounded LMentry, with a range of +60 to +117, using more lookups.

Holding the fitted actions fixed, quoted execution preserved the eager held-out case totals and saved 12,518 lookups for the prefix and 12,051 for the fixed policy across the cohorts. Relative to the old eager fixed fit, the quoted fixed fit gained 76 pooled passes and saved 667 lookups. These pooled counts are descriptive because the cohorts reuse some tasks. Both quoted fits scored below the affordable task-tuned simple schedule in every cohort. General task-conditioned selection and live performance remain unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview each plan seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.quoted_schedule_discovery_transfer --fit \
  --execute 9bcae1306d25ffd137c572f95f0d6a4743630b6bb6824ccce22120de0b332e13 \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.quoted_schedule_discovery_transfer \
  --cohort bounded-LMentry --fitted NEW_FIT.json \
  --execute d61e13d8d91c817bd9bd89237d02d48ec2530233c653593ca82f972e871bb829 \
  --out NEW_REPORT.json
```

[Frozen fit](quoted-schedule-discovery-fit-v1.json) · [Bounded BBH](quoted-schedule-discovery-transfer-bounded-bbh-v1.json) · [Bounded LMentry](quoted-schedule-discovery-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](quoted-schedule-discovery-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](quoted-schedule-discovery-transfer-four-case-mmlu-v1.json) · [Tie BBH](quoted-schedule-discovery-transfer-tie-bbh-v1.json) · [Tie LMentry](quoted-schedule-discovery-transfer-tie-lmentry-v1.json) · [Additional MMLU](quoted-schedule-discovery-transfer-additional-mmlu-v1.json)

Thirteen targeted tests passed. Two independent fits and two replays for each cohort matched byte for byte with DNS and outbound sockets blocked. An altered fit plan was rejected before target evaluation. The seven cohorts covered 2,048 episodes and the experiment issued zero provider requests. Storage Guard measured 9.9 GiB free. The temporary source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_quoted_schedule_discovery_transfer.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
