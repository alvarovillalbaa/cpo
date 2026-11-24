# Check whether discovery cohort floors improve episode routing

The frozen two-probe schedule beats the subject-tuned archived GEPA budget bound in both LMentry cohorts and tie BBH. It trails that bound by 2–12 passes in the other four cohorts. The discovery fit also loses 17 passes in new-task BBH and 29 and 23 passes in the two LMentry discovery cohorts. A pooled pass objective can accept those losses in exchange for gains elsewhere. [Original fit and transfer](settled-episode-refit.md)

This fit requires each discovery cohort to match or exceed the bounded opening's exact held-out score and stay within its realized lookup budget, including any probes. Within those constraints it maximizes pooled passes and breaks ties by realized lookups. It uses the original schedule menu and the same 70 discovery panels from 31 tasks. The verifier reproduces the original budget-only fit before scoring the guarded table on the separate archived target enrollment. [Benchmark](../benchmarks/settled_episode_cohort_guard.py)

## Discovery result

The cohort floors admit one of the 2,150 budget-feasible tables. It selects the bounded opening after every possible training outcome, so the settled probe buys zero training replies. The guard reproduces the bounded opening's 84,043 discovery passes on 67,022 lookups. The original fit records 84,046 passes on 64,938 lookups. The guard therefore yields no new routing policy within this menu.

## Transfer at realized cost

Each GEPA column is the upper bound for subject-tuned, split-safe GEPA at the corresponding policy's lookup count. The verifier replays affordable GEPA settings that establish the lower bound and preserves intervals where the upper bound lacks an exact witness at that cost. Scores are passes on the archived holdout cases.

| Cohort | Guarded passes / lookups | GEPA upper at guarded cost | Frozen passes / lookups | GEPA upper at frozen cost |
| --- | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,347 / 13,421 | 6,350 | 6,338 / 12,340 | 6,350 |
| Bounded LMentry | 6,338 / 15,636 | 5,931 | 6,390 / 15,146 | 5,931 |
| Bounded MMLU | 7,719 / 6,554 | 7,717 | 7,715 / 5,956 | 7,717 |
| Four-case MMLU | 22,369 / 10,591 | 22,369 | 22,366 / 10,522 | 22,369 |
| Tie BBH | 2,145 / 12,521 | 2,126 | 2,138 / 12,520 | 2,126 |
| Tie LMentry | 992 / 6,971 | 919 | 1,004 / 6,863 | 919 |
| Additional MMLU | 7,398 / 6,354 | 7,399 | 7,397 / 6,211 | 7,399 |

Across the 2,048 archived episodes, the guard gives up 40 passes and uses 2,490 more lookups. The two LMentry cohorts account for 64 lost passes and 598 additional lookups. The paired 95% ranges for those losses are 21–83 in bounded LMentry and 2–21 in tie LMentry. These ranges resample cases within the enrolled subjects. They describe the archive, where subjects may recur across cohorts. Fresh live quality remains unverified. [Replay receipt](settled-episode-cohort-guard-v1.json)

The packaged policy retains its original schedule table. Within the tested menu, mandatory cohort-level score floors select the bounded opening for every episode.

## Reproduce offline

Use the pinned GEPA 0.1.4 benchmark environment and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.settled_episode_cohort_guard --out /tmp/cpo-cohort-guard.json
```

Two runs with sockets and DNS blocked produced identical receipts. Fifty-eight targeted tests passed, including an exhaustive check of the guarded fitter against paid callback traces on small tables. Storage Guard measured 9.6 GiB free. The disposable source, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception and were removed after verification. No provider requests were made. [Guard tests](../tests/unit/test_settled_episode_cohort_guard.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
