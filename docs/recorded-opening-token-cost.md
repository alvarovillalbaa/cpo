# Measure the opening-pair replay at historical provider cost

The opening-pair replay gave CPO and both official GEPA 0.1.4 controls the same recorded rewrite and repair. A later audit reproduced every route on both sets of 40 splits per task, for 240 trials. It joined each replayed evaluation to the recorded GPT‑6.2 Sol token receipt for that prompt and case. It charges the shared opening reflection to each arm, and charges later model-generated edges using their original reflection receipts. Local rule edits and exhausted slots are counted separately. [Original matched comparison](recorded-replay.md#precomputed-opening-against-field-aware-gepa)

| Second seed set | CPO estimated search cost | Sequential GEPA | Batched GEPA | CPO holdout pass gain vs sequential / batched |
| --- | ---: | ---: | ---: | ---: |
| Ticket | $2.240064 | $2.472456 | $3.027024 | 0 / 0 |
| Warehouse | $5.877192 | $8.632128 | $9.772368 | 0 / 0 |
| Outage | $9.589224 | $16.297488 | $17.890080 | 0 / 2 |
| Total | $17.706480 | $27.402072 | $30.689472 | 0 / 2 |

The pooled savings were **35.4% against sequential GEPA** and **42.3% against batched GEPA** on the second seed set. The first seed set saved 34.2% and 41.4%. The archived outcomes contain zero matched critical losses. The savings stayed positive on each task when the repeated evaluation receipts were repriced within their observed ranges, with the same price for each prompt and case across arms. Ticket routing tied sequential GEPA on passes and saved 9.7% and 9.4% across the two seed sets at the primary historical prices. That misses the original 10% threshold for tied scores on that task.

The follow-up certificate closed the ticket gap on these same recorded trials while preserving every selected prompt. [Opening certificate and cost results](opening-certificate.md)

These figures price retrospective replays using the source archive's cost estimates. The trials reuse observations and supplied proposals. Comparing newly generated candidates, independent live holdouts, and live provider spend still requires a fresh run.

## Verification

The source comparison is sealed as `41a7ab5fa364d117bc9ea4695db7167d1f0c90bd9b8f02f51c71771a3a31c39a`. The historical cost report SHA-256 is `5d72eeab3d44a433fb47cee8d22bc0f6b8f8f68f2110eb5bc09327beaa56fe27`. Two offline runs matched byte for byte. In the original GEPA research workspace, `python -B run_recorded_opening_cost.py --out NEW_REPORT.json` verifies the source archives and loads CPO `42fd9e42802a4b6d898de7039cfcde38655e0de9` with pinned GEPA 0.1.4 and the original prompt contract.
