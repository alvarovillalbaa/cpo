# Route the next CPO cycle from the previous qualification result

The [one-cycle override](settled-episode-cycle-override.md) improved discovery and lost passes on transfer. This study replaces the fixed cycle position with the immediately preceding outcome. It tests four signals that are already available from a completed cycle. The incumbent can pass its qualification precheck, validation can return no finalist, qualification can reject the finalist, or qualification can promote it. A selected signal may activate in either follow-up cycle. Each cycle carries forward the actual qualified incumbent.

Earlier [promotion-aware routing](promotion-aware-archive-routing.md) switched permanently after the first promotion. Here the previous outcome can change again. The first cycle follows the anchor. The two paid opening grades can select a replacement action for each state. One fitted trigger applies across all states, and a state needs observations from at least three discovery subjects before the fitter can assign it a replacement.

The control can replace both follow-up searches regardless of the preceding outcome. Both fits use the same schedule menu and the packaged policy's realized discovery lookups as each cohort's cap. The fit maximizes pooled passes and takes the cheaper table on a tie. The runner replays both anchors and applies each frozen fit to the original task-disjoint target cohorts. It charges only the opening prefix needed to settle the actual rule. Reading the previous cycle's outcome adds no requests. [Benchmark](../benchmarks/settled_episode_qualification_feedback.py)

## Discovery

The unconditional fit keeps the packaged schedule. The conditioned fit selects a switch only after qualification rejects the previous finalist. This trigger has discovery support from 21, 30, and 28 subjects in the zero-, one-, and two-pass opening states, respectively.

| Opening passes | Anchor | Next cycle after a rejected finalist |
| ---: | --- | --- |
| 0 | Bounded opening | Halving with eight challengers, cap 14 |
| 1 | Uniform with eight challengers, cap 18 | Bounded opening |
| 2 | Halving with four challengers, cap 6 | Retain the incumbent for one cycle |

When the triggering outcome is absent, the next cycle uses the anchor again. The conditioned fit scores 84,078 passes on 64,237 lookups, gaining 32 passes and saving 701 lookups versus the packaged policy in discovery.

## Archived transfer

The GEPA column shows the split-safe, subject-tuned upper bound at the conditioned fit's realized lookup cost. The receipt includes directly reproduced feasible settings and the score bounds at that cost.

| Cohort | Packaged and unconditional passes / lookups | Conditioned passes / lookups | GEPA upper at conditioned cost |
| --- | ---: | ---: | ---: |
| Bounded BBH | 6,338 / 12,340 | 6,326 / 12,173 | 6,350 |
| Bounded LMentry | 6,390 / 15,146 | 6,403 / 14,824 | 5,931 |
| Bounded MMLU | 7,715 / 5,956 | 7,715 / 5,873 | 7,717 |
| Four-case MMLU | 22,366 / 10,522 | 22,366 / 10,530 | 22,369 |
| Tie BBH | 2,138 / 12,520 | 2,140 / 12,196 | 2,126 |
| Tie LMentry | 1,004 / 6,863 | 997 / 6,820 | 919 |
| Additional MMLU | 7,397 / 6,211 | 7,398 / 6,166 | 7,399 |
| **Pooled** | **53,348 / 69,558** | **53,345 / 68,582** | — |

The trigger changes 735 follow-up cycles across 2,048 archived episodes. It uses 976 fewer lookups and scores three fewer passes than the packaged policy. Bounded LMentry gains 13 passes and saves 322 lookups, with a paired 95% range of −5 to +31 passes. The corresponding ranges cross zero in all five cohorts with nonzero score changes. The ranges resample cases within enrolled subjects. The pooled totals describe the archived mix, which can repeat subjects across cohorts.

The conditioned policy preserves most of the packaged policy's archived score at lower lookup cost. The evidence supports keeping it as a candidate alongside the packaged policy. It exceeds the subject-tuned GEPA budget bound in the same three cohorts. Fresh live performance remains unverified. [Replay receipt](settled-episode-qualification-feedback-v1.json)

## Reproduce offline

Use the pinned GEPA 0.1.4 benchmark environment and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.settled_episode_qualification_feedback --out /tmp/cpo-feedback.json
```

Two runs produced identical receipts with sockets and DNS blocked. All 73 targeted tests passed, including checks for observed outcome classification, immediate-cycle feedback, and probe pricing. Storage Guard measured 9.5 GiB free. The disposable source export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception and were removed after verification. No provider requests were made. [Tests](../tests/unit/test_settled_episode_qualification_feedback.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
