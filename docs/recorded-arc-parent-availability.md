# Filter ARC parents by proposal availability

The baseline stops only when every tracked parent has exhausted its recorded children. This comparison gives CPO, sequential GEPA, and two-proposal batched GEPA the same availability predicate once the supplied openings are consumed. The selector computes its Pareto draw over parents with a remaining child. Every admitted candidate stays eligible for final selection. The predicate uses the proposal source’s remaining entries and exposes no case scores or costs. [Baseline protocol](recorded-arc-lineage-quotes.md) · [Replay receipt](recorded-arc-parent-availability-results-v1.json)

| Search ceiling and later proposal price, in evaluation quotes | CPO holdout passes before → after, out of 9,600 | CPO case-block range | CPO recorded evaluation plus modeled proposal costs before → after |
| --- | ---: | ---: | ---: |
| 32, 1 | 6,662 → 6,621 | −59 to −24 | $455.32 → $460.42 |
| 32, 4 | 6,638 → 6,533 | −131 to −78 | $500.52 → $486.77 |
| 60, 1 | 6,662 → 6,665 | −4 to +10 | $455.72 → $505.03 |
| 60, 4 | 6,662 → 6,665 | −4 to +10 | $520.28 → $620.36 |

Filtering eliminated empty later proposal slots for sequential CPO and GEPA. Batched GEPA could still select an eligible parent with only one child left and use an empty second slot. At the wider ceiling and four-quote price, filtering gained seven passes for sequential GEPA and 67 for batched GEPA, with combined costs rising by $131.98 and $111.06. CPO with filtering gained one pass over sequential GEPA with filtering, with a paired range of −7 to +8. It gained 75 over batched GEPA with filtering, with a range of +57 to +94. The default CPO scheduler keeps its original parent draw. The same 80 problems recur across paths, and the availability predicate is specific to a finite source of proposals.

## Reproduce offline

Use Python 3.12 and the pinned GEPA 0.1.4 wheel. The unrestricted arms matched the published ARC exhaustion-aware traces at all four price points. The result counts zero new provider requests. [Benchmark requirements](../requirements-benchmark.txt)

Storage Guard measured 8.5 GiB free. The standing LAB exception covered a bounded 0.1 GiB temporary source export and wheel expansion. The replay blocked DNS and outbound sockets and removed the temporary files after verification.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_lineage_quotes --available-parents
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_lineage_quotes --available-parents \
  --execute dbf425a57b2a39270481e3d4863dc76f7f2e76fef47d7e932d326b1eac52f90f \
  --out NEW_REPORT.json
```
