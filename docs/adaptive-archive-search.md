# Choose a search screen from the first paid qualification reply

The earlier three-cycle replay found that uniform screening and successive halving were competitive under CPO's lookup budget. This experiment gives CPO those search options alongside its existing screens. The policy uses one action if the incumbent fails its first qualification case and another if it passes. The qualification precheck already pays for that reply. Both branches receive the same disjoint validation cases, candidate roster, and exact one-net-gain promotion rule. The fixed control can choose the same menu of actions but uses one action on both branches. [Previous search controls](continuous-search-controls.md) · [Replay runner](../benchmarks/adaptive_archive_search.py)

The fit excludes every subject present in any of the seven target cohorts, including a discovery cohort with no eligible subjects. It evaluates all pairs of the four existing screens, 24 uniform or halving settings, and retention after the precheck. It carries the deployed prompt forward for three cycles and maximizes total discovery passes with a separate cap for each discovery cohort. The cap is the earlier routed CPO policy's realized lookup count on that cohort. Ties favor lower cost and then action name. The fixed and adaptive choices use the same caps. [Discovery fit](adaptive-archive-search-fit-v1.json)

Transfer reuses the published starts, fixed rosters, disjoint case roles and final holdout. The earlier router reproduces every paid trajectory. The replay identifies and directly executes the strongest affordable common setting in each simple family and the subject-tuned mixture at the adaptive policy's realized lookup cost. GEPA uses published cost anchors, with the affordable common anchor replayed directly. Equal lower and upper bounds identify the exact affordable common score. The gate requires a positive paired lower endpoint against the earlier router, fitted fixed search, the best common simple controls and the exact common GEPA score. It also requires a higher score than both subject-tuned ceilings and spending no more than the earlier router.

## Discovery

The fit covered 70 model-task panels in seven eligible discovery cohorts. It chose incumbent-first search after a failed first qualification reply and retention after a pass. The fixed control chose four-challenger successive halving with a validation cap of eight lookups. The adaptive policy scored 83,807 passes at 58,505 lookups. Fitted fixed scored 83,539 at 62,505. The earlier router scored 84,194 at 73,806. Its score was higher in each discovery cohort.

## Transfer

| Cohort | Adaptive search | Fitted fixed | Earlier router | Subject-tuned simple controls | Subject-tuned GEPA range |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Bounded BBH](adaptive-archive-search-bounded-bbh-v1.json) | 6,311 / 11,187 | 6,321 / 12,570 | 6,389 / 13,797 | 6,379 / 10,672 | 6,111 to 6,350 |
| [Bounded LMentry](adaptive-archive-search-bounded-lmentry-v1.json) | 6,249 / 14,134 | 5,839 / 12,385 | 6,321 / 15,711 | 6,229 / 14,096 | 3,855 to 5,931 |
| [Bounded MMLU](adaptive-archive-search-bounded-mmlu-v1.json) | 7,713 / 5,323 | 7,717 / 7,303 | 7,725 / 7,696 | 7,727 / 4,221 | 7,706 to 7,717 |
| [Four-case MMLU](adaptive-archive-search-four-case-mmlu-v1.json) | 22,368 / 8,650 | 22,357 / 10,251 | 22,381 / 12,145 | 22,406 / 7,964 | 22,348 to 22,369 |
| [Tie BBH](adaptive-archive-search-tie-bbh-v1.json) | 2,135 / 11,386 | 2,103 / 8,372 | 2,204 / 13,130 | 2,159 / 11,170 | 1,944 to 2,126 |
| [Tie LMentry](adaptive-archive-search-tie-lmentry-v1.json) | 979 / 6,676 | 948 / 4,022 | 1,028 / 7,195 | 1,011 / 6,506 | 919 to 919 |
| [Additional MMLU](adaptive-archive-search-additional-mmlu-v1.json) | 7,395 / 5,243 | 7,395 / 7,023 | 7,384 / 7,257 | 7,404 / 5,018 | 7,393 to 7,399 |

The first four result columns show final held-out passes and paid lookups. The last column bounds the affordable GEPA score in passes. The adaptive rule missed the gate in all seven cohorts. Across 2,048 episodes, it recorded 53,150 passes in 62,599 lookups, saving 14,332 lookups and losing 282 passes against the earlier router. It scored 470 more passes than fitted fixed and spent 673 more lookups. Bounded LMentry accounted for 410 of those additional passes, with a paired 95% range of +337 to +479 and 1,749 more lookups.

The subject-tuned simple controls scored higher and spent fewer lookups on six cohorts. Bounded LMentry was the exception at +20 adaptive passes, with a paired range of −49 to +86. Adaptive search exceeded the published subject-tuned GEPA upper bound on bounded LMentry, tie BBH and tie LMentry. The earlier router still scored higher on all three. The first qualification reply alone did not recover its advantage.

Case resampling holds the selected comparator schedules fixed. The fitted choices used separate tasks. The transfer cohorts had already been used to compare earlier routing policies, and this follow-up uses frozen candidate grades. Fresh proposals and live optimization quality remain unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview the seal for another cohort. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.adaptive_archive_search --fit NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.adaptive_archive_search \
  --fitted NEW_FIT.json --cohort tie-LMentry \
  --execute 6b7d8adfc94cc6705f4e038a438978f83edec21493e03b13a7b11450b9bdf7d4 \
  --out NEW_REPORT.json
```

Two discovery fits and two isolated replays per cohort matched byte for byte with DNS and outbound sockets blocked. A direct replay of the fitted discovery choices verified every cohort's score and cost through paid callbacks. Fourteen targeted tests passed. Storage Guard measured 10.1 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_adaptive_archive_search.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
