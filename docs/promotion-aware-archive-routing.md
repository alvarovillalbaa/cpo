# Choose a search screen before and after the first promotion

The three-cycle benchmark found that a routing policy's advantage can grow or shrink as deployments carry forward. This replay fits a policy that can change its search screen once, after the first verified promotion. It uses the same paid screens, disjoint case roles, three cycles, and exact independent qualification as the continuous benchmark. Every candidate comes from the existing frozen roster. [Previous benchmark](continuous-archive-routing.md) · [Replay runner](../benchmarks/promotion_aware_archive_routing.py)

The fit compares all 16 pairs of the four existing CPO policies. It uses the first policy until a challenger is deployed and the second afterward. The initial 95% cap left no feasible fixed control. Before running any transfer cohort, the fit moved to each discovery cohort's full static lookup budget and retained a feasibility count at the stricter cap. The fit maximizes pooled held-out passes within the separate budgets and takes the lower-cost table on a score tie. The fixed control chooses one policy for the whole episode under the same budgets. The selected pair and fixed control are frozen on discovery before transfer. [Fit and feasible schedules](promotion-aware-archive-routing-fit-v1.json)

The target replay includes all seven previous transfer cohorts and verifies all four original CPO trajectories before comparing the fitted choices. The GEPA comparison reuses exact three-cycle native anchors. It takes the best published setting whose realized cost fits the new budget as a lower bound. A published ceiling at a larger budget supplies an upper bound. The runner directly reproduces the chosen affordable settings and their paired holdout grades. Equal bounds identify the exact native score at the fitted policy's budget. The gate requires the switch to stay within fitted fixed's cost, beat fitted fixed and the exact best affordable common GEPA score at positive paired lower endpoints, and beat the subject-tuned upper bound.

## What the fit selected

All 134 discovery panels fit the three-cycle case layout. At 95% of static spend per cohort, no fixed or switching pair was feasible. At the full caps, the fixed choice used the conservative cohort-nonloss screen for all three cycles. The primary used that screen until a verified promotion and then switched to static. On discovery the primary gained four passes and used 1,566 more lookups than fitted fixed.

Before inspecting the transfer scores, a secondary fit used the fixed policy's actual per-cohort costs as tighter caps. The only feasible pair with different actions used the cohort-budgeted screen before promotion and the cohort-nonloss screen afterward. In discovery it spent 12,915 fewer lookups and scored 108 fewer passes than fitted fixed.

## Three-cycle transfer

Each entry gives final held-out passes / paid lookups. The last column gives the subject-tuned GEPA score bounds at the secondary switch's budget. The primary's paired comparisons with directly reproduced native settings are in the cohort receipts.

| Cohort | Fitted fixed | Primary switch | Fixed-budget switch | GEPA bounds at fixed-budget switch cost |
| --- | ---: | ---: | ---: | ---: |
| [Bounded BBH](promotion-aware-archive-routing-bounded-bbh-v1.json) | 6,365 / 17,702 | 6,365 / 17,964 | 6,377 / 14,505 | 6,350–6,361 |
| [Bounded LMentry](promotion-aware-archive-routing-bounded-lmentry-v1.json) | 6,512 / 18,728 | 6,512 / 19,017 | 6,341 / 16,795 | 5,931–6,070 |
| [Bounded MMLU](promotion-aware-archive-routing-bounded-mmlu-v1.json) | 7,722 / 8,366 | 7,722 / 8,419 | 7,727 / 7,648 | 7,717 |
| [Four-case MMLU](promotion-aware-archive-routing-four-case-mmlu-v1.json) | 22,399 / 13,131 | 22,399 / 13,182 | 22,381 / 12,140 | 22,369 |
| [Tie BBH](promotion-aware-archive-routing-tie-bbh-v1.json) | 2,156 / 14,377 | 2,156 / 14,448 | 2,199 / 13,352 | 2,126–2,136 |
| [Tie LMentry](promotion-aware-archive-routing-tie-lmentry-v1.json) | 976 / 7,452 | 988 / 7,496 | 1,020 / 7,400 | 920 |
| [Additional MMLU](promotion-aware-archive-routing-additional-mmlu-v1.json) | 7,395 / 7,963 | 7,397 / 7,985 | 7,386 / 7,285 | 7,399 |

The primary missed the gate in all seven cohorts. It gained 14 passes and spent 792 more lookups than fitted fixed in aggregate. The paired 95% range on tie LMentry was +4 to +19 passes versus fitted fixed with 44 more lookups there.

The fixed-budget switch saved 8,594 lookups and lost 94 passes overall versus fitted fixed. Its gains versus fitted fixed on tie BBH and tie LMentry were +43 and +44 passes, with paired ranges of +3 to +84 and +21 to +66. The previously published cohort-budgeted policy still scored higher at lower cost on both tie cohorts. On bounded LMentry the fixed-budget switch lost 171 passes to fitted fixed, with a range of −208 to −136, and scored 271 passes above the native upper bound at its lookup budget. These retrospective results do not establish a broadly better promotion-conditioned policy. Fresh proposal generation remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Preview the selected cohort with the fitted receipt to get its seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.promotion_aware_archive_routing --fit NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.promotion_aware_archive_routing \
  --fitted NEW_FIT.json --cohort tie-LMentry \
  --execute 4b351410e2b77db0d622d91c02f2db17c1dcc560e1b697a56b406840bdef3847 \
  --out NEW_REPORT.json
```

Two discovery fits and two source replays per cohort matched byte for byte with DNS and outbound sockets blocked. The secondary analysis reproduced all earlier fitted action choices, CPO trajectories, and primary native comparisons. Thirty targeted tests passed, including the first-promotion transition and budget-bound checks. Storage Guard measured 10.4 GiB free at preflight. The source export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. [Focused tests](../tests/unit/test_promotion_aware_archive_routing.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
