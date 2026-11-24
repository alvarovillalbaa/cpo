# Transfer task-calibrated CPO schedules between models

The [task-disjoint discovery fit](quoted-schedule-discovery-transfer.md) improved the price and quality of several common schedules. It still trailed the simple controls selected separately on each target task's holdout. This study tests task-specific selection with prior archived evidence. Each of the 32 cohort-task pairs has two recorded model panels. One model calibrates the schedule and the other audits it, then the roles reverse. [Benchmark runner](../benchmarks/quoted_schedule_checkpoint_transfer.py)

Each task's fixed original scoring holdout is divided by hashed case ID. The calibration model scores one half and the audit model scores the other. Calibration uses the 16 even-position seeds and audit uses the 16 odd-position seeds from the original layout. The three-cycle prompt rosters and their disjoint training, validation and qualification cases retain the original sampler. Neither scoring fold enters any optimizer's search or qualification. The study tests transfer within a task between recorded models. The task and original archives remain familiar to earlier experiments.

For each direction, the three menus select a fixed setting that maximizes calibration passes within the calibration router's actual spend. The quoted and eager menus share all uniform and successive-halving settings and free retention. Native GEPA uses both modes, full and half validation widths, six independent proof wrappers, and every funded integer cap through 54. The audit directly replays each selected setting and compares the frozen discovery prefix, the original router and retention on the same episodes. It also replays the quoted policy's exact setting with eager accounting. Audit costs can differ because calibration never sees audit prices. All methods have a common ceiling of 54 search lookups and eight qualification lookups per cycle. These costs describe audit execution. Calibration uses already recorded grades.

## Audit results

Each cell gives final held-out passes and actual paid lookups. The two directions are summed for each task. The case-paired ranges in the receipts group results by original case ID and hold the chosen settings fixed.

| Cohort | Task-calibrated quoted | Task-calibrated eager | Task-calibrated GEPA | Frozen CPO prefix | Original CPO router |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 1,628 / 3,435 | 1,635 / 3,780 | 1,600 / 3,566 | 1,662 / 6,532 | 1,670 / 6,792 |
| Bounded LMentry | 1,549 / 6,797 | 1,408 / 6,510 | 1,205 / 6,660 | 1,590 / 7,856 | 1,582 / 7,773 |
| Bounded MMLU | 1,924 / 1,404 | 1,924 / 1,937 | 1,928 / 0 | 1,923 / 3,293 | 1,929 / 3,766 |
| Four-case MMLU | 5,538 / 1,285 | 5,538 / 1,811 | 5,538 / 0 | 5,546 / 5,257 | 5,561 / 6,007 |
| Tie BBH | 485 / 4,548 | 484 / 4,822 | 468 / 3,447 | 497 / 6,400 | 511 / 6,707 |
| Tie LMentry | 261 / 3,153 | 221 / 2,732 | 211 / 2,220 | 244 / 3,524 | 257 / 3,677 |
| Additional MMLU | 1,802 / 918 | 1,802 / 1,197 | 1,802 / 0 | 1,803 / 3,124 | 1,799 / 3,438 |

Quoting changed the selected setting in 18 of 64 directions. Holding the setting fixed, it saved 6,181 of 27,721 audit lookups, with the same held-out case totals as eager execution. Against the independently calibrated eager menu, the quoted menu gained 175 pooled passes and used 1,249 fewer lookups. The two LMentry gains had paired ranges above zero and cost more at audit time. The pooled totals are descriptive because cohorts reuse some tasks.

The quoted menu scored above the independently calibrated GEPA menu in four cohorts, matched it in two, and trailed by four passes in bounded MMLU. On bounded and tie LMentry it gained 344 and 50 passes, with paired ranges of +302 to +386 and +27 to +73. It spent 137 and 933 more audit lookups, respectively. The comparison matches calibration budgets and reports audit spend as observed.

Task calibration spent fewer lookups than the frozen CPO prefix in every cohort. On tie LMentry it gained 17 passes with 371 fewer lookups and a paired range of +9 to +25. On bounded LMentry it lost 41 passes with 1,059 fewer lookups. Its pooled total was 78 passes below the prefix and 14,446 lookups cheaper. Free retention matched or exceeded the quoted result in all three MMLU cohorts. The results support task calibration on some archived model transitions. Live inference and transfer to fresh tasks remain unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview the plan seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.quoted_schedule_checkpoint_transfer \
  --cohort bounded-LMentry \
  --execute 216f79919eb573c26bf8e5656376111c8b61e15ada353433aab91d1d8b3ad871 \
  --out NEW_REPORT.json
```

[Bounded BBH](quoted-schedule-checkpoint-transfer-bounded-bbh-v1.json) · [Bounded LMentry](quoted-schedule-checkpoint-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](quoted-schedule-checkpoint-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](quoted-schedule-checkpoint-transfer-four-case-mmlu-v1.json) · [Tie BBH](quoted-schedule-checkpoint-transfer-tie-bbh-v1.json) · [Tie LMentry](quoted-schedule-checkpoint-transfer-tie-lmentry-v1.json) · [Additional MMLU](quoted-schedule-checkpoint-transfer-additional-mmlu-v1.json)

Sixteen targeted tests passed. Two replays per cohort matched byte for byte with DNS and outbound sockets blocked. A separate direct replay verified the score and price of all three calibration choices in every direction. The study covered 1,024 audit episodes and issued zero provider requests. Storage Guard measured 9.9 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_quoted_schedule_checkpoint_transfer.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
