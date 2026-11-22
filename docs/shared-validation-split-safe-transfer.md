# Reprice shared-panel CPO against split-safe GEPA

The archived paid-read GEPA runner supplied separate training and validation lists to GEPA 0.1.4. Both loaders numbered cases from zero, so the shared evaluation cache could reuse a training grade at the same validation position. A controlled check against the actual runner reproduced the problem in both GEPA modes. Giving the loaders disjoint IDs caused each mode to pay for all six validation cases and retain the true winner. [Cache identity regression tests](../tests/unit/test_shared_validation_split_safe_transfer.py) · [Earlier provider-archive correction](grounded-gepa-cache-controls.md)

The new replay keeps the published CPO wide nonloss policy and verifies the historical positional-cache controls before correcting them. Native GEPA keeps the same seeded order within each split, proposals, training, qualification wrappers, and held-out cases. Each GEPA mode can choose all six validation cases or the first three, which are the cases available to wide CPO. Native caps range from the cost of a full incumbent panel at each width through 180. At each realized CPO budget, the replay computes the exact subject-tuned ceiling over both split-safe widths, with one setting per subject shared across both checkpoints and all seeds. [Frozen CPO policy](budgeted-shared-panel-search.md) · [Split-safe replay driver](../benchmarks/shared_validation_split_safe_transfer.py)

The eight cohorts contain 134 archived model panels and 32 seeded schedules per panel at each qualification margin. The checkpoint transfer covers Flan-T5-XL and Minotaur-15B. Most transfer tasks also appear in the original study. Causal judgment and ends-with-word are the two additional tasks. The qualification and final holdout retain their original disjoint case assignments. [Checkpoint archive](../benchmarks/data/shortlist-model-transfer-v1.json)

## Results

Each entry gives held-out passes and paid lookups at one qualification gain. The corrected GEPA column uses the best subject-tuned schedule over both split-safe widths within CPO's realized budget.

| Cohort | Wide nonloss CPO | Corrected GEPA | CPO pass difference | Conditional paired 95% range |
| --- | ---: | ---: | ---: | ---: |
| [Original BBH](shared-validation-split-safe-bbh-results-v1.json) | 9,840 / 20,209 | 9,745 / 20,198 | +95 | +13 to +174 |
| [BBH, other checkpoints on previously studied tasks](shared-validation-split-safe-bbh-seen-task-results-v1.json) | 4,901 / 11,037 | 4,920 / 9,845 | −19 | −66 to +26 |
| [BBH, causal judgment](shared-validation-split-safe-bbh-new-task-results-v1.json) | 620 / 1,341 | 592 / 1,318 | +28 | +13 to +43 |
| [Original LMentry](shared-validation-split-safe-lmentry-results-v1.json) | 6,078 / 11,379 | 5,674 / 11,362 | +404 | +314 to +493 |
| [LMentry, other checkpoints on previously studied tasks](shared-validation-split-safe-lmentry-seen-task-results-v1.json) | 5,546 / 8,027 | 5,404 / 7,949 | +142 | +81 to +203 |
| [LMentry, ends-with-word](shared-validation-split-safe-lmentry-new-task-results-v1.json) | 315 / 1,465 | 278 / 1,279 | +37 | +19 to +56 |
| [Earlier MMLU](shared-validation-split-safe-earlier-screen-cohort-results-v1.json) | 26,642 / 17,421 | 26,655 / 8,574 | −13 | −59 to +34 |
| [Disjoint MMLU](shared-validation-split-safe-disjoint-transfer-cohort-results-v1.json) | 56,034 / 17,005 | 56,089 / 6,814 | −55 | −121 to +11 |

The paired ranges resample held-out cases within subject, holding the attaining GEPA settings fixed across draws. They describe these archived prompts and checkpoints. At two qualification gains, GEPA led in seven cohorts. CPO led by 25 passes on ends-with-word.

The capacity change matters even where it leaves the winner unchanged. On ends-with-word, letting corrected GEPA also use three validation cases raised its attainable one-gain score from 242 to 278. On earlier MMLU, the combined menu attained the same 26,655 passes as corrected six-case GEPA and saved 1,405 lookups. Across the eight cohorts at native search cap 180 and one qualification gain, disjoint cache IDs changed 939 nominations and 353 deployments across 8,576 sequential and batched trials. The CPO paths in the four previously measured cohorts reproduced exactly.

The wide policy remains opt-in. The replay supports one-gain performance on these LMentry cohorts and two of the three BBH cohorts. Fresh-model superiority remains unverified.

## Reproduce offline

Use Python 3.12 and the pinned GEPA 0.1.4 benchmark dependency. Preview the required cohort to get its seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.shared_validation_split_safe_transfer --cohort BBH
PYTHONHASHSEED=0 python -B -m benchmarks.shared_validation_split_safe_transfer \
  --cohort BBH --execute eb076840578e12983a8bf1b28c353c6c4e9f6ce7391a997d958b6297378cd67b \
  --out NEW_BBH_REPORT.json
```

Other cohorts are `LMentry`, `BBH/seen-task`, `LMentry/seen-task`, `BBH/new-task`, `LMentry/new-task`, `earlier-screen-cohort`, and `disjoint-transfer-cohort`.

Two socket-blocked runs per cohort matched byte for byte. Each phase checked 2,100 historical settings, 2,100 corrected six-case settings and 2,136 corrected three-case settings. The runner independently replayed the one-gain attaining GEPA schedule and reconciled scores and costs per subject. Thirteen targeted tests passed. Storage Guard measured 2.3 GiB free. The source export, benchmark wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. No provider requests were sent. [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
