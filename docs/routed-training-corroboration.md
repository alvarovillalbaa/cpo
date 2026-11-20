# Transfer the training check to archived MMLU model splits

On the AIME replay, increasing the qualification margin did not replace the separate training check. This study transfers the two proofs to the existing 16-panel MMLU confirmation archive. The panels pair eight subjects with Llama 3 8B Instruct and Mistral 7B v0.1. The proof settings come from the math replay. The archived subjects and models had already been used to study routing and qualification. [Math replay](recorded-margin-corroboration.md) · [MMLU source and split provenance](routed-start-model-confirmation.md)

## Protocol

Each episode keeps the original start, four search cycles, 12 validation cases per cycle, eight independent qualification cases per cycle, and final holdout. One five-case training panel is fixed from the episode seed. It excludes every validation and qualification case across the episode and all final holdout cases. Selection prefers the original training pool and fills any shortfall from the remaining unused cases.

The extra proof applies once per episode to a fresh challenger that qualifies to replace the starting prompt and has room for a full ten-lookup training check under the original search cap. All three experimental arms use that same eligibility rule. The archive qualification and later fresh challenges follow the original route. The training check requires a strict gain on its paired cases. Strength only requires a two-pass qualification margin. Strength first extends the original independent qualification proof and falls back to training if it cannot certify the extra gain. [Replay runner](../benchmarks/routed_training_corroboration.py)

The primary arm is training only. The controls are strict routed CPO, retaining the starting prompt, and the two official GEPA modes at 52 paid search lookups. Both GEPA modes retain their original search and qualification policy. The gate requires at least 10% fewer lookups against both and a nonnegative lower endpoint of the joint paired range. The 4,096 draws resample held-out cases within subject, keeping both models and all 32 scheduled episodes paired.

## Results

| Policy | Holdout passes / 26,944 | Paid lookups |
| --- | ---: | ---: |
| Retain start | 17,617 | 0 |
| Strict routed CPO | 17,724 | 49,330 |
| Training only | 17,695 | 50,840 |
| Strength only | 17,699 | 50,002 |
| Strength first | 17,700 | 50,653 |
| Batched GEPA, cap 52 | 17,694 | 57,271 |
| Sequential GEPA, cap 52 | 17,721 | 81,537 |

The training-only check approved 23 of 111 eligible challengers and used 1,028 training lookups. Across whole episodes it spent 1,510 more lookups than strict CPO and lost 29 held-out passes. The paired range against strict CPO was −53 to −6 passes. The losses were six passes on Llama and 23 on Mistral. Strength first skipped 18 training checks, scored five passes above training only, and saved 187 lookups. Its paired range against training only was −4 to +14. [Per-panel results and traces](routed-training-corroboration-results-v1.json)

All three variants cleared the lookup-savings requirement against both GEPA controls. Their joint quality ranges crossed zero. Training only saved 11.2% of lookups against batched GEPA and 37.6% against sequential GEPA, with a joint range of −86 to +30. The gate was inconclusive for all three variants. This replay supports retaining the strict route on this MMLU cohort. The AIME improvement did not transfer to this four-cycle setting. Fresh-model superiority remains unverified.

## Reproduce

Use GEPA 0.1.4 and the bundled correctness snapshot. Preview the seal, then execute to a fresh path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.routed_training_corroboration
PYTHONHASHSEED=0 python -B -m benchmarks.routed_training_corroboration \
  --execute 5f5a37d6215d47a7be36a62f93b568a1991f1e73208f3ffef774396935c463ff \
  --out NEW_REPORT.json
```

Two source-export replays matched byte for byte with sockets and DNS blocked. They reproduced 48 published control traces across 16 model and subject panels. Seven focused tests passed, including deterministic reservation and rejection when too few disjoint cases remain. The CLI rejected a wrong seal and preserved an existing result. Storage Guard measured 21.2 GiB free. The 15.5 MB temporary overlay was removed under the standing LAB exception. [Focused tests](../tests/unit/test_routed_training_corroboration.py)
