# Match the language validation-tail policies to GEPA’s realized cost

Reserving the end of validation saved lookups on BBH, LMentry, and MMLU at the original shared search cap. This replay keeps the same 26 language panels, splits, starts, rosters, and independent qualification. It sweeps sequential and batched GEPA from 6 through 180 permitted search lookups, for 350 native settings per cohort. Both search and qualification count toward the realized lookup budget, and retaining the starts is available at zero cost. [Original validation-tail benchmark](recorded-validation-tail-finalists.md) · [Frontier runner](../benchmarks/recorded_validation_tail_language_frontier.py)

The common-cap comparison picks the highest-scoring setting affordable at each CPO policy's realized spend. Its paired 95% range resamples case IDs within each subject and reselects the affordable setting on each draw. Models and repeated trials for the same cases stay paired. A separate, optimistic comparison can choose the GEPA mode and a fixed cap for each subject using its held-out results. Both model panels of a subject share that choice, and the cohort total must fit the same budget. The report lists a fixed subject schedule attaining each optimum. [All cap points, paired ranges, and subject schedules](recorded-validation-tail-language-frontier-results-v1.json)

| Cohort and CPO policy | CPO passes / lookups | Best affordable common GEPA passes / lookups | CPO margin and paired 95% range | Subject-tuned GEPA ceiling / lookups |
| --- | ---: | ---: | ---: | ---: |
| BBH, full validation | 2,121 / 11,258 | 2,099 / 10,792 | +22, −12 to +50 | 2,109 / 9,309 |
| BBH, one reserved case | 2,125 / 10,569 | 2,096 / 10,287 | +29, −5 to +55 | 2,109 / 9,309 |
| BBH, two reserved cases | 2,117 / 9,979 | 2,089 / 9,101 | +28, −12 to +57 | 2,109 / 9,309 |
| LMentry, full validation | 939 / 6,106 | 842 / 4,571 | +97, +64 to +124 | 842 / 4,182 |
| LMentry, one reserved case | 926 / 5,635 | 842 / 4,571 | +84, +48 to +115 | 842 / 4,182 |
| LMentry, two reserved cases | 924 / 5,219 | 842 / 4,571 | +82, +47 to +112 | 842 / 4,182 |
| MMLU, full validation | 13,442 / 12,319 | 13,447 / 8,776 | −5, −30 to +14 | 13,455 / 5,714 |
| MMLU, one reserved case | 13,449 / 11,814 | 13,447 / 8,776 | +2, −25 to +24 | 13,455 / 5,714 |
| MMLU, two reserved cases | 13,444 / 11,464 | 13,447 / 8,776 | −3, −31 to +20 | 13,455 / 5,714 |

On LMentry, two reserved cases saved 887 lookups versus full validation and gave up 15 passes. They retained a positive paired margin over the best affordable GEPA setting. BBH's one-case policy had the largest point lead and an inconclusive paired range. On MMLU the batched 38-cap setting improved the GEPA point to 13,447 at 8,776 lookups. The subject-tuned schedule reached 13,455 at 5,714 lookups, six more passes than one-case CPO, using fewer than half its lookups. The subject settings use hindsight and describe these archived panels. Fresh performance remains unverified.

A follow-up swept CPO’s caps as well. At 5,714 available lookups on MMLU, a cap of 13 on the strict validation race led the common comparison. [Symmetric cap sweep](recorded-validation-tail-matched-caps.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Two socket- and DNS-blocked runs matched byte for byte. All 67 targeted tests passed from a clean export. The suite verified the integer-cap sweep by directly running every cap on representative episodes in each cohort and both GEPA modes. It checked subject-budget pooling against brute force. A separate direct audit checked the selected common and subject-specific schedules. The original CPO endpoints, full-cap native traces, sealed live-plan preview, and public selector receipt reproduced. The CLI rejected the prior seal. Storage Guard measured 1.7 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_validation_tail_language_frontier
python -B -m benchmarks.recorded_validation_tail_language_frontier \
  --execute 01fa5bd33a37aaf219f101b7d68ef5771914fcb6c76a123b60cfdbed3f6e23cc \
  --out NEW_REPORT.json
```
