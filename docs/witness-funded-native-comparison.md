# Pair selective retry against affordable native GEPA

The retry funding experiment selected a rule on the other benchmark family and compared it with CPO's single proof. This replay compares both CPO policies directly with native GEPA on the same episodes. The gates remain fixed at at least 14 remaining reads for BBH and LMentry and at least 12 for both MMLU cohorts. The original paid search, episode starts, proposal rosters, proof panels, and case splits remain fixed. [Retry funding experiment](witness-retry-funding.md) · [Native control sweep](witness-cached-gepa-evidence.md) · [Runner](../benchmarks/witness_funded_native_comparison.py)

The runner checks native lookup counts, scores, and available trace hashes for each model and subject. It verifies that GEPA's training and validation IDs are disjoint. Each of 4,096 draws samples subjects and the same held-out cases for every arm. Each sampled case carries both model panels and all episodes. Subjects receive equal weight. For each CPO policy, the comparator reselects the strongest fixed native setting that fits that draw's sampled CPO lookup cost. Retaining the start remains eligible at zero cost.

The gate requires a positive lower endpoint against the resampled native comparator and spend within the seeded CPO proof cost on all three cohorts. The pooled MMLU result and the best possible retrospective subject-by-subject native allocation are diagnostic.

## Results

| Cohort | Funded CPO passes / lookups | Best affordable GEPA on observed totals | Funded CPO paired 95% range | Single-proof CPO paired 95% range |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,253 / 71,868 | 16,180 / 71,655 | +1.473 to +3.549 pp | +1.174 to +3.085 pp |
| MMLU prior subjects | 21,180 / 34,398 | 21,159 / 30,096 | −0.118 to +0.167 pp | −0.117 to +0.158 pp |
| MMLU additional subjects | 8,973 / 13,812 | 8,976 / 13,219 | −0.429 to +0.412 pp | −0.384 to +0.412 pp |
| MMLU pooled diagnostic | 30,153 / 48,210 | 30,127 / 46,190 | −0.137 to +0.180 pp | −0.120 to +0.181 pp |

On BBH and LMentry, funded retry passed the paired native gate and spent 666 fewer lookups than the original seeded CPO proof. Its observed equal-subject score was 1.143 percentage points above the best hindsight subject-by-subject native allocation at the same budget. The single proof also cleared the native quality gate at its own lower budget. Both MMLU intervals crossed zero, and the funded policy exceeded seeded CPO spend in both MMLU cohorts. The all-cohort gate failed. [Complete results and draw-level comparator frequencies](witness-funded-native-comparison-results-v1.json)

## Reproduce

Use a clean source export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 46 targeted tests passed and two full replays matched byte for byte. The CLI rejected a stale seal and the prospective live manifest reproduced byte for byte. The replay issued zero provider calls. Storage Guard measured 5.4 GiB free. The export, wheel overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Budget reselection tests](../tests/unit/test_witness_funded_native_comparison.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_funded_native_comparison
python -B -m benchmarks.witness_funded_native_comparison \
  --execute 8b0b0e38099d35da9ce8dda83b5c8b079587896e07b69e62cb49d0fe06936bb8 \
  --out NEW_REPORT.json
```
