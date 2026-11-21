# Start the fallback race with paid grades

The previous four-anchor fallback reused the witness cache when it encountered a requested grade. It reached its 16-new-lookup ceiling before settling in 461 of 591 eligible episodes. This replay initializes every candidate's score bounds and every anchor's pass rate from all relevant paid grades before choosing the first purchase. It keeps the same candidate roster, seeded anchors, cycle order, and shared budget. [Earlier fallback replay](witness-anchor-fallback.md) · [Runner](../benchmarks/witness_paid_anchor_bounds.py)

The exact arm stops when no rival can beat the leading lower bound under the original tie order. The second arm can also nominate at the cap when the best observed lower bound is strictly higher than the incumbent's upper bound. That proves an anchor gain even if a different challenger could finish higher. Both arms keep every original witness nomination and use the same single independent proof after fallback. Qualification and holdout grades stay outside the search.

The proved-gain arm is the primary comparison. Its paired 95% lower endpoint must be positive against the original Halving policy, and its realized lookup total must stay within seeded CPO's ceiling on each cohort. The exact arm isolates how much of the result comes from applying the paid grades earlier. The report verifies the frozen original control traces and includes native GEPA points at each arm's realized cost.

## Results

| Cohort | Original Halving passes / lookups | Earlier cached race passes / lookups | Initialized exact race passes / lookups | Proved gain at cap passes / lookups | Seeded lookup ceiling |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 16,929 / 71,163 | 16,929 / 71,157 | 17,071 / 71,884 | 72,534 |
| MMLU prior subjects | 21,180 / 34,122 | 21,173 / 34,825 | 21,173 / 34,825 | 21,178 / 35,010 | 34,343 |
| MMLU additional subjects | 8,976 / 13,639 | 8,981 / 13,920 | 8,981 / 13,920 | 8,981 / 13,960 | 13,754 |

Initializing the exact race saved six lookups and preserved every cohort's score total. Each initialized arm reached the cap with the winning identity unsettled in 461 of 591 eligible episodes, matching the earlier fallback's count. The proved-gain arm recovered 80 additional nominations at those stops. The independent proof promoted 33 of them and used 952 extra lookups across the three cohorts. The two initialized arms spent the same number of validation lookups.

Against original Halving, the proved-gain arm gained three BBH and LMentry passes. The paired 95% interval ran from −0.175 to +0.182 percentage points. It exceeded the seeded ceiling by 667 lookups on the prior MMLU subjects and 206 on the additional subjects. Neither arm passed the transfer gate. The replay uses recorded grades and sends zero provider requests. [Full results, lookup charges, and paired intervals](witness-paid-anchor-bounds-results-v1.json)

## Reproduce

Use Python 3.12 with the pinned GEPA 0.1.4 wheel. With sockets and DNS blocked, two complete replays matched byte for byte and 101 targeted tests passed. The small-board test enumerated all binary outcomes and paid subsets under three lookup caps. The CLI rejected a stale seal, and the prospective live-plan preview reproduced byte for byte. Storage Guard measured 6.1 GiB free. The temporary export, wheel overlay, and publication worktree used the standing 0.2 GiB LAB exception. [Bounds and shared-budget tests](../tests/unit/test_witness_paid_anchor_bounds.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_paid_anchor_bounds
python -B -m benchmarks.witness_paid_anchor_bounds \
  --execute b48f48f870a82ac73503d65fa92c447c47a7b227c0945e0d4ffc02c695f55d7a \
  --out NEW_REPORT.json
```
