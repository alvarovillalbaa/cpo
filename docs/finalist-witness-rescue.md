# Reuse a stalled narrow search to test a second witness

The routed backup scored 30 fewer passes than sequential GEPA on the later MMLU model splits. We reproduced the sequential GEPA and routed CPO traces for all 16 panels. Sequential GEPA scored higher in 103 of 512 paired episodes. Its final prompt was absent from CPO's fresh and archive qualification nominations in 66 of those episodes, accounting for 133 of the 210 gross pass deficit. The final GEPA prompt is used only for this retrospective diagnosis. [Prior study](finalist-screen-budget.md) · [Per-panel loss audit](finalist-witness-rescue-results-v1.json)

## Continuation rule

The candidate starts from the ordinary deferred first-gain search. If that search finds no validation gain, the rescue may read the incumbent through its second miss. It reuses all paid replies and buys at most one new witness probe per alternative, preferring the second miss. A probe must leave enough capacity to finish measuring the incumbent and the tested alternative. The top two eligible witnesses may attempt a strict gain certificate. A shortlist rank uses the smoothed fraction of observed passes, with proposal order resolving ties. The narrow search's already rejected finalist is excluded. Every nominee still needs the original independent qualification, and the recency archive and cap of 52 remain in force. [Replay runner](../benchmarks/finalist_witness_rescue.py)

The late arms retain the two-miss route and apply the rescue only in narrow searches after cycle one. They distinguish an opening that found no witness from one whose finalist failed validation. The two restricted arms run after an empty opening. One stops screening at the first new witness, and the other stops at the first witness or after two new probes. The narrow-with-rescue arm starts every fresh search with the narrow opening and permits rescue in all four cycles.

## Results

Each cell shows holdout passes / distinct paid search and qualification lookups.

| Policy | BBH and LMentry | MMLU pilot | MMLU model transfer |
| --- | ---: | ---: | ---: |
| Routed backup | 3,419 / 50,448 | 22,391 / 35,895 | 12,223 / 54,166 |
| Rescue after empty opening | 3,435 / 54,173 | 22,416 / 46,587 | 12,236 / 67,697 |
| Rescue after validation rejection | 3,443 / 53,198 | 22,392 / 36,439 | 12,223 / 56,740 |
| Rescue after either stall | 3,459 / 56,894 | 22,417 / 47,130 | 12,233 / 70,175 |
| Narrow with rescue every cycle | 3,447 / 54,578 | 22,426 / 49,989 | 12,208 / 75,527 |
| Empty opening, stop at first witness | 3,435 / 53,580 | 22,416 / 45,710 | 12,230 / 65,950 |
| Empty opening, at most two probes | 3,424 / 51,605 | 22,406 / 39,490 | 12,226 / 58,744 |
| Batched GEPA, cap 52 | 3,396 / 47,537 | 22,352 / 38,990 | 12,181 / 57,817 |
| Sequential GEPA, cap 52 | 3,457 / 65,252 | 22,361 / 56,504 | 12,253 / 83,250 |

Rescue after an empty opening recovered **13 of the 30 missing passes** on the later model splits and cost 13,531 lookups above the routed backup. It found 139 validation nominees across 692 rescue attempts, with 42 gross holdout passes gained and 29 lost. Restricting the rescue to two probes cut the additional lookup cost to 4,578 and retained three of the 13 passes. It spent 927 more lookups than batched GEPA and finished 27 passes behind sequential GEPA. On BBH and LMentry, starting rescue after either stall gained two passes and saved 8,358 lookups against sequential GEPA, while costing 9,357 more lookups than batched GEPA.

The added witness can improve coverage, with uneven returns from a separate round of probing. None of the rescue arms matches the strongest holdout score on the later model splits. This is a retrospective selection study using archived outcomes. Fresh prompt generation and provider charges remain unverified. [Complete results](finalist-witness-rescue-results-v1.json)

The follow-up allocates one opening probe per challenger across the two misses observed by the route. It also tests whether a third incumbent reply can fund the wider race selectively. [Split opening witnesses](routed-witness-split.md)

## Reproduce

Use GEPA 0.1.4. Preview each phase for its seal. The other phases are `bbh-lmentry` and `mmlu`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.finalist_witness_rescue --phase model-transfer
PYTHONHASHSEED=0 python -B -m benchmarks.finalist_witness_rescue \
  --phase model-transfer --execute 1449826bf2158c66e13d33745ab168ce7319665186729502df6c35236de88134 \
  --out NEW_REPORT.json
```

Two offline source-export replays per cohort matched byte for byte with sockets and DNS blocked. The 40 routed backup trace hashes and 16 sequential GEPA trace hashes reproduced. Three focused tests passed, including 4,096 binary matrices at each of two budgets. They check strict gain, critical-case preservation, lookup accounting, and a rescue probe limit. The CLI rejected an incorrect seal. Storage Guard measured 15.7 GiB free. The 12.6 MB scratch overlay was removed under the standing LAB exception. [Focused tests](../tests/unit/test_finalist_witness_rescue.py)
