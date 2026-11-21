# Start qualification with the incumbent replies already paid for

The earlier CPO replay ran qualification first when no paid validation backup was eligible. Its certificate reused incumbent precheck grades as it encountered them in the seeded order. This follow-up puts every paid incumbent grade into the certificate bounds before buying another reply. It compares two ways to read what remains. The first preserves the seeded order. The second uses CPO's expected-cost scheduler, estimating each prompt's pass probability from its own paid validation grades. The estimates choose which reply to buy. The exact independent qualification gate determines the result. [Previous proof order](recorded-training-proof-order.md) · [Replay runner](../benchmarks/recorded_paid_qualification_order.py)

Both changes apply equally to CPO and the official sequential and batched GEPA controls. Across 1,520 archived trials per arm and mode, the runner reproduced the published traces and checked that search lookup counts, nominees, deployed prompts, and held-out grades stayed the same. Crediting the prefix while preserving the unread order never added a lookup. Expected-cost ordering traded individual increases against larger aggregate savings.

| Eight-challenger rotation | Method | Holdout passes | Original paid lookups | Credit only | Expected-cost order | Hindsight floor |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| AIME | CPO | 4,073 | 12,212 | 12,206 | 12,164 | 11,872 |
| AIME | Sequential GEPA | 4,074 | 13,720 | 13,713 | 13,701 | 13,430 |
| AIME | Batched GEPA | 4,055 | 13,410 | 13,404 | 13,397 | 13,144 |
| ARC-AGI | CPO | 13,822 | 10,068 | 10,063 | 9,896 | 9,597 |
| ARC-AGI | Sequential GEPA | 13,785 | 11,962 | 11,961 | 11,880 | 11,688 |
| ARC-AGI | Batched GEPA | 13,781 | 10,785 | 10,785 | 10,702 | 10,546 |

On AIME, expected-cost ordering saved CPO 48 paid lookups. With the same order policy on the controls, CPO saved 11.2% against sequential GEPA and 9.2% against batched GEPA. The joint paired case sensitivity range stayed at −23 to +22 passes. On ARC, the order saved CPO 172 lookups, with matched savings of 16.7% and 7.5% and a joint range of −12 to +81 passes. Neither rotation cleared the joint gate. [All settings and paid lookup counts](recorded-paid-qualification-order-results-v1.json)

The hindsight floor keeps each original search and precheck. After nomination, it uses the archived pair to count the fewest unread replies that could prove the same qualification decision. Each such reply can tighten the relevant bound by at most one. The floor selects the replies that tighten it, which requires their future outcomes. On the AIME rotation, the two hindsight floors are 11,872 for CPO and 13,144 for batched GEPA, a 9.7% saving. This diagnostic quantifies what qualification scheduling can save on the fixed paths. Held-out scores stay fixed under every exact schedule.

## Reproduce

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 27 targeted tests passed, including every binary reply matrix for a three-case proof, and two replays matched byte for byte. The CLI rejected the earlier seal and the original ordered live plan reproduced. Storage Guard measured 5.8 GiB free. The 39 MiB source export and publication worktree fit the standing 0.2 GiB LAB exception. The replay used zero provider requests. [Proof tests](../tests/unit/test_recorded_paid_qualification_order.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_paid_qualification_order
python -B -m benchmarks.recorded_paid_qualification_order \
  --execute 1e1a1f694b62dce9be3d609096284563b711ac673c892261a44597981bffc602 \
  --out NEW_REPORT.json
```
