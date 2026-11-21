# Detect shared errors when confirmation fields move

The ordered witness comparison trains and scores on facts presented in a canonical field order. This offline rehearsal moves the first field to the end on four confirmation cases per task. It keeps the facts, labels, critical flags, repeat count, and byte length of every input. The 12 cases include two critical and two ordinary examples each for ticket, warehouse, and outage. They are selected by confirmation case order before scoring. [Ordered protocol](grounded-witness-ordered-futility.md) · [Rehearsal runner](../benchmarks/witness_confirmation_field_order.py)

The replay binds the prompts, attributed search costs, and shared-response schedule from the qualifying ordered development fixture. Of 128 confirmation requests, 64 receive reordered facts. Every other request field is identical to the canonical panel. The rehearsal compares the existing paired gate with an additional check that requires the CPO candidate to give at least one exact reply out of two on each reordered case.

| Fixture | Paired gate | Case-level check | Requests scored |
| --- | --- | --- | ---: |
| Replies independent of field order | Pass | Pass | 128 |
| Every arm fails the first repeat on each reordered case | Pass | Pass | 128 |
| Every arm fails both repeats on one reordered case | Pass in 12 of 12 trials | Reject in 12 of 12 trials | 128 per trial |
| Every arm fails both repeats on all reordered cases | Reject early | Unmeasured | 67 |

Each injected error changes one output field and is scored by the existing exact grader. On the order-agnostic fixture, the scorecard and gate verdicts reproduced the canonical confirmation. The paired gate could still qualify when every arm shared one persistent error, since the comparison retained its relative margin and absolute task floors. The extra check caught that error and tolerated a single failed repeat. This measures the ability to detect scripted errors under one controlled input change. Fresh model behavior and provider token counts remain unmeasured. [Exact cases, schedule hashes, and results](witness-confirmation-field-order-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and outbound sockets blocked, 32 targeted tests passed and two replays matched byte for byte. A stale seal was rejected and the published ordered development manifest reproduced unchanged. Storage Guard measured 5.9 GiB free. The 39 MiB export, fixtures, and publication worktree fit the standing 0.2 GiB LAB exception. The rehearsal made zero provider requests. [Verification tests](../tests/unit/test_witness_confirmation_field_order.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_confirmation_field_order
python -B -m benchmarks.witness_confirmation_field_order \
  --execute e73aff58418c4a31c8ffe5a5fef74943e5d04a0772e2e08f74c1e84ec287211a \
  --out NEW_REPORT.json
```
