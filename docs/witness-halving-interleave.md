# Allocate Halving fallback one lookup at a time

Ranking fallback cycles once at entry had a small effect on recorded scores. This replay recalculates the same priority after each new paid grade. The leading cycle can purchase at most one answer before the priorities are updated. A settled challenger can enter the original independent proof. The policy uses the inherited witness search and shared 16-lookup fallback budget. [Fixed cycle priority](witness-halving-cycle-priority.md) · [Replay runner](../benchmarks/witness_halving_interleave.py)

The separate hindsight calculation starts each cycle directly from the paid witness cache and runs the original cap-eight Halving schedule under the same shared new-lookup cap. A cycle contributes an option only if it yields a challenger that passes the original independent proof and improves the held-out score. Each episode can keep the incumbent at no additional cost or choose one complete option. The calculation maximizes held-out passes under the original or seeded cohort lookup budget using future outcomes and charges. Its scope is the evaluated direct-cycle menu. It measures the room for choosing a cycle without modeling every possible interleaved acquisition policy.

The eligibility trigger, case splits, candidate rosters, and proof panels are fixed. The deployable interleaving policy uses only paid validation grades. It must fit the seeded lookup budget and have a positive paired 95% lower endpoint against original Halving in every cohort. The strongest affordable native GEPA point is reported at its measured cost.

## Results

| Cohort | Original Halving passes / lookups | Fixed priority passes / lookups | Interleaved passes / lookups | Direct-cycle hindsight passes / lookups |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,070 / 71,029 | 17,091 / 71,065 | 17,169 / 67,613 |
| MMLU prior subjects | 21,180 / 34,122 | 21,186 / 34,116 | 21,197 / 34,187 | 21,211 / 30,936 |
| MMLU additional subjects | 8,976 / 13,639 | 8,975 / 13,662 | 8,976 / 13,664 | 8,986 / 12,684 |

Interleaving gained 23 passes while saving six lookups on BBH and LMentry. The prior MMLU subjects gained 17 passes for 65 more lookups. The additional MMLU subjects matched the original score for 25 more lookups. All three fit the seeded budgets. The paired 95% intervals against original Halving were −0.021 to +0.142, −0.015 to +0.098, and −0.127 to +0.066 percentage points, respectively. The policy missed the gate.

The direct-cycle maximum used the same score and cost under both ceilings on each cohort. An improving direct choice existed in 47 of 254 BBH and LMentry fallback episodes, nine of 259 prior MMLU episodes, and three of 78 additional MMLU episodes. With hindsight, that menu gained 101, 31, and ten passes against original Halving and saved 3,458, 3,186, and 955 lookups, respectively. These maxima select from archived proof and holdout outcomes. [Full receipt and matched-cost native GEPA points](witness-halving-interleave-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With sockets and DNS blocked, 107 targeted tests passed and two complete replays matched byte for byte. The CLI rejected a stale seal, and the prospective live-plan preview reproduced byte for byte. Storage Guard measured 6.2 GiB free. The 39 MiB export and bounded publication worktree used the standing 0.2 GiB LAB exception. The replay sent zero provider requests. [Acquisition and single-proof tests](../tests/unit/test_witness_halving_interleave.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_halving_interleave
python -B -m benchmarks.witness_halving_interleave \
  --execute d84fd21a0f53ccd31f46e500afdd84ae5edfc26b8ef1fe9b557fce8355c884c3 \
  --out NEW_REPORT.json
```
