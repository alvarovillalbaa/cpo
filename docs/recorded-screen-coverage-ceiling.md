# Measure which archived prompt improvements reach qualification

The one-failure reserve missed the transfer gate, and the complete-panel reserve had an inconclusive lead over the best affordable GEPA setting. This audit replays the three cap-13 policies on the same 960 trials and verifies every panel’s original decision trace, cost, and score. It then measures where the best archived alternatives drop out. [Transfer result](recorded-one-failure-screen-transfer.md) · [Audit runner](../benchmarks/recorded_screen_coverage_ceiling.py)

For each trial the audit starts from the actual deployment and can always retain it or restore the start. It finds the best held-out score in increasingly restricted sets of alternatives. The funded set subtracts the original incumbent reads and each paid first-miss probe from cap 13. A screened candidate must be able to prove a strict gain using its probe grade and the most favorable unread replies within the remaining cap. Every qualified alternative must have a strict gain on the separate qualification panel. All these ceilings use archived grades with hindsight.

| Alternatives available | Complete panel | One failed reply | Minimum |
| --- | ---: | ---: | ---: |
| Whole roster | 2,564 / 753 | 2,587 / 751 | 2,573 / 749 |
| Strict qualification gain | 620 / 173 | 643 / 170 | 629 / 166 |
| Strict gain on validation and qualification | 169 / 46 | 192 / 43 | 178 / 39 |
| Both gains and a paid screening probe | 49 / 15 | 108 / 22 | 109 / 23 |
| Both gains and an affordable certificate after the paid probes | 49 / 15 | 108 / 22 | 63 / 10 |
| Original nominee or retained start | 37 / 10 | 18 / 5 | 4 / 1 |

Each cell gives extra passes and the number of trials with a possible improvement. The whole-roster ceilings describe the raw choices in the archive. On the complete-panel route, the two strict gates reduced that headroom from 2,564 passes to 169. The paid probes left 49 passes reachable, including 37 that a perfect veto of the original promotion could recover by retaining the start. For the minimum reserve, the larger screen left 109 passes in the probed set and 63 fundable after the probes. The one-failure reserve left 108 fundable passes from screened alternatives. These numbers bound specific changes to selection on the same archived prompts. They leave open whether different qualification evidence or fresh proposals improve performance. [Per-panel ceilings and reproduced totals](recorded-screen-coverage-ceiling-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_screen_coverage_ceiling
python -B -m benchmarks.recorded_screen_coverage_ceiling \
  --execute 943fa57c0f771ec11014981e5a124555843815b56a7ab6e2237db71e68e1f0d2 \
  --out NEW_REPORT.json
```

Two clean-export replays with DNS and sockets blocked matched byte for byte at SHA-256 `ba6b3abacbb68323bbf7c78cf2f4d00cf60043bb70682633ec0f95df6820e0c0`. All 38 targeted tests passed. A separate audit enumerated post-screen read sets for all 2,880 paths. The CLI rejected the predecessor seal. Storage Guard measured 3.1 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Regression tests](../tests/unit/test_recorded_screen_coverage_ceiling.py)
