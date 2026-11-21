# Compare quoted search on ARC’s recorded parent graph

The archive contains ten Gemini 3 Flash architectures scored on 80 ARC problems. The replay uses the five starts that have recorded children. Each of 40 seeded splits assigns 18 training, eight validation, six admission, and 48 held-out problems. All arms receive up to two supplied children in the same order. Later proposals follow the remaining recorded children of the selected parent. A separate admission check runs before held-out scoring. [Bundled archive](../benchmarks/data/gepa-recorded-math-v1.json) · [Source license](../benchmarks/data/LICENSE.gepa-artifact)

The search ceilings are 32 and 60 times the maximum recorded evaluation charge, with a limit of 64 evaluation reads per search. A later proposal has a modeled price of one or four times the maximum charge. Search and admission reads use their recorded charges. The benchmark repeats each comparison with every arm allowed to stop when supplied openings and recorded children of tracked parents are exhausted. This stop preserved every nominee, admission decision, held-out outcome, and count of retrieved children at all four price points. [Replayer](../benchmarks/recorded_arc_lineage_quotes.py) · [Sealed results](recorded-arc-lineage-quotes-results-v1.json)

## Results at the wider ceiling and four-quote proposal price

| Arm with archive stopping | Held-out passes / 9,600 | Search and admission reads | Recorded evaluation cost | Modeled proposal cost |
| --- | ---: | ---: | ---: | ---: |
| CPO shared budget | 6,662 | 3,726 | $434.20 | $86.08 |
| GEPA 0.1.4 sequential | 6,657 | 4,774 | $548.43 | $103.59 |
| GEPA 0.1.4 batched | 6,523 | 4,903 | $561.21 | $96.29 |
| CPO supplied proposals only | 6,368 | 2,922 | $340.78 | $0.00 |

CPO’s shared budget reduced recorded evaluation cost by 20.8% against sequential GEPA and 22.6% against batched GEPA. Including modeled proposal costs, the savings were 20.2% and 20.9%. The paired held-out gain was five over sequential GEPA, with a 95% case-block bootstrap range of −3 to +13. The gain over batched GEPA was 139, with a range of +110 to +171. At the tighter ceiling and same proposal price, CPO gained 308 passes over batched GEPA and cost $5.69 more after adding modeled proposal charges.

The same 80 problems recur across splits and starts, and the original architecture search may have used them. The resampling ranges describe this archive. Fresh proposal quality, realized proposal costs, and independent generalization remain unverified.

## Reproduce offline

From the repository root, use Python 3.12 with the GEPA 0.1.4 wheel pinned in [the benchmark requirements](../requirements-benchmark.txt). The preview prints the plan seal. The execution verifies that seal and requires a fresh output path. The reference replay ran with DNS and outbound sockets blocked.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_lineage_quotes
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_lineage_quotes \
  --execute 5b21be8fae0716d9b44a65f5162ec89d0a3c58ab094e4d71be9628e6512c0ebe \
  --out NEW_REPORT.json
```
