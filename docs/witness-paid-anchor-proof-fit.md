# Fit the search cap and which challengers earn proof

The earlier fallback used 16 new lookups per episode. Its optional proofs restored the BBH and LMentry score and drove MMLU further above its seeded budget. The exact race already exceeded both MMLU budgets before those proofs. This replay fits the search cap and the proof decision together. [Earlier paid-anchor comparison](witness-paid-anchor-bounds.md) · [Replay runner](../benchmarks/witness_paid_anchor_proof_fit.py)

The menu uses caps of 8, 12, and 16 new grades. It preserves every witness nominee and every settled winner. At the cap, an unsettled challenger needs a proved anchor gain to be eligible for independent proof. The learned rule may require a strict lower-bound lead of two, preservation of every paired incumbent pass already observed, or at least two net wins across paid paired grades. The shared menu also covers proving every eligible challenger, proving none, and using original Halving. The blind menu uses the same caps and permits stable hash gates at one quarter, one half, or three quarters of eligible episodes.

Each fit excludes both models and all seeds for the evaluated subject. It uses the other subjects from BBH and LMentry together or from both MMLU cohorts together. The fit maximizes mean subject accuracy within the training group's combined seeded lookup allowance. Lower cost breaks ties. The replay restores the incumbent and removes only the exact proof charge when a rule skips a proof. It verifies the 16-lookup all-proof and exact arms against their published totals.

The learned rule needs a positive paired 95% lower endpoint against original Halving and the separately fitted blind rule. It must also stay within the realized seeded budget on every cohort. The report gives the best fixed native GEPA point affordable at the learned rule's realized cost.

## Results

| Cohort | Original Halving passes / lookups | Learned rule passes / lookups | Blind rule passes / lookups | Fixed cap of eight, all eligible proofs | Seeded lookup ceiling |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,029 / 71,720 | 17,029 / 71,720 | 17,046 / 69,624 | 72,534 |
| MMLU prior subjects | 21,180 / 34,122 | 21,184 / 33,781 | 21,184 / 33,745 | 21,184 / 32,914 | 34,343 |
| MMLU additional subjects | 8,976 / 13,639 | 8,986 / 13,646 | 8,986 / 13,623 | 8,986 / 13,349 | 13,754 |

No paid filter won a training fold. On BBH and LMentry, both fits selected the 16-lookup cap with all eligible proofs for 17 subjects and original Halving for five. The fitted rule lost 39 passes and used 649 more lookups than Halving. The paired 95% interval ran from −0.234 to +0.028 percentage points.

On MMLU, both fits selected 12 lookups on 12 subjects and eight on one. The learned rule proved every eligible challenger. The blind rule used the three-quarters rate, saved 59 proof lookups across both cohorts, and matched the learned scores. The learned rule fit all three seeded budgets and missed the paired quality gate. As a fixed-rule diagnostic, eight lookups with all eligible proofs added four and ten MMLU passes while saving 1,208 and 290 lookups against original Halving. The same setting lost 22 BBH and LMentry passes. [Full receipt, selected rules, paired intervals, and matched-cost native GEPA points](witness-paid-anchor-proof-fit-results-v1.json)

## Reproduce

Use Python 3.12 with the pinned GEPA 0.1.4 wheel. With sockets and DNS blocked, 104 targeted tests passed and two complete replays matched byte for byte. The CLI rejected a stale seal, and the prospective live-plan preview reproduced byte for byte. Storage Guard measured 6.1 GiB free. The temporary export, wheel overlay, and publication worktree used the standing 0.2 GiB LAB exception. The replay sent zero provider requests. [Proof, accounting, and subject exclusion tests](../tests/unit/test_witness_paid_anchor_proof_fit.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_paid_anchor_proof_fit
python -B -m benchmarks.witness_paid_anchor_proof_fit \
  --execute c929be0c6534b6129e54e5c417e9492dc49fbf4e8a6e9e05b1aa0acecccb90db \
  --out NEW_REPORT.json
```
