# Skip training reads when the selected parent has no proposal

For a finite proposal source, pass `proposal_unavailable(index, parent)` to `select_sequential_field_rewrites`. Return true only when the selected parent cannot provide a proposal in that slot. The selector keeps the scheduled parent and counts the slot toward the round limit. It skips the parent’s training minibatch, the proposal quote, and the proposal call. Final selection still includes every admitted candidate. In a source with supplied openings, keep those slots available until their assigned turns have passed. [Selector](../cpo/sequential_field_rewrite.py)

The replay reuses the four budgets, cases, seeds, and ordered proposal queues from the parent-filter comparison. It keeps both GEPA controls with and without parent filtering. CPO’s empty-slot check uses the same queue-availability information as filtering while keeping the seeded parent draw. The original arm’s trace and the filtered arms’ totals and paired results matched the earlier receipts at every point. [Parent-filter protocol](recorded-arc-parent-availability.md) · [Sealed receipt](recorded-arc-skip-empty-slots-results-v1.json)

| Ceiling and later proposal price, in evaluation quotes | Matched held-out passes / 9,600 | Search reads saved | Recorded evaluation cost saved |
| --- | ---: | ---: | ---: |
| 32, 1 | 6,662 | 238 | $25.20 |
| 32, 4 | 6,638 | 192 | $19.42 |
| 60, 1 | 6,662 | 240 | $25.60 |
| 60, 4 | 6,662 | 240 | $25.60 |

Every nominee, admission decision, held-out outcome, and per-path count of retrieved children matched the original CPO policy. At the wider ceiling and four-quote price, CPO’s recorded evaluation cost was $408.60, versus $548.43 for sequential GEPA and $561.21 for batched GEPA. CPO gained five passes over sequential GEPA, with a case-block range of −3 to +13, and 139 over batched GEPA, with a range of +110 to +171. The GEPA arms with the same availability information scored two more and 72 fewer passes than CPO, respectively.

At the tighter ceiling and four-quote price, CPO gained 308 passes over batched GEPA and spent $13.73 less on recorded evaluations plus modeled proposals. The earlier CPO policy cost $5.69 more at that price. Results reuse the same 80 archived problems. Fresh proposals, realized costs, and independent qualification remain unverified.

## Reproduce offline

Use Python 3.12 and the pinned GEPA 0.1.4 wheel from the [source revision for this receipt](https://github.com/alvarovillalbaa/cpo/tree/d35a970a2cc5cff2bb8c4504f2a7d25d09e5a80e). Storage Guard measured 8.5 GiB free. The standing LAB exception covered the bounded 0.1 GiB temporary source export and wheel expansion. The replay blocked DNS and outbound sockets and removed the temporary files after verification. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_lineage_quotes --skip-empty-slots
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_lineage_quotes --skip-empty-slots \
  --execute 20a4b07a83a3c973798c1674e57df25a6c8a09a873faba3252a42fbfc09d0f34 \
  --out NEW_REPORT.json
```

The follow-up also removed empty slots from GEPA’s native samplers and tested a reserve based on available slots. [Matched GEPA controls](recorded-arc-native-empty-slots.md)
