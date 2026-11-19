# Stop qualification when the decision is settled

`certify_paired_qualification` keeps the same gate as CPO's full paired cycle. Promotion requires the requested exact gain, nonnegative gain in each task family, and preservation of every incumbent critical pass. The certificate stops once every possible completion of the remaining replies would give the same decision. It keeps the same seeded prompt order and can stop after the first reply in a pair.

```python
from cpo.paired_qualification import certify_paired_qualification

decision = certify_paired_qualification(
    incumbent, challenger, qualification_rows, evaluate_qualification,
    repeats=2, minimum_gain=1, seed=17, evaluation_limit=48,
)
```

The callback receives the prompt, qualification row, and repeat number. It returns a boolean. Choose the qualification rows separately from any search inputs. The result contains the observed prefix and upper and lower bounds on total gain. A budget stop may return `undecided`. Only `promoted` selects the challenger. The existing `run_cycle` entry point continues to collect the full panel.

## Recorded savings

The replay keeps search and any earlier archive qualification fixed on the six transfer panels. The same stopping rules apply to CPO and both GEPA controls. Each reported comparison preserves the original decision and final holdout score. [Source replay](prompteval-validation-transfer.md) · [Per-panel counts and seal](prompteval-qualification-bounds-results-v1.json)

| Method | Full qualification | Stop at a complete pair | Stop after any reply |
| --- | ---: | ---: | ---: |
| CPO | 11,814 | 11,646 | 11,439 |
| Sequential GEPA | 3,103 | 3,052 | 3,007 |
| Batched GEPA | 1,802 | 1,772 | 1,743 |

CPO saved 375 qualification lookups, including 207 from stopping between the two replies of a pair. That cut its combined cost from 40,203 to 39,828, about 0.9%. Sequential and batched GEPA still used fewer lookups. The certificate reduces the cost of a qualification decision while the larger search-cost gap remains.

Exhaustive tests verified the first decisive prefix across every outcome of a small panel with two families, critical cases, two repeats, and several gain thresholds. The PromptEval replay uses binary correctness without critical labels. Both offline runs returned identical reports.

## Reproduce offline

Use pinned GEPA 0.1.4. Preview to obtain the plan seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_qualification_bounds
```

[Library API](../cpo/paired_qualification.py) · [Replay runner](../benchmarks/prompteval_qualification_bounds.py) · [Exhaustive tests](../tests/test_paired_qualification.py)
