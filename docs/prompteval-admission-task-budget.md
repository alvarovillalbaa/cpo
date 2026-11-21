# Stress the one-admission result with task-specific budgets

CPO retained a **118-pass lead** over the strongest measured GEPA allocation at the same 68,125-lookup ceiling. GEPA could choose a different setting for each archived task with full knowledge of its holdout outcomes. Its cheapest hindsight allocation to reach CPO's score used **5,267 more lookups**. [Sealed results](prompteval-admission-task-budget-results-v1.json) · [Runner](../benchmarks/prompteval_admission_task_budget.py)

The analysis joins the matched-admission and narrower-validation receipts on all 44 BBH and LMentry model panels and checks every repeated score and cost. Each allocation keeps both models of each task together. The 22 tasks have equal holdout denominators, with 42,240 scored decisions in total. The integer frontier computes both the maximum score within the fixed CPO budget and the lowest cost to reach the fixed CPO score. Retaining the starting prompt is available at zero lookups. [Matched controls](prompteval-matched-admission-attempt.md) · [Narrow validation controls](prompteval-narrow-native-admission.md)

| Choice of settings | Best within 68,125 lookups | Cheapest to reach 16,887 passes |
| --- | ---: | ---: |
| Fixed CPO, one admission | 16,887 passes / 68,125 lookups | 16,887 / 68,125 |
| Native GEPA, limits of one admission | 16,720 / 68,114 | 16,887 / 79,423 |
| Native GEPA, including unrestricted settings | 16,769 / 68,039 | 16,888 / 73,392 |
| CPO, including unrestricted settings | 17,228 / 67,766 | 16,892 / 58,041 |
| Combined CPO and GEPA menu | 17,296 / 68,111 | 16,890 / 55,689 |

The task-specific native allocation closed most of the 804-pass gap against the best fixed affordable GEPA setting. CPO's own hindsight allocation found 341 more passes than fixed one-admission CPO at slightly lower cost. That allocation retained the start on five tasks, ran unrestricted CPO on five, and kept the one-attempt limit on 12. These allocations use target holdout scores and realized costs.

The held-out routing rules instead choose from costs and scores of completed training tasks. The target task and both its model panels are excluded from each fit. Each split uses either all other tasks, the other tasks in the same benchmark, or the other benchmark alone. A setting must fit the training tasks' mean relative CPO cost. The best eligible setting is then measured on the omitted task. In all three splits the native menu chose eight-anchor batched GEPA at cap 32 for every task, and every menu that included CPO chose fixed one-admission CPO. These archived folds leave the hindsight savings unexplained by any of the tested routing rules. [Held-out routing method](task-budget-selection.md)

## Reproduce

Use Python 3.12 and the repository's sealed receipts. The analysis ran with sockets and DNS blocked and made zero provider requests. Storage Guard measured 5.1 GiB free. A disposable source export was bounded at 0.2 GiB under the standing LAB exception. [Exhaustive frontier test](../tests/unit/test_prompteval_admission_task_budget.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_admission_task_budget
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_admission_task_budget \
  --execute 18c8c5c5754b28de6d00ae365c8a9ff8bf1215861231b74ebe0f78e72284f235 \
  --out NEW_REPORT.json
```

The results SHA-256 is `c2afffab0fd35fab5a2b18481b11c9ae5aaa4d2dc26a8626c4072d0e6b3a1ea1`. Fresh-model performance remains unverified.
