# Search a fresh roster after qualification rejects a finalist

Two-round halving lost 13 GSM8K passes in an episode where rejection in cycle one triggered a skip of cycle two. The packaged feedback policy can apply the same skip after other rejected finalists in its two-pass opening state. This replay replaces that action with a limited search on the fresh roster. The first variant reads the first incumbent validation case. The second reads up to two, stopping at the first miss. When the incumbent misses, at most four challengers can answer that one shared case. A nominee still has to clear the original independent qualification. Critical validation panels retain the incumbent. The validation quote is at most five or six reads, respectively. [Two-round halving replay](promptolution-two-round-halving.md) · [Benchmark](../benchmarks/feedback_rejection_scout.py)

## Archived Promptolution results

| Policy | Held-out passes | Paid lookups |
| --- | ---: | ---: |
| Packaged feedback | 3,885 | 2,348 |
| One-case search | 3,885 | 2,364 |
| First miss within two cases | 3,885 | 2,373 |
| Two-round feedback | 3,872 | 2,360 |
| Two-round feedback with one-case search | 3,872 | 2,382 |
| Two-round feedback with first miss within two cases | 3,885 | 2,400 |

The second-case check recovered all 13 lost passes in GSM8K episode `47139`. The incumbent passed the first validation case in the cycle that had been skipped. The extended search reached the second case, found the miss, and nominated DSPy-GEPA, which passed qualification. The run used 29 lookups in that episode. Packaged feedback reached the same prompt with 23. This episode motivated the intervention, so the recovery is an attribution result. [Episode transitions and budget comparisons](feedback-rejection-scout-v1.json)

## Archived language transfer

Across 2,048 episodes from seven frozen cohorts, one-case search lost one pass and added 371 lookups. The first-miss arm gained eight passes and added 528 lookups. Its only positive change was nine additional bounded-BBH passes, with a paired 95% range of −5 to +23 passes. Tie BBH lost one pass. The other five cohorts tied packaged feedback. The same three cohorts as packaged feedback exceeded the subject-tuned GEPA score bound at their own realized budgets. These cohorts can repeat subjects.

The replays identify how the skip lost a useful prompt, but the replacement searches did not improve the overall cost and score trade-off. The packaged feedback policy keeps its original rule. Live superiority remains unverified.

## Reproduce offline

Use the pinned Promptolution corpus and GEPA 0.1.4 environment. The language fixtures and frozen control receipts are loaded from the repository.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.feedback_rejection_scout \
  --corpus PREDICTIONS.json \
  --execute 33ac3e51a73611c73db4d7695f90f5114e039c6da560287d9448df2b5932f004 \
  --out /tmp/cpo-feedback-rejection-scout.json
```

Two network-disabled replays produced byte-identical receipts. All 91 focused tests passed. The checks covered callback pricing, the first four roster slots, the late critical-case fallback, and unchanged independent qualification. Storage Guard measured 10.4 GiB free. The disposable source, pinned wheel overlay, corpus copy, and publication checkout fit the standing 0.2 GiB LAB exception. Teardown was verified. [Tests](../tests/unit/test_feedback_rejection_scout.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
