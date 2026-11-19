# Policy coverage on the promotion panel

On the outage replay, distributing critical cases across more policy conditions raised CPO from 490 to 507 passes for 92 additional calls. On identical diverse panels, CPO passed 76 more cases than sequential GEPA and 75 more than batched GEPA, with fewer calls. It still lost one matched critical pass against sequential GEPA and three against batched GEPA. The outage gate remains unmet. [Replay results](recorded-promotion-strata-results-v1.json)

## Protocol

Every task retains its 220 three-case holdouts and corresponding training cases. The experiment starts from the existing two-critical allocation. It redistributes the same six validation and promotion cases while preserving both panel sizes and both critical-case counts. A seeded control makes the same number of swaps without using the policy categories. CPO and official GEPA 0.1.4 search the same archived proposal graph with their previous settings. [Baseline](recorded-promotion-coverage.md)

The categories come from policy inputs. Outage crosses the duration bands at 30 and 120 minutes with posted or missing evidence. Ticket uses the topic. Warehouse crosses positive or nonpositive stock after reservations and damage with inspection and tier. The allocation maximizes distinct critical categories on promotion, then on validation, then overall category coverage on each panel. Ties retain the original assignments where possible. The sampler never reads expected answers or replies.

## Results

Each cell gives exact holdout passes and charged calls. Each task has 660 holdout observations across repeated uses of its 12 archived cases.

| Task | CPO two-critical | CPO matched swaps | CPO diverse | Sequential GEPA diverse | Batched GEPA diverse |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ticket | 660 / 660 | 660 / 660 | 660 / 660 | 660 / 660 | 660 / 660 |
| Warehouse | 605 / 2,000 | 605 / 1,911 | 605 / 1,808 | 605 / 2,423 | 605 / 2,423 |
| Outage | 490 / 6,253 | 496 / 6,134 | 507 / 6,345 | 431 / 7,270 | 432 / 7,516 |

On outage, summing distinct critical categories per promotion panel gives 382 for two-critical, 395 for matched swaps, and 408 for the diverse policy. The two new allocations each moved 104 cases relative to the baseline. Diverse CPO gained 11 passes on 211 extra calls over the swap control and missed five of its critical passes. Relative to two-critical CPO it missed nine critical passes. The results support targeted coverage as a trade-off. They leave the critical preservation requirement open.

The original provider holdout covers two of seven distinct directed outage pairs against diverse sequential GEPA and two of six against diverse batched GEPA. The deduplicated pass delta across the observed directed pairs is zero in each comparison. The missing pairs and fixed proposal bank limit what this replay says about independent performance.

A follow-up checked a reserved long-outage case against the remaining failure mode. The loss counts persisted under every completion of the missing witness replies. [Reserved outage check](recorded-outage-witness.md)

## Reproduce offline

Use the intact research archive and hash-pinned GEPA 0.1.4. Preview the plan, then use its seal with a fresh path.

```sh
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_promotion_strata \
  --replay FULL_PROMOTION_REPLAY.json
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_promotion_strata \
  --replay FULL_PROMOTION_REPLAY.json --execute PLAN_SHA256 --out NEW_REPORT.json
```

Both network-disabled runs reproduced every original two-critical arm record and returned byte-identical reports. [Runner](../benchmarks/recorded_promotion_strata.py) · [Tests](../tests/test_recorded_promotion_strata.py)
