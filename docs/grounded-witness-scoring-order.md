# Test whether scoring order can shorten a failed witness comparison

The sealed witness and Halving comparison already stops when the best possible completion fails its gate. This offline replay tests whether the same guard can reach rejection sooner by changing only the order of scoring requests. It preserves every selected prompt, case, repeat, shared reply, search cost and acceptance rule. The published live plan remains sealed. [Original futility plan](grounded-witness-halving-futility.md) · [Ordering replay](../benchmarks/grounded_witness_scoring_order.py)

One order scores critical case-repeats first when the candidate has a different prompt from at least one control. It leaves the original order within each case-repeat. A second order also scores the candidate's reply first within each case-repeat and moves replies used exclusively by the descriptive arm to the end. Both still score every scheduled reply on a qualifying run.

The replay covers development and independent confirmation. It reproduces the published qualifying fixture and the all-fail scoring fixture, then faults the candidate on each task in turn. It also tries a matched loss at every contested critical case-repeat by making the candidate fail and one distinct control pass. A changed shared reply affects every arm that shares it. Each order's result is checked against the fully observed acceptance gate. These scenarios measure how ordering affects scoring requests after search. They use scripted grades and supply no evidence about provider behavior under a changed request order.

## Results

| Phase | Rejected scenarios | Contested critical first, earlier / tied | Gate-relevant first, earlier / tied | Most requests saved by gate-relevant order |
| --- | ---: | ---: | ---: | ---: |
| Development | 60 | 56 / 4 | 58 / 2 | 135 |
| Independent confirmation | 28 | 28 / 0 | 28 / 0 | 56 |

Both reordered schedules rejected every failed scenario at or before the original cutoff. The 88 failed scenarios included 80 matched critical losses. On the all-fail development fixture, the gate-relevant order scored 19 requests against the original 20. On the outage-only development failure, it scored 128 against 209. The outage-only confirmation failure took 55 requests against 93. The qualifying fixtures ran all 288 development and 128 confirmation scoring requests under every order. All decisions matched the fully observed gate. [Request counts and scenario receipts](grounded-witness-scoring-order-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Two offline replays matched byte for byte. The runner regenerated the published qualifying development archive and all four original scoring traces. The prospective live-plan preview reproduced byte for byte and the CLI rejected a stale seal. With sockets and DNS blocked, 36 targeted tests passed, including exhaustive gates for a six-reply shared panel. Storage Guard measured 6.1 GiB free. The 38 MiB export and bounded publication worktree used the standing 0.2 GiB LAB exception. [Ordering and gate tests](../tests/unit/test_grounded_witness_scoring_order.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.grounded_witness_scoring_order
python -B -m benchmarks.grounded_witness_scoring_order \
  --execute c98b7b4a106b9c9a1aa3f4109de960e8ffee2e1aebd2578516be525f03c7d756 \
  --out NEW_REPORT.json
```
