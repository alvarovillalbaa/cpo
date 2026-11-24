# Test a different schedule in one CPO cycle

Requiring every discovery cohort to match the bounded opening's score left a single fixed episode table. It chose bounded opening in all three cycles. Earlier hindsight replay showed that changing schedules between cycles can improve the archived trade-off. That replay selected from holdout results. This study fits one preselected cycle's schedule using discovery tasks and paid training evidence. [Score floor experiment](settled-episode-cohort-guard.md) · [Archived schedule frontier](language-roster-budget-frontier.md)

The fitter starts from either the bounded opening or the packaged two-probe policy. It can replace the schedule in one cycle with any existing menu action for each opening pass count. The changed cycle is the same for all three pass counts. The other two cycles use the anchor schedule. Two fits compare the lookup caps alone and the lookup caps with a baseline score floor in each discovery cohort. Both maximize discovery passes and break ties by realized cost.

The runner charges the opening probe until all remaining grade outcomes choose the same three-cycle path. Each cycle starts with the incumbent chosen by the previous qualification decision. Training, validation, qualification, and final holdout preserve the original disjoint case assignments. The fitter reproduces both anchor scores on the discovery set. The chosen tables are then fixed for all seven archived target cohorts. The verifier compares native split-safe GEPA and simple controls at each candidate's realized lookup budget. [Benchmark](../benchmarks/settled_episode_cycle_override.py)

## Discovery

The expanded menu contains 118,094 distinct tables. Lookup caps admit 10,862. The score floors still admit only the unchanged bounded opening. The budget-only fit changes cycle two after either one or two training passes.

| Opening passes | Cycles one and three | Cycle two |
| ---: | --- | --- |
| 0 | Bounded opening | Bounded opening |
| 1 | Uniform with eight challengers, cap 18 | Halving with eight challengers, cap 9 |
| 2 | Halving with four challengers, cap 6 | Halving with four challengers, cap 12 |

The override scores 84,076 discovery passes on 65,528 lookups. The packaged policy scores 84,046 on 64,938. Both fit the original per-cohort caps. The selected paths differ for all three pass counts, so the override still buys both probes on every episode.

## Archived transfer

The GEPA column shows the split-safe, subject-tuned upper bound at the override's realized lookup cost. The receipt includes the lower bound and its replayed witness where the two bounds differ.

| Cohort | Packaged passes / lookups | Override passes / lookups | GEPA upper at override cost |
| --- | ---: | ---: | ---: |
| Bounded BBH | 6,338 / 12,340 | 6,322 / 12,075 | 6,350 |
| Bounded LMentry | 6,390 / 15,146 | 6,348 / 15,171 | 5,931 |
| Bounded MMLU | 7,715 / 5,956 | 7,704 / 6,256 | 7,717 |
| Four-case MMLU | 22,366 / 10,522 | 22,366 / 10,315 | 22,369 |
| Tie BBH | 2,138 / 12,520 | 2,154 / 12,083 | 2,126 |
| Tie LMentry | 1,004 / 6,863 | 997 / 6,729 | 919 |
| Additional MMLU | 7,397 / 6,211 | 7,399 / 6,334 | 7,399 |
| **Pooled** | **53,348 / 69,558** | **53,290 / 68,963** | — |

The override saves 595 lookups and loses 58 passes across 2,048 archived episodes. Bounded LMentry accounts for 42 lost passes, with a paired 95% range of 15–69 lost passes and 25 additional lookups. Tie BBH gains 16 passes and saves 437 lookups, with a paired range of −2 to +33 passes. The ranges resample cases within enrolled subjects. The pooled counts describe the archived mix, which can repeat subjects across cohorts.

The packaged policy remains in use. The middle-cycle override transfers a cost reduction and gives up much of the LMentry gain. Fresh live performance remains unverified. [Replay receipt](settled-episode-cycle-override-v1.json)

## Reproduce offline

Use the pinned GEPA 0.1.4 benchmark environment and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.settled_episode_cycle_override --out /tmp/cpo-cycle-override.json
```

Two offline runs produced identical receipts with sockets and DNS blocked. All 63 targeted tests passed, including exhaustive pricing against the executed probe and a check that a later cycle uses the actual qualified incumbent. Storage Guard measured 9.6 GiB free. The disposable source export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception and were removed after verification. No provider requests were made. [Tests](../tests/unit/test_settled_episode_cycle_override.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
