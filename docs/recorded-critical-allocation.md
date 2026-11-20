# Test whether reallocating cases covers critical outage conditions

The earlier replay found three matched critical losses against GEPA at search cap 36. All three policy conditions were missing from the critical validation and qualification rows on their respective splits. This follow-up checks whether training contained a case that could supply the missing evidence and tests reassigning cases across all three roles. [Prior replay](recorded-coverage-confirmation.md)

## Protocol

The experiment keeps all 220 three-case holdouts per task. Each split reuses the same nine development cases, candidate order, lookup caps, role sizes of three training, four validation, and two qualification cases, and original critical-case count in each role. The allocation sees only declared categories and critical labels for those nine cases.

- **Original** reuses the seeded assignment.
- **Matched moves** draws a seeded assignment with the same number of cases changing roles as risk coverage.
- **Risk coverage** maximizes the number of distinct critical policy strata across validation and qualification. Ties favor more strata on qualification, then validation, then fewer role changes.

CPO and both official GEPA 0.1.4 modes share each layout. The parent runner retains the same scoring, budget accounting, and independent qualification. After selection the audit checks whether the condition for each critical loss was represented anywhere in the nine development cases. [Runner](../benchmarks/recorded_critical_allocation.py)

## Results

On outage, the sum of distinct critical strata represented across both evaluation roles over 220 splits rose from 562 in the original allocation to 571 with matched moves and 618 with risk coverage. Both alternate allocations changed 148 case roles in total.

| Outage allocation | Cap 24 CPO passes / lookups | Cap 36 CPO passes / lookups |
| --- | ---: | ---: |
| Original | 457 / 4,166 | 485 / 5,253 |
| Matched moves | 458 / 4,166 | 496 / 5,287 |
| Risk coverage | 461 / 4,278 | 495 / 5,383 |

At cap 36, risk coverage cost 96 more lookups than matched moves and passed one fewer case. The three critical loss observations against the original GEPA controls occurred in splits where the corresponding conditions were absent from all nine available development cases. With risk coverage and GEPA rerun on the same panels, there was still one matched critical loss against batched GEPA and two against sequential GEPA. Each was also missing from the entire development split. The limited original provider holdout retained four observed critical losses against each control. At cap 24, risk coverage retained zero matched critical losses against both GEPA controls and used more lookups than either.

Ticket outcomes and cost were identical under all layouts. Warehouse retained 605 passes out of 660 under every layout. Risk coverage raised CPO's warehouse lookup count by 279 and 370 against the original allocation at the two caps. The evidence supports leaving risk allocation optional. Repairing the identified outage evidence gap requires cases from the missing conditions. [Totals, matched comparisons and loss attribution](recorded-critical-allocation-results-v1.json)

## Reproduce

Use the intact GEPA research archive, its original Open Evals source study, and GEPA 0.1.4.

```sh
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_critical_allocation
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_critical_allocation \
  --execute b77951895a5e5c056fc3b67829baa6e8b0f4d89a560c27349fc53a1f1a90462d \
  --out NEW_REPORT.json
```

Both exact-source replays matched byte for byte with sockets and DNS blocked. Each reproduced the original arm traces and totals on all three tasks at both caps. Eleven focused tests passed. The CLI rejected a wrong seal and an existing output path. Storage Guard measured 17.6 GiB free. The 18.8 MB temporary source and wheel overlay was removed under the standing LAB exception. [Verification receipt](recorded-critical-allocation-verification-v1.json)
