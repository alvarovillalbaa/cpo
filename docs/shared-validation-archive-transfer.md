# Transfer the frozen shared validation policies

The recent repair races reused the same model and task pairs. This replay enrolls 56 pairs absent from those comparisons, drawn from three existing correctness snapshots. The cases and prompt templates were already archived. Several tasks appeared in the earlier study on other checkpoints. The runner verifies the three snapshot hashes, checks for duplicate or previously scored model and task pairs, and keeps both checkpoints for each enrolled task. [Discovery comparison](paired-repair-race.md) · [Bounded discovery archive](bounded-discovery-transfer.md) · [Four-case archive](four-case-qualification-transfer.md) · [Tie extension archive](tie-extension-cross-benchmark.md)

The replay applies certified wide, incumbent-first, single repair, and preserve one at one and two independent qualification gains. The primary is preserve one on MMLU and certified wide on BBH and LMentry. Each trial uses the original one-cycle schedule, an eight-challenger roster, ten training cases, six validation cases, four separate qualification cases, and a fixed 30% holdout. Search and qualification pay for their actual replies. The 19-lookup CPO search cap and all four policies are unchanged from discovery. [Transfer runner](../benchmarks/shared_validation_archive_transfer.py)

GEPA 0.1.4 uses the same starts, rosters, and splits. The sweep includes both native modes, both split-safe validation widths, six qualification wrappers, and every funded integer search cap through 180. That gives 4,236 settings per cohort. The best common setting must fit the primary's realized budget across the whole cohort. The subject-tuned comparison can choose a different setting for each subject at the same pooled budget. Both menus also permit retaining the start. [Split-safe GEPA protocol](shared-validation-split-safe-transfer.md)

## One-gain transfer results

Each score and cost column gives held-out passes / paid lookups. The gate requires a positive paired lower endpoint against the best affordable common setting and a higher point score than the subject-tuned ceiling.

| Cohort and size | Primary CPO | Best common GEPA | Subject-tuned GEPA | CPO paired 95% range vs subject-tuned GEPA | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| [Bounded MMLU, 8 panels](shared-validation-archive-transfer-bounded-mmlu-v1.json) | 7,711 / 2,833 | 7,710 / 1,926 | 7,716 / 2,026 | −20 to +9 | Missed |
| [Four-case MMLU, 12 panels](shared-validation-archive-transfer-four-case-mmlu-v1.json) | 22,348 / 4,083 | 22,348 / 0 | 22,348 / 0 | −6 to +6 | Missed |
| [Bounded BBH, 12 panels](shared-validation-archive-transfer-bounded-bbh-v1.json) | 6,290 / 7,336 | 6,232 / 7,226 | 6,306 / 7,202 | −85 to +53 | Missed |
| [Bounded LMentry, 12 panels](shared-validation-archive-transfer-bounded-lmentry-v1.json) | 5,539 / 7,575 | 4,960 / 7,465 | 5,312 / 7,558 | +162 to +289 | Passed |
| [Tie BBH, 8 panels](shared-validation-archive-transfer-tie-bbh-v1.json) | 2,077 / 5,631 | 2,045 / 4,704 | 2,083 / 5,470 | −50 to +37 | Missed |
| [Tie LMentry, 4 panels](shared-validation-archive-transfer-tie-lmentry-v1.json) | 815 / 2,819 | 746 / 2,632 | 822 / 2,754 | −34 to +19 | Missed |

Bounded LMentry's primary led the common setting by 579 passes, with a paired 95% range of +518 to +637. The cheaper single-repair arm scored 5,217 on 3,993 lookups, 434 passes above the subject-tuned ceiling at that lower budget. That is a secondary point result. Tie LMentry also had a positive paired lower endpoint against the common setting, but the subject-tuned ceiling led by seven passes. On both BBH cohorts the ranges cross zero against both native comparisons. On four-case MMLU the best affordable native policy retained the start. The primary CPO arm changed some deployments and tied the total score.

Each interval resamples held-out cases within a task, keeping both checkpoints and all 32 seeded trials together. The attaining GEPA settings were selected using the archived holdout and stay fixed during resampling. The results describe these archived prompt banks. Fresh-model performance remains unverified.

## Reproduce offline

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel. The first command previews the seal for the selected cohort. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.shared_validation_archive_transfer --cohort bounded-LMentry
PYTHONHASHSEED=0 python -B -m benchmarks.shared_validation_archive_transfer \
  --cohort bounded-LMentry \
  --execute c838b54fced7dc1818f6a98dd913fbe155f8558b92bffa50fc8b9543f0d25e50 \
  --out NEW_REPORT.json
```

The other cohort names are `bounded-MMLU`, `four-case-MMLU`, `bounded-BBH`, `tie-BBH`, and `tie-LMentry`. Two DNS- and socket-blocked source replays matched byte for byte in each cohort. The replays reconciled each primary GEPA attainer's costs and case scores by subject. Twenty-three targeted tests passed. A separate check verified all 1,792 paired schedules for disjoint case roles and detected a normalized checkpoint alias in the exclusion list. Storage Guard measured 10.8 GiB free at preflight. The source export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
