# Compare full-roster CPO with subject-tuned GEPA

The earlier cap-19 study chooses a common GEPA setting for each cohort. This replay gives GEPA a separate choice for each subject. Each choice applies across both model checkpoints and all 32 schedules for that subject. GEPA can use either native search mode, any integer cap from 6 through 180, any of the three sealed qualification wrappers, or the retained start. The sum of search and qualification lookups across subjects must fit the realized CPO budget. [Common-setting comparison](deferred-certificate-cycle.md) · [Replay driver](../benchmarks/deferred_certificate_subject_ceiling.py)

The assignment maximizes archived held-out passes. It includes settings that would exceed the budget if applied to the whole cohort. The solver removes dominated score and cost pairs, then recovers a schedule that attains the exact ceiling. Held-out grades determine the GEPA choices, so the margin measures the archived hindsight comparison.

The replay verifies each full native cost curve and every previously published subject-budget solution before evaluating the new budgets. Each qualification variant reuses a native search only within the same scheduled trial and only at identical search inputs. It dispatches the stored evaluation and budget callbacks in their original order and checks their grades and cumulative spend as they run. The qualification variants keep their own actual costs and choices.

## Results

Each GEPA score is the best attainable at the lookup budget used by its CPO counterpart. CPO stays at the full-roster cap of 19. The pass differences are observed archive margins against the hindsight choices. [Exact settings, costs, and subject contributions](deferred-certificate-subject-ceiling-results-v1.json)

| Cohort | One-gain CPO passes / lookups | GEPA passes / lookups | CPO margin | Two-gain CPO passes / lookups | GEPA passes / lookups | CPO margin |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BBH, original | 9,548 / 16,146 | 9,650 / 16,145 | −102 | 8,998 / 15,149 | 9,605 / 15,108 | −607 |
| BBH, other checkpoints on previously studied tasks | 4,843 / 9,098 | 4,917 / 8,955 | −74 | 4,790 / 8,439 | 4,907 / 8,428 | −117 |
| BBH, causal judgment | 591 / 1,123 | 590 / 959 | +1 | 569 / 1,016 | 590 / 959 | −21 |
| LMentry, original | 5,650 / 8,781 | 5,424 / 8,776 | +226 | 5,192 / 8,386 | 5,388 / 8,349 | −196 |
| LMentry, other checkpoints on previously studied tasks | 5,307 / 6,174 | 5,117 / 6,095 | +190 | 4,963 / 5,402 | 5,018 / 5,396 | −55 |
| LMentry, ends-with-word | 263 / 1,170 | 233 / 1,000 | +30 | 256 / 1,186 | 233 / 1,000 | +23 |
| Disjoint MMLU | 56,094 / 12,933 | 56,116 / 11,578 | −22 | 56,094 / 9,017 | 56,112 / 8,948 | −18 |
| Earlier MMLU | 26,619 / 13,739 | 26,654 / 10,848 | −35 | 26,630 / 9,831 | 26,653 / 8,978 | −23 |

One-gain CPO exceeded the stronger GEPA control on all three LMentry groups. The largest original LMentry contributions came from rhyming word and homophones. On the alternate checkpoints, any words from category accounted for 158 of the 190 net passes. Separate GEPA settings reversed the one-gain leads on both previously studied BBH cohorts. The two new-task groups have one subject each, so their subject-tuned and common GEPA controls coincide. The prior paired range for CPO’s one-pass lead on BBH causal judgment crosses zero. Fresh-model performance and the quality of newly generated prompts remain unverified. [Paired fixed-control comparisons](deferred-certificate-cycle.md#full-roster-comparison-with-gepa)

Requiring a repair with zero qualification regressions narrowed the disjoint MMLU gap to 11 passes. The same guard lost passes on original BBH and two LMentry groups. [Regression-free qualification replay](regression-free-qualification.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. [Pinned wheel](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.deferred_certificate_subject_ceiling
PYTHONHASHSEED=0 python -B -m benchmarks.deferred_certificate_subject_ceiling \
  --execute 86c7519f36607d023c02e984daa940ffe070fe8d5fbd29b50474ace78b34d3f0 \
  --out NEW_REPORT.json
```

Two clean-source runs matched byte for byte at SHA-256 `3c92e05d85a303d96393c994610a434ceaf32487fef4437ff1351603235875b9`. The runner verified 8,400 native cohort-setting totals and 32 prior subject budgets, including their attaining schedules. A separate verification ran 5,056 direct schedule-setting executions and matched every new subject contribution without using search transcripts. All 22 targeted tests and four subtests passed. DNS and outbound sockets were blocked, and the CLI rejected the prior seal before creating a report. Storage Guard measured 3.2 GiB free. The source export, GEPA wheel overlay and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Search replay test](../tests/unit/test_deferred_certificate_subject_ceiling.py)
