# Screen a fixed prompt pool for one finalist

`select_single_finalist` measures the incumbent on the validation panel, screens the supplied challengers, and reserves enough calls for one finalist. The finalist needs a strict exact gain and must preserve every validation case marked critical that the incumbent passed. The selector reuses the finalist's screening replies in its certificate. Use separate qualification cases before promoting the result. [Selector](../cpo/single_finalist.py) · [Paired qualification](paired-qualification.md)

| Screen | Nomination rule |
| --- | --- |
| `ordered` | Evaluate every challenger on the first validation case. A shared second probe can resolve a tie when the remaining budget can still fund the finalist. |
| `gain-first` | Use cases the incumbent failed first, with the same full screen and tie probe. |
| `first-gain` | Screen in proposal order and nominate the first challenger that passes an incumbent miss. |

```python
from cpo.single_finalist import select_single_finalist

selection = select_single_finalist(
    incumbent, archived_challengers, validation_rows, evaluate,
    metric_limit=52, screen="first-gain",
)
```

`selection.prompt` is either the certified validation finalist or the incumbent. `selection.finalist` identifies the attempted challenger when there was one. `selection.evaluations` counts the actual callback calls.

## Offline comparison

The replay uses the same six PromptEval panels, 12 validation cases, 52-lookup cap, and archive policy as the frozen transfer. Any archive lookup costs are deducted first. The three variants change only CPO's selection among the supplied fresh candidates. The final qualification cases and both official GEPA control traces remain identical. [Source transfer](prompteval-validation-transfer.md)

| Policy | Final holdout passes | Paid lookups | Panels meeting both GEPA gates |
| --- | ---: | ---: | ---: |
| Prior CPO policy | 4,479 | 40,203 | 0 / 6 |
| Sequential GEPA | 4,483 | 31,157 | — |
| Batched GEPA | 4,466 | 22,028 | — |
| CPO, ordered | 4,465 | 34,126 | 0 / 6 |
| CPO, gain-first | 4,464 | 34,430 | 0 / 6 |
| CPO, first-gain | 4,455 | 21,833 | 1 / 6 |

First-gain used 18,370 fewer lookups (45.7%) than the prior CPO policy and finished 24 passes lower. It used 195 fewer lookups than batched GEPA in aggregate and finished 11 passes lower. Llama high-school computer science was the only panel where it improved on both GEPA controls at lower cost. The two full-screen variants saved lookups relative to prior CPO and exceeded both GEPA controls' costs on every panel.

The aggregate sums are descriptive. Each panel must match or exceed each control's final passes at equal or lower cost, and a score tie requires at least 10% savings. The panels reuse recorded outcomes, subjects, and fixed holdout cases from the prior transfer. The result supports keeping this selector opt-in. Two offline executions produced identical reports. [Sealed results](prompteval-single-finalist-results-v1.json)

A follow-up tested a second certificate after a failed first-gain screen. All three retry policies spent more lookups, and aggregate holdout accuracy tied or fell. [Finalist retry replay](prompteval-finalist-retry.md)

A replay across 18 panels used earlier paid outcomes to pick the first-gain witness. The two rules gained six and 17 aggregate passes and added paid lookups. [Paid witness replay](prompteval-paid-witness.md)

## Reproduce

Use pinned GEPA 0.1.4. Preview to obtain the seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_single_finalist
```
