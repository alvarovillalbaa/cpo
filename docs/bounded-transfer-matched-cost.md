# Reuse recorded evidence in the CPO and GEPA transfer

The 32-panel transfer counted repeat evaluations again when they appeared in a different cycle. This follow-up checks the same decision traces after applying identical reuse rules to deferred first-gain CPO, two-read CPO, and sequential and batched GEPA 0.1.4. [Original transfer](bounded-discovery-transfer.md)

Each arm starts each episode with an empty search cache. The first recorded outcome for a prompt and case pair is charged. Identical later outcomes for that pair are reused within the episode. The runner checks every cycle's ordered search journal against its sealed hash and rejects contradictory repeats. It also checks the full original trace for each panel against the archived transfer report.

Fresh qualification is charged through the first reply that makes promotion or rejection certain. The replay applies the same paired bound and seeded reply order to every arm, preserves the archived qualification decision, and charges any preceding archive evaluations. The original logical search budgets, prompt rosters, and qualification cohorts still drive every decision.

This accounting estimates the lookup savings available when identical requests can reuse deterministic evidence. A policy that spends the savings on extra proposals would need a separate comparison. The replay continues to use recorded outcomes and repeated holdout cases across seeds. [Qualification bounds](paired-qualification.md) · [Replay runner](../benchmarks/bounded_transfer_matched_cost.py)

## Results

Across 32 panels, every arm reproduced its complete original selection and qualification trace.

| Method | Holdout passes | Original lookups | Lookups with reuse and early stopping | Both GEPA gates with reuse |
| --- | ---: | ---: | ---: | ---: |
| Deferred first-gain | 21,023 | 110,318 | 101,034 | 10 / 32 |
| Frozen two-read | 20,963 | 118,267 | 107,423 | 4 / 32 |
| Sequential GEPA | 20,865 | 177,292 | 140,003 | — |
| Batched GEPA | 20,427 | 131,384 | 103,045 | — |

Deferred first-gain's lead over batched GEPA narrowed from 16.0% to **1.95% fewer lookups** with identical reuse rules. Deferred first-gain finished 596 passes ahead of batched GEPA and 158 ahead of sequential GEPA. It used 27.8% fewer lookups than sequential GEPA. Its aggregate accuracy and lookup leads against each control survived omitting any one subject and both model panels. Against batched GEPA the smallest remaining leads across those omissions were 382 passes and 726 lookups.

Search reuse removed 26,674 batched GEPA lookups and 6,875 deferred first-gain lookups. Early qualification stopping saved another 1,665 and 2,409 lookups, respectively. The revised costs reduced the number of panels where deferred first-gain met both gates from 15 to 10 and two-read from 14 to four. Two-read still gained 536 passes over batched GEPA and cost 4,378 additional lookups.

Both offline executions of every phase produced byte-identical reports. The lookup savings describe deterministic evidence reuse on existing trajectories. Fresh provider accuracy, latency, and costs remain unmeasured. [Per-panel results and seals](bounded-transfer-matched-cost-results-v1.json)

The public fixed-pool cycle replay meters actual callback reads and matches these archived CPO decisions and deterministic lookup costs. [Fixed-pool cycle](fixed-pool-cycle.md)

A later replay let GEPA spend the saved search lookups within the same paid ceiling. Both GEPA controls gained passes and spent more, and deferred first-gain retained a narrower aggregate accuracy lead. [Paid-cap follow-up](gepa-paid-cap-transfer.md)

## Reproduce

Use pinned GEPA 0.1.4. Preview a phase to get its seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.bounded_transfer_matched_cost --phase mmlu
```

The other phases are `bbh-lmentry` and `bbh-lmentry-stress`.
