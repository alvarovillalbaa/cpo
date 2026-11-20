# Bound opening-only CPO savings using recorded Sol charges

**Historical baseline.** These bounds price the original GEPA traces, which used overlapping list-loader IDs in the evaluation cache. The corrected frontier uses stable case IDs for separate splits. [Cache correction and rerun](grounded-gepa-cache-controls.md)

The opening-only comparison originally used one historical token charge for each evaluated prompt and case. This audit replayed all 240 paths and measured the savings over the full range of eligible archived charges for those same cells. Across 852 cells, 25 had different charges. All retained repeats for a cell had identical exact-pass and field grades. The archive therefore supports a cost sensitivity analysis with the selected prompts and grades held fixed. [Original comparison](grounded-staged-recorded-opening.md) · [Result and verification](grounded-opening-price-bounds-results-v1.json)

| Compared with | Minimum opening-only savings | Maximum opening-only savings |
| --- | ---: | ---: |
| Staged CPO | $5.546064 | $5.546064 |
| Sequential GEPA | $20.664288 | $21.226848 |
| Batched GEPA | $24.820824 | $25.743504 |

The bounds use the same charge for a prompt and case in every arm and both seed sets. The original attributed costs of the shared opening and later archived proposals stay fixed. For each cell the replay multiplies its observed low and high charges by the difference in paid uses. This cancels equally used replies and gives exact bounds under the stated charge assignments. Opening-only remained at least 10% cheaper than both GEPA controls on each task. Staged CPO tied opening-only on ticket cost and its entire excess cost came from warehouse and outage.

Two offline runs produced identical reports. All 240 original paths reproduced, and 343 exact enumeration checks confirmed the signed bound calculation. This result describes the recorded proposal graph, cases, and charge ranges. Quality on the original independent holdout is still incomplete for GEPA. Fresh model quality and billing remain open.

The same-cost follow-up tuned both GEPA modes over all 53 search caps. Its cheapest matching point narrowed the opening-only advantage to 15.7% at the primary recorded prices. [Tuned GEPA comparison](grounded-opening-cost-frontier.md)
