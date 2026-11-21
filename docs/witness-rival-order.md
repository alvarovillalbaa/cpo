# Measure the cost of ordering a rival's proof

The paid-rival audit found 180 MMLU second attempts where an improving rival passed the complete independent proof but exceeded the remaining budget. This replay keeps paid search, the first proof, the ranked rival, and the rival's allotted rows fixed. It compares the expected-read scheduler with one that prioritizes the estimated probability of certifying promotion before the same cap. Paid validation grades seed the estimate. Exact score bounds decide promotion. [Rival audit](witness-rival-capacity.md) · [Replay runner](../benchmarks/witness_rival_order.py)

For the 180 MMLU episodes and their BBH and LMentry counterparts, the replay also computes two hindsight minima for each improving paid rival with a complete certificate. With the row order fixed on each side, it finds the cheapest combination of incumbent and challenger prefixes. With arbitrary order, it counts only the favorable grades needed for a proof. An eight-row panel with minimum gain one needs at least nine favorable replies. A tied base panel requires all 16 base replies before opening the extension, even with perfect ordering. The minima use the complete archived replies and measure what is possible under the fixed proof rule.

## Results

| Cohort | A different side order could fit | A different case order was needed | Even the minimum exceeded the cap | All episodes with an improving certificate beyond the recorded cap |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 30 | 189 | 14 | 233 |
| MMLU prior subjects | 8 | 112 | 9 | 129 |
| MMLU additional subjects | 3 | 43 | 5 | 51 |

On MMLU, a perfect side scheduler could make room for at least one improving paid rival in 11 of the 180 episodes while keeping both sides' case order. Another 155 required changing the order of cases. The last 14 exceeded the remaining cap even with the cheapest possible certificate. Those 14 necessarily require opening the tie panel since a base certificate can always fit the reserved minimum.

Promotion-first scheduling changed zero deployments across all 1,066 observed second attempts. It used 156 extra lookups, including 14 on MMLU, and the paired score intervals were zero in all three cohorts. The measured headroom is for reordering cases and considering all paid rivals with hindsight. The tested scheduler changed only which side to read next for the original ranked rival. [Full results](witness-rival-order-results-v1.json)

Chronological peer-model validation grades supported a case reorder in 986 second attempts. The resulting policy added eight pooled MMLU passes and failed the cross-cohort gate. [Peer case-order replay](witness-peer-case-order.md)

A follow-up used the first proof's cases for the preselected backup and reused the incumbent replies already paid there. [Shared-panel proof comparison](witness-shared-incumbent-proof.md)

## Reproduce

Use a clean export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 30 targeted tests passed and two replays matched byte for byte. The complete parent audit reproduced, the CLI rejected a stale seal, and the prospective live plan reproduced byte for byte. The replay issued zero provider requests. Storage Guard measured 5.7 GiB free. The export, overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Certificate tests](../tests/unit/test_witness_rival_order.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_rival_order
python -B -m benchmarks.witness_rival_order \
  --execute c9e2b8f546b3ddcdda3e17a31e31cf36a2172c33734a7501de6c634b7b4d3952 \
  --out NEW_REPORT.json
```
