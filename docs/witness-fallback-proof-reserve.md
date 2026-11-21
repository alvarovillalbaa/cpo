# Reserve proof first near the fallback budget boundary

Reserving proof first let some tasks run a fallback that the full reservation would have blocked. At the primary budget it spent **239 more lookups** and scored **three fewer passes** in aggregate than reserving the complete episode. The method missed the transfer gate. [Full-reservation comparison](witness-fallback-reserve.md) · [Sealed evidence](witness-fallback-proof-reserve-results-v1.json)

The replay keeps the earlier issued budgets and the paid and blind ordering that each held-out fold fitted on other families. Before each fallback it reserves the maximum independent proof cost. Search receives the lesser of 16 new lookups and the remaining credit after that reservation. The ledger returns unused credit after settlement. When only proof fits, search can use its paid cache with a cap of zero. When proof no longer fits, the task stops. A shorter search that cannot produce a nominee retains the incumbent. The grade cache, admission gate, and holdout remain as in the published comparison. [Runner](../benchmarks/witness_fallback_proof_reserve.py)

| Held-out family | Issued lookups | Full paid reservation, added passes / lookups | Proof-first paid | Proof-first blind |
| --- | ---: | ---: | ---: | ---: |
| BBH | 1,528 | 105 / 1,219 | 105 / 1,316 | 38 / 1,327 |
| LMentry | 504 | 41 / 350 | 41 / 376 | 22 / 391 |
| MMLU | 2,696 | 13 / 2,297 | 10 / 2,411 | 9 / 2,406 |
| Promptolution | 64 | 44 / 38 | 44 / 40 | 70 / 56 |
| Pooled counts | 4,792 | 203 / 3,904 | 200 / 4,143 | 139 / 4,180 |

No task exceeded its issued budget. The proof-first policy tried more episodes near the cutoff and reproduced the same passes on three families at the primary rate. All three MMLU passes lost relative to the full reservation came from the shortened-search path. The gate required a positive paired lower endpoint in every family against full-reservation paid ordering and equally funded proof-first blind ordering. At the lower rate of four lookups per eligible episode, the first paid Promptolution fallback became affordable and added 22 passes for 17 lookups. At that rate the proof-first blind order added 24 for 19. These are results on archived grades. Fresh-model performance remains open. [Sensitivity and per-task settlements](witness-fallback-proof-reserve-results-v1.json)

## Reproduce

Two offline replays matched byte for byte. The runner reproduced the original full-reservation paid and blind outcomes and replayed all 16 shorter search caps. Twelve targeted tests passed, covering proof protection, zero-search admission credit, and exact settlement. Storage Guard measured 6.0 GiB free. The task-owned exports and pinned wheel overlay fit within the standing LAB exception's 0.2 GiB scope. [Tests](../tests/unit/test_witness_fallback_proof_reserve.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.promptolution_witness_capture --out PREDICTIONS.json
python -B -m benchmarks.witness_fallback_proof_reserve \
  --corpus PREDICTIONS.json \
  --execute 0d6b5a0d5288e6286dbc6d69d77a3eca1c49c071d5f9070c8cf5666badc334eb \
  --out PROOF_FIRST.json
```
