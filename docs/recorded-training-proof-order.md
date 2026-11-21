# Run the shorter qualification panel first when there is no backup

The certified training-backup policy protects AIME promotions from weak training support. It originally runs a training check before independent qualification so a training veto can hand the single qualification slot to an already validated backup. This replay tests a conditional change. When the paid validation ledger has no eligible backup and the full training reserve fits, run qualification first. A qualification failure then settles the deployment without buying the training check. An eligible backup keeps the original order. [Original training policy](recorded-training-backup.md) · [Replay runner](../benchmarks/recorded_training_proof_order.py)

The replay keeps the same incumbents, rosters, training and qualification panels, incumbent precheck, search ceiling, and holdout. It verifies the published CPO and GEPA traces and requires the revised policy to return the same deployed prompt and every held-out grade on all 1,520 trials. A qualification-first check can cost more on individual trials where qualification passes and training vetoes the nominee. The policy checks the training reserve before starting either proof.

| Archived setting | Holdout passes | Original paid lookups | Qualification-first paid lookups | Saved |
| --- | ---: | ---: | ---: | ---: |
| AIME root, four challengers | 489 | 1,213 | 1,162 | 51 |
| AIME root, eight challengers | 485 | 1,650 | 1,610 | 40 |
| AIME rotation, four challengers | 4,078 | 8,936 | 8,603 | 333 |
| AIME rotation, eight challengers | 4,073 | 12,534 | 12,212 | 322 |
| ARC root, four challengers | 1,561 | 1,826 | 1,826 | 0 |
| ARC root, eight challengers | 1,578 | 2,025 | 2,025 | 0 |
| ARC rotation, four challengers | 13,761 | 9,031 | 8,581 | 450 |
| ARC rotation, eight challengers | 13,822 | 10,589 | 10,068 | 521 |

On the eight-challenger AIME rotation, the revised policy skipped 90 training proofs after qualification rejected the nominee. It also paid for qualification on 25 trials where training later vetoed the nominee. The net saving moved CPO to 11.0% fewer lookups than sequential GEPA and 8.9% fewer than batched GEPA. CPO remained one pass behind sequential GEPA and 18 ahead of batched GEPA. The joint paired 95% case sensitivity range was −23 to +22 passes, and the saving against batched GEPA fell below the 10% requirement. On the eight-challenger ARC rotation the revised policy saved 6.6% against batched GEPA and 15.8% against sequential GEPA. Its joint range was −12 to +81. These replays reuse stored replies. The new order reduces cost on the tested backup policies while preserving their archived quality gaps. [Full results and paid lookup accounting](recorded-training-proof-order-results-v1.json)

A follow-up credited the paid incumbent replies before starting the certificate and applied expected-cost ordering to CPO and both GEPA controls. [Paid qualification scheduling](recorded-paid-qualification-order.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 17 targeted tests passed and two replays matched byte for byte. A stale seal was rejected, and the prospective ordered live plan matched its manifest. Storage Guard measured 5.8 GiB free. The 39 MiB export and bounded publication worktree fit the standing 0.2 GiB LAB exception. The replay sent zero provider requests. [Proof-order tests](../tests/unit/test_recorded_training_proof_order.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_training_proof_order
python -B -m benchmarks.recorded_training_proof_order \
  --execute 2f4daa984e2e488b5f3a43e56f9a1481c6a9c1e1aebbead7c218f5c603d9f917 \
  --out NEW_REPORT.json
```
