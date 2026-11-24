# Verify task-specific CPO schedules before switching

The [cross-model replay](quoted-schedule-checkpoint-transfer.md) found that a task-specific schedule could save lookups while losing passes relative to the frozen discovery prefix. This study keeps the same 64 model directions and splits each direction's original calibration cases into separate selection and guard sets by hashed case ID. The audit model, audit cases, audit seeds and original search and qualification layouts remain fixed. Selection and guard share calibration seeds and use disjoint scoring cases. The audit uses the other model, different cases and different seeds. [Replay runner](../benchmarks/quoted_schedule_guarded_transfer.py)

The candidate is the best quoted schedule within the calibration router's realized budget, selected using only the selection cases. The guard switches from the frozen discovery prefix only when the candidate's paired 95% lower endpoint on guard cases is nonnegative and its lookup cost is at most the prefix's. A strict saving or a positive lower endpoint breaks a tie. The final audit compares this policy with the same candidate without the guard, the frozen prefix, and the original checkpoint-transfer controls. Selection and guard use already archived grades. The table charges actual audit lookup spend.

## Audit results

Each cell gives final held-out passes and paid lookups. The last column counts accepted switches across both directions for each task.

| Cohort | Guarded policy | Same candidate without the guard | Frozen prefix | Switches |
| --- | ---: | ---: | ---: | ---: |
| Bounded BBH | 1,643 / 5,860 | 1,629 / 4,221 | 1,662 / 6,532 | 2 |
| Bounded LMentry | 1,590 / 7,720 | 1,501 / 6,571 | 1,590 / 7,856 | 1 |
| Bounded MMLU | 1,922 / 1,913 | 1,924 / 1,094 | 1,923 / 3,293 | 5 |
| Four-case MMLU | 5,544 / 2,257 | 5,538 / 1,083 | 5,546 / 5,257 | 9 |
| Tie BBH | 495 / 6,230 | 486 / 4,566 | 497 / 6,400 | 1 |
| Tie LMentry | 244 / 3,393 | 264 / 3,113 | 244 / 3,524 | 1 |
| Additional MMLU | 1,803 / 1,467 | 1,802 / 193 | 1,803 / 3,124 | 5 |

The guard accepted 24 of 64 switches. All 24 saved audit lookups. Seventeen matched the prefix's audit score, two improved it, and five lost passes. Fifteen of the accepted directions used retention. Among the 40 decisions to keep the frozen prefix, the smaller-calibration schedule would have lost passes in 16 and gained passes in 13. These outcomes measure a transfer tradeoff across models and cases.

Across the seven cohorts, the guard recovered 97 of the unguarded policy's 121 lost passes relative to the frozen prefix. It finished 24 passes below the prefix and used 7,146 fewer lookups, a 19.9% reduction. These sums are descriptive because cohorts reuse some tasks. Paired ranges against the frozen prefix included zero in all cohorts. On bounded LMentry the guard recovered 89 passes over unguarded selection, with a paired range of +57 to +119. It matched the prefix's 1,590 passes and saved 136 lookups. On tie LMentry it lost 20 passes relative to unguarded selection, with a paired range of −27 to −13. Live performance remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview the seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.quoted_schedule_guarded_transfer \
  --cohort bounded-LMentry \
  --execute 3d67139d2f16c5a957ab45315c49256fe5a568a745500cc0629bba9aa45664e6 \
  --out NEW_REPORT.json
```

[Bounded BBH](quoted-schedule-guarded-transfer-bounded-bbh-v1.json) · [Bounded LMentry](quoted-schedule-guarded-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](quoted-schedule-guarded-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](quoted-schedule-guarded-transfer-four-case-mmlu-v1.json) · [Tie BBH](quoted-schedule-guarded-transfer-tie-bbh-v1.json) · [Tie LMentry](quoted-schedule-guarded-transfer-tie-lmentry-v1.json) · [Additional MMLU](quoted-schedule-guarded-transfer-additional-mmlu-v1.json)

Fourteen targeted tests passed. Two replays per cohort matched byte for byte with DNS and outbound sockets blocked. A separate receipt audit checked the three disjoint sets of scoring cases and the switch rule for all 64 directions. The study covered 1,024 audit episodes and issued zero provider requests. Storage Guard measured 9.9 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_quoted_schedule_guarded_transfer.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
