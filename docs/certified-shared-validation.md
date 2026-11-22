# Certify each shared validation cut with fewer lookups

`run_certified_shared_validation_cycle` is an opt-in fixed-pool runner in `cpo.certified_shared_validation_cycle`. It takes the same callbacks, schedules, and limits as `run_shared_validation_cycle`. It assumes stable boolean grades for a prompt and case within a cycle. Qualification uses a separate panel and decides which prompt to deploy. [Runner](../cpo/certified_shared_validation_cycle.py) · [Eager policy and original protocol](budgeted-shared-panel-search.md)

On each round's common case, an unread challenger can increase its known score by at most one. The runner visits challengers by that optimistic score and uses the original pool order to break ties. It stops as soon as the worst exact survivor outranks the best possible unread challenger, or when no unread challenger can still meet the eligibility threshold. Every survivor has an exact score for the same cases, so the next round and the independent qualification receive the original evidence. The original cap still determines which whole rounds are funded. The runner leaves saved lookups unspent and passes critical validation panels through the original strict screen.

## Archived results

The paired replay covers 134 archived model panels and 32 seeds per panel at each of two independent qualification margins. Across all 8,576 paths, the certified runner preserved every nominee, ordered qualification receipt, deployment, and held-out grade. It skipped 15,425 of 156,798 total lookups, including 9,545 at one qualification gain. Those 9,545 lookups account for 10.9% of all one-gain lookups and 15.0% of one-gain validation lookups. [Sealed replay](certified-shared-validation-results-v1.json)

| Cohort at one qualification gain | Held-out passes | Eager to certified lookups | Lookups saved | CPO pass difference against split-safe GEPA |
| --- | ---: | ---: | ---: | ---: |
| Original BBH | 9,840 | 20,209 → 18,788 | 7.0% | +95 to +164 |
| BBH, other checkpoints on previously studied tasks | 4,901 | 11,037 → 10,306 | 6.6% | −19 |
| BBH, causal judgment | 620 | 1,341 → 1,209 | 9.8% | +28 to +30 |
| Original LMentry | 6,078 | 11,379 → 10,666 | 6.3% | +404 to +480 |
| LMentry, other checkpoints on previously studied tasks | 5,546 | 8,027 → 7,271 | 9.4% | +142 to +298 |
| LMentry, ends-with-word | 315 | 1,465 → 1,425 | 2.7% | +37 |
| Earlier MMLU | 26,642 | 17,421 → 14,732 | 15.4% | −13 |
| Disjoint MMLU | 56,034 | 17,005 → 13,942 | 18.0% | −55 |

The GEPA column uses the prior subject-tuned split-safe menu. The prior ceiling at the higher budget bounds GEPA from above. A published attaining setting that fits the lower budget bounds GEPA from below. Matching bounds give the exact ceiling. The ranges are budget bounds. At one gain CPO still leads in five cohorts. On earlier and disjoint MMLU the exact GEPA ceilings still cost 8,574 and 6,814 lookups respectively. These results cover stable archived grades. Fresh-model performance remains unverified. [Split-safe GEPA results and controls](shared-validation-split-safe-transfer.md)

## Reproduce offline

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.certified_shared_validation
PYTHONHASHSEED=0 python -B -m benchmarks.certified_shared_validation \
  --execute 04fcbf15154f7dc92c65e3df619572b4c229173379534355924cb9c71f30118e \
  --out NEW_REPORT.json
```

The replay uses Python 3.12 and the pinned GEPA 0.1.4 archive dependency. Two socket-blocked source runs and the installed wheel run produced identical result bytes. Thirteen targeted tests passed, including exhaustive comparison on 4,096 grade matrices at seven caps and two validation margins, and callback-order parity for critical validation. Storage Guard measured 2.2 GiB free. The temporary source export, wheel verification, and publication checkout were scoped to 0.2 GiB under the standing LAB exception. [Benchmark requirements](../requirements-benchmark.txt) · [Parity tests](../tests/unit/test_certified_shared_validation_cycle.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
