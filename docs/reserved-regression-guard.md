# Check the final prompt for regression on reserved cases

Previously paid validation and qualification favored CPO’s selected prompt in all 109 losing comparisons where the start would have matched GEPA. Moving the final qualification check later recovered none of those losses. This replay tests advice from a new paired panel while leaving the trajectory that produced the final candidate intact. [Paid-evidence result](paid-start-retention.md) · [Final-cycle ordering study](final-start-reconciliation.md)

For each of the original 896 schedules, the replay excludes every scheduled training, validation, qualification, and final holdout case. It reserves up to eight remaining cases in a seeded order without using their outcomes. Both models on a subject share the reserve. The guard runs only when the final prompt differs from the start, at least four cases are available, and unused capacity under the original episode allowance can fund a complete check. It charges the actual replies through the first exact decision. The reserve stays separate from the final holdout.

The primary guard returns to the start only when the start wins the paired panel. A tie keeps the final prompt. The comparison guard requires a measured gain to keep a changed prompt, matching the direction of the earlier independent guard. CPO receives both policies. Both official GEPA modes at cap 52 receive the same primary guard as an additional control and retain their original unguarded results. [Earlier independent guard](prompt-episode-guard.md) · [Runner](../benchmarks/reserved_regression_guard.py)

## Results

Each cell gives final holdout passes and paid lookups, including the guard.

| Method | Llama and Mistral | Gemma and Flan |
| --- | ---: | ---: |
| Original CPO route | 17,724 / 49,330 | 17,435 / 35,496 |
| CPO, rollback on strict loss | 17,721 / 50,513 | 17,419 / 36,772 |
| CPO, require a strict upgrade | 17,682 / 50,516 | 17,411 / 36,774 |
| Batched GEPA | 17,694 / 57,271 | 17,422 / 40,184 |
| Batched GEPA, rollback on strict loss | 17,680 / 57,968 | 17,412 / 40,684 |
| Sequential GEPA | 17,721 / 81,537 | 17,409 / 60,951 |
| Sequential GEPA, rollback on strict loss | 17,716 / 82,606 | 17,403 / 61,737 |

The schedule left at least four unused cases in 700 of 896 episodes. CPO changed its final prompt from the start in 229 episodes, of which 175 had enough available cases for a guard. The loss-only guard made 31 rollbacks, improving 11 episodes, harming 18, and tying two. It matched GEPA again in 20 of the 109 audited losses where retaining the start was sufficient. It lost 19 net passes and spent 2,459 more lookups across the two cohorts. Requiring a strict upgrade recovered 74 of those comparisons and lost 66 net passes. The recovery count considers each GEPA control separately. [Panel totals and reserved case IDs](reserved-regression-guard-results-v1.json)

Against unguarded cap-52 GEPA, the loss-only arm had joint paired ranges of −62 to +57 and −48 to +39. It saved 11.8% and 8.5% compared with batched GEPA, respectively. The first cohort’s gate was inconclusive and the second fell short of the 10% savings requirement. Giving the same guard to GEPA left joint paired ranges of −50 to +60 and −37 to +46. The loss-only guard stays an experimental comparison. Fresh-model performance remains unverified.

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Two source-export replays matched byte for byte with sockets and DNS blocked. Both reproduced 84 published control traces and counted all guard replies within the original episode allowance. Four focused tests checked the reserve, budget admission, exact loss, and ties. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 12.6 GiB free. The 20.6 MB temporary overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_reserved_regression_guard.py) · [Verification receipt](reserved-regression-guard-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.reserved_regression_guard \
  --execute 31ab7bb0f7d58e491986fae9490529418b972d402d45124e7fbefc26eee8385c \
  --out NEW_REPORT.json
```
