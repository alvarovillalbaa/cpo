# Stress-test opening-route budgets

The fractional opening rule improved BBH and LMentry on archived replies and exceeded the seeded lookup budget on held-out subjects. This comparison keeps the same paid opening, routes, and rule menu. It tests whether a stricter training budget transfers and measures how much improvement the two fixed routes could produce within the same budget. [Fractional routing comparison](witness-anchor-routing.md) · [Replay runner](../benchmarks/witness_anchor_routing_budget.py)

The primary fit must stay within seeded cost on the full training pool and on every pool formed by removing one training subject. The second fit requires every training subject to fit its own seeded cost. Both maximize mean subject accuracy, with lower lookup cost breaking ties. The evaluated subject, including both models and all seeds, is excluded from training. Both MMLU cohorts use the other MMLU subjects for fitting. The primary rule must stay within each cohort's realized seeded cost and have a positive paired 95% lower endpoint against both the original route and the previous blind fit.

The hindsight calculation chooses one of the two fixed routes per episode with access to both final holdout grades and lookup totals. It starts from the cheaper choices and finds the exact best set of paid upgrades under the original or seeded aggregate ceiling. It maximizes total holdout passes and subject-macro accuracy separately. Ties favor fewer lookups. These are upper bounds for this pair of routes, and achieving them requires future evidence unavailable when routing.

## Results

| Cohort | Original passes / lookups | Leave-one-training-subject-out passes / lookups | Individual training budget passes / lookups | Seeded lookup ceiling | Hindsight maximum passes / lookups |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,131 / 72,971 | 17,068 / 71,122 | 72,534 | 18,465 / 67,342 |
| MMLU prior subjects | 21,180 / 34,122 | 21,182 / 34,415 | 21,180 / 34,122 | 34,343 | 21,313 / 32,284 |
| MMLU additional subjects | 8,976 / 13,639 | 8,976 / 13,642 | 8,976 / 13,639 | 13,754 | 9,012 / 12,815 |

On BBH and LMentry, the primary fit lowered the earlier fractional rule's overage from 1,332 to 437 lookups. It gained 63 passes over the original and had four fewer passes than the blind fit, which used 764 fewer lookups. Its paired 95% intervals were −0.076 to +0.381 percentage points against the original and −0.090 to +0.073 against the blind fit. The prior MMLU subjects still exceeded the seeded ceiling by 72 lookups, and the additional subjects gained no passes. The individual training-budget fit stayed within every held-out cohort's ceiling and matched the original's pass totals. It chose the wider route in one of 2,240 episodes. Both fits missed the transfer gate.

The hindsight maxima and their costs are identical under both ceilings, because the minimum-cost mix that maximizes holdout passes fits within each original budget. It supplies 1,397 additional BBH and LMentry passes for 3,729 fewer lookups than the original route. The MMLU maxima add 133 and 36 passes while saving 1,838 and 824 lookups, respectively. The wider route was cheaper in 838 episodes, and it improved holdout passes at the same or lower cost in 156 episodes. These results quantify what episode selection could recover. Tightening the budget for the existing opening rule did little to recover it. [Full receipt, macro maxima, paired intervals, selected rules, and matched-cost native GEPA points](witness-anchor-routing-budget-results-v1.json)

A follow-up ran the four-anchor race only after the witness search found no nominee. With the same fallback cap as Halving, the anchor race exhausted its budget before settling in 461 of 591 eligible episodes and missed the transfer gate. [Cached fallback comparison](witness-anchor-fallback.md)

## Reproduce

Use Python 3.12 with the pinned GEPA 0.1.4 wheel in a clean source export. With sockets and DNS blocked, 95 targeted tests passed and two complete replays matched byte for byte. The runner reproduced both fixed routes and the previous opening and blind fits. It rejected a stale seal. The prospective live plan reproduced byte for byte. Both replays made zero provider requests. The bounded export and publication worktree used the standing 0.2 GiB LAB storage exception after Storage Guard measured 6.3 GiB free. [Budget and exact-selection tests](../tests/unit/test_witness_anchor_routing_budget.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_anchor_routing_budget
python -B -m benchmarks.witness_anchor_routing_budget \
  --execute 9af2ddeaec747d9ffb4f3d1dfa3ba17e6f835cb05d6529c473e57e4a9d102930 \
  --out NEW_REPORT.json
```
