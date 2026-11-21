# Prepare the Sol outage holdout offline

The replay recovered three distinct outage finalists across the two wider budgets and two matched GEPA controls. The coverage packet has 36 slots for the two prompts absent from the original provider holdout. The matched packet has 54 slots to score all three prompts on the same 18 cases in one model configuration. The two scopes use the same sealed packet. [Sol transfer](recorded-sol-empty-slots.md) · [Capture receipt](recorded-sol-provider-holdout-receipt-v1.json)

| Scope | Requests | Reservation at the original plan rates |
| --- | ---: | ---: |
| Missing historical coverage | 36 | $4.395552 |
| Fresh matched comparison | 54 | $6.549048 |

The local SDK capture reproduced all 90 historical outage reservation amounts from the serialized body lengths. It records hashes of the newly reconstructed bodies. The archive contains an alias and reservation records. A shared provider snapshot for historical and future requests has not been established. A complete result for the coverage scope reports those outcomes separately. The matched scope supports the four directed prompt comparisons and the four replay-weighted groups. Reused prompts share one outcome for each original case.

## Capture and score

With the original research archive and installed runtime, use the offline capture subcommand. The preview emits the current plan seal. The second invocation uses a local stub and writes request fingerprints to a new file.

```sh
node benchmarks/recorded_sol_holdout.mjs capture \
  --design PAIR_DESIGN.json --archive ORIGINAL_OPEN_EVALS_STUDY \
  --source-plan REWRITE_FIRST_PLAN.json --runtime ORIGINAL_OPENAI_RUNTIME.mjs \
  --execute 137ac952a391a529f3bea709ae1a97c1dac66841df29bee8a6916be2cff1529b \
  --out NEW_PACKET.json
```

Use `score` with a journal following the [holdout journal format](recorded-holdout-score.md). For `--scope missing`, filter the packet’s slots by the `missing` attribute and number the remaining requests from one. For `--scope matched`, use the full order. The scorer checks reservations against the packet, uses the hash-verified original grader, and emits comparisons after a complete matched journal.

```sh
node benchmarks/recorded_sol_holdout.mjs score \
  --packet NEW_PACKET.json --scope matched --cases ORIGINAL_OUTAGE_STRICT_PLAN.json \
  --grader ORIGINAL_IMPROVEMENT_PLAN.mjs --wire PANEL_WIRE.jsonl --out NEW_SCORE.json
```

The capture and scorer were exercised offline with all 54 reconstructed bodies and fixture replies. The packet remains unexecuted. No provider outcomes or spending were observed for either scope.
