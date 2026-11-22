# Match the threshold precheck on CPO and GEPA

The threshold precheck reduced CPO’s lookup count at the two-gain margin on four archived cohorts. This comparison gives both native GEPA modes the same precheck. A paid incumbent pass reduces the maximum attainable gain by one. A gain below two stops the trial before search, and two incumbent misses release the original search. The subsequent independent proof credits every incumbent reply that the precheck bought. [CPO precheck and path replay](threshold-prechecked-cycle.md) · [Replay driver](../benchmarks/threshold_precheck_gepa_frontier.py)

The replay covers 102 model panels and 32 schedules per panel. CPO uses its published cap-13 screen at both margins. Sequential and batched GEPA each get every integer search cap from 6 to 180 under the earlier one- and two-gain wrappers and the threshold-prechecked two-gain wrapper. All arms use the same starts, fixed candidate rosters and case splits. Each paired draw reselects the highest-scoring common GEPA setting or retained starts at the CPO arm’s realized search-plus-qualification budget. The replay also reports what GEPA could attain by choosing a different setting for each subject with hindsight. [Original matched MMLU comparison](recorded-matched-qualification-margin.md) · [Original language comparison](recorded-qualification-margin-language-transfer.md)

## Results

The gate requires a positive observed held-out margin with a nonnegative lower paired endpoint. The table compares each CPO variant with the strongest affordable control across all wrappers. The paired ranges use 4,096 held-out case draws within subjects. [Full matched curves and subject schedules](threshold-precheck-gepa-frontier-results-v1.json)

| Cohort | CPO qualification | CPO passes / lookups | Best affordable control | CPO margin and paired 95% range | Gate |
| --- | --- | ---: | --- | ---: | --- |
| BBH | One gain | 9,363 / 12,567 | Sequential cap 16, one gain | +450 [390, 513] | Passed |
| BBH | Two gains | 8,953 / 12,107 | Sequential cap 16, one gain | +40 [−6, 86] | Inconclusive |
| LMentry | One gain | 5,166 / 7,105 | Sequential cap 16, one gain | +583 [517, 650] | Passed |
| LMentry | Two gains | 4,826 / 6,911 | Sequential cap 16, one gain | +243 [193, 295] | Passed |
| Disjoint MMLU | One gain | 56,079 / 9,596 | Sequential cap 16, one gain | +11 [−26, 42] | Inconclusive |
| Disjoint MMLU | Two gains | 56,094 / 7,110 | Retain starts | +29 [10, 46] | Passed |
| Earlier MMLU | One gain | 26,613 / 10,253 | Retain starts | −12 [−40, 12] | Inconclusive |
| Earlier MMLU | Two gains | 26,628 / 7,746 | Retain starts | +3 [−6, 10] | Inconclusive |

The precheck also made native GEPA cheaper on many settings. On disjoint MMLU, two-gain sequential GEPA at cap 16 fell from 9,286 to 6,985 lookups and preserved 56,065 passes. It tied the retained starts on accuracy. The new settings therefore changed which options the paired draws could afford even when the best observed control stayed the same.

GEPA’s subject-tuned hindsight ceiling exceeded both CPO variants on all four cohorts at each CPO budget. It uses held-out grades to choose a setting for each subject. Fixed-roster replay supports the reported cost and outcome comparisons. Fresh-model superiority and performance on a new candidate pool remain unverified.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. [Wheel requirement](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.threshold_precheck_gepa_frontier
PYTHONHASHSEED=0 python -B -m benchmarks.threshold_precheck_gepa_frontier \
  --execute d93cb3758cd8de37d266e655238375a162c2881c02649c0ff1f879a45f51001f \
  --out NEW_REPORT.json
```

Two clean-source runs with DNS and outbound sockets blocked produced byte-identical reports at SHA-256 `2f5c498945d4ef5dbe8b4841047449d426769a59b1ede6d07826cd9ca1f58921`. The replay checked 98,844 legacy GEPA paths, 40,370 threshold-prechecked GEPA paths and 6,528 paid CPO callback paths. Another 8,128 direct schedule-setting executions verified the selected common controls and the attaining subject schedules. All 15 targeted tests and four subtests passed. The CLI rejected the predecessor seal before writing an output file. Storage Guard measured 3.9 GiB free and the temporary work fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Regression tests](../tests/unit/test_threshold_precheck_gepa_frontier.py)
