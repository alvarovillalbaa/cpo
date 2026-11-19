# Choose an optimizer setting without seeing the target task's outcomes

The paid-budget frontier let GEPA choose its method and cap with knowledge of the target task's holdout results. This study tests a selection rule that sees only completed training tasks. It uses the 16 archived tasks and their 32 model panels. Every fold excludes both model panels for the target task and chooses one setting for both. [Paid-budget frontier](paid-budget-frontier.md)

The selector ranks settings by mean task accuracy on the training tasks. It divides each task's passes by its possible passes so large panels carry the same weight as smaller ones. It keeps settings whose mean training cost relative to the reference CPO setting is at most one. It breaks score ties by lower relative cost. The target task's cost is measured after selection.

The menus contain CPO settings, official GEPA settings, and both. The CPO menu includes the published first-gain cap ladder, the three archive variants, and bounded two-read at their previously measured cap. The GEPA menu includes both official search modes at every measured ceiling. The primary folds use other tasks from the same benchmark. Two further splits use all other tasks or exclude the target's entire cohort.

The replay also computes a hindsight bound for each menu at the original aggregate CPO cost. The bound can choose separately for each task after seeing its outcomes. The fold tests exclude target outcomes from the choice step, while all menus and outcomes come from previously inspected archives. They measure retrospective selection transfer. [Replay runner](../benchmarks/task_budget_selection.py)

A follow-up tests screen choice from earlier searches on the same incumbent. [Episode-based screen selection](episode-screen-adaptation.md)

## Results

Each cell shows holdout passes and paid lookups across the 16 held-out tasks.

| Training split | CPO menu | GEPA menu | Mixed menu |
| --- | ---: | ---: | ---: |
| Other tasks in the same benchmark | 21,014 / 94,924 | 20,295 / 86,659 | 20,996 / 95,579 |
| All other tasks | 21,007 / 95,696 | 20,315 / 91,363 | 21,007 / 95,696 |
| Other cohorts only | 20,976 / 97,544 | 20,315 / 91,363 | 20,976 / 97,544 |

The primary CPO selector used 6,110 fewer lookups and finished nine passes lower than the fixed CPO reference of 21,023 passes at 101,034 lookups. It gained passes on three tasks, tied on four, and lost passes on nine. It spent less on 13 tasks and tied the reference cost on three. The broader training splits lost more passes, and the mixed menu produced no improvement over the CPO menu in these splits.

The GEPA selector trained on all other tasks or other cohorts picked the same batched setting with ceiling 44 for all 16 targets. Same-benchmark selection used 4,704 fewer lookups and finished 20 passes lower than that setting. It recovered none of the previously measured GEPA accuracy gain from hindsight.

With hindsight at the fixed CPO budget, the expanded CPO menu can score 21,171 passes at 94,395 lookups. The GEPA bound reproduces 21,182 at 100,995, and the mixed bound reaches 21,345 at 100,985. The difference between those bounds and the held-out selectors leaves the value of a deployable task-specific rule unverified. Two offline runs reproduced the report byte for byte. [Sealed folds, scores, and allocations](task-budget-selection-results-v1.json)

## Reproduce

Preview the plan to obtain the seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`. This replay reads sealed results from the earlier experiments.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.task_budget_selection
```
