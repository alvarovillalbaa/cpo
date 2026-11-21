# Let settled proofs guide the shared admission queue

The previous shared-budget replay found that the retry-first order selected for MMLU spent 325 lookups without a promotion. This comparison keeps the same original search outcomes, optional proof offers, and fixed cohort budgets. It asks whether the queue can switch between stalled-search admission and exact-rejection retry using feedback it has already paid for. [Fixed queue comparison](witness-shared-admission-credit.md) · [Runner](../benchmarks/witness_adaptive_admission_credit.py)

Both new queues preserve scheduled episode order within each route. The alternating control favors the route with fewer settled attempts. The adaptive queue initially tries each affordable route and then favors the larger ratio of promotions plus one to charged reads plus 24. Fewer attempts and earlier episode order break ties. The queue skips offers it cannot fully reserve. Once a proof settles, only its exact promotion and charged reads affect the next choice. The held-out grades are available only to the benchmark's scoring step.

The replay verifies every previously published fixed queue. It compares the adaptive policy with the alternating control and the single proof. The other family can choose any fixed or adaptive queue based on promotion counts and spend. A positive paired lower endpoint against the single proof is required in all three cohorts.

## Results

| Cohort | Full single proof passes / lookups | Alternating passes / lookups | Adaptive passes / lookups | Adaptive vs single proof paired 95% range, percentage points |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,268 / 72,522 | 17,290 / 72,530 | +0.313 to +0.746 |
| MMLU prior subjects | 21,180 / 34,122 | 21,190 / 34,336 | 21,190 / 34,342 | −0.008 to +0.072 |
| MMLU additional subjects | 8,976 / 13,639 | 8,976 / 13,753 | 8,976 / 13,753 | 0 to 0 |

The adaptive queue matched the best observed fixed order on BBH and LMentry. It added 222 held-out passes over the single proof within the seeded budget. It also gained 22 passes for eight extra lookups over alternating, whose paired comparison ranged from zero to +0.142 percentage points.

On the prior MMLU subjects, adaptation moved the budget toward direct proofs. It opened 11 direct proofs and three retries, with four promotions from the direct route. It tied the alternating queue on held-out passes. The fixed direct-only queue achieved the same ten-pass gain with 19 fewer lookups. Neither new queue promoted anyone on the additional MMLU subjects. The outside-family fits still selected direct-only for BBH and LMentry and retry-first for MMLU. The all-cohort gate remained unmet. [All queue results and comparison ranges](witness-adaptive-admission-credit-results-v1.json)

Shorter proof reservations funded additional attempts without improving the MMLU scores. [Shortened proof comparison](witness-short-admission-credit.md)

## Reproduce

Use a clean export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 61 targeted tests passed and two replays matched byte for byte. Every fixed queue reproduced its published scores, costs, and dispatch trace. The CLI rejected a stale seal, and the prospective live plan reproduced byte for byte. Storage Guard measured 6.3 GiB free. The export, overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Adaptive funding tests](../tests/unit/test_witness_adaptive_admission_credit.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_adaptive_admission_credit
python -B -m benchmarks.witness_adaptive_admission_credit \
  --execute b76309cd848984a58b15021bff9dde448d63f789296d16fee34d90eeb00366b6 \
  --out NEW_REPORT.json
```
