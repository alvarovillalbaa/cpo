# Cap the cost of discovering more screening cases

Deferred first-gain saves incumbent lookups by screening on the first missed case. Full rotation uses more misses and can spend the entire incumbent panel even when it finds no nominee. This replay tests a middle ground. After finding the first miss, the screen can read a bounded number of extra incumbent cases. It rotates among whichever misses those reads uncover and still probes each visited challenger once. [Deferred first-gain](lazy-incumbent.md) · [Full rotation](prompteval-coverage-rotation.md)

| Policy | Challenger screen |
| --- | --- |
| Two reads | Share the first miss with the first challenger, then spend up to two extra incumbent reads on discovery. |
| Four reads | Apply the same rule with up to four extra incumbent reads. |
| Two reads after four | Share the first miss with the first four challengers, then allow up to two extra incumbent reads. |

The discovery cap applies during screening. After a challenger passes its assigned miss, the selector can complete the incumbent panel and attempts only that finalist. The logical search budget reserves a full incumbent panel and the finalist suffix. A certified finalist requires a strict validation gain and must preserve all incumbent critical passes. Independent qualification still determines promotion.

The 18-panel replay preserves the four-cycle schedule, the 12 validation cases and 52-lookup search cap, the archive policy, and the eight independent qualification cases per cycle. It reproduces the archived deferred first-gain trace and the measured sequential and batched GEPA totals. [Benchmark runner](../benchmarks/prompteval_bounded_discovery.py)

## Results

Each cell reports final holdout passes and paid lookups. The last column counts panels meeting both GEPA gates.

| Policy | Development | Finalist transfer | Retrospective transfer | Both GEPA gates |
| --- | ---: | ---: | ---: | ---: |
| Deferred first-gain | 4,149 / 11,804 | 4,455 / 17,179 | 10,187 / 24,166 | 7 / 18 |
| Two reads | 4,151 / 13,418 | 4,449 / 19,517 | 10,252 / 27,384 | 10 / 18 |
| Four reads | 4,147 / 14,568 | 4,451 / 21,348 | 10,246 / 29,911 | 2 / 18 |
| Two reads after four | 4,161 / 13,637 | 4,462 / 20,005 | 10,212 / 27,679 | 8 / 18 |
| Sequential GEPA | 4,128 / 21,574 | 4,483 / 31,157 | 10,219 / 43,164 | — |
| Batched GEPA | 4,150 / 15,311 | 4,466 / 22,028 | 10,244 / 30,632 | — |

The two-read policy gained **61 passes** and spent 7,170 extra lookups relative to deferred first-gain. It gained passes on nine panels and lost passes on seven. Across all panels it finished 22 passes ahead of sequential GEPA and eight short of batched GEPA. It used **11.3% fewer lookups than batched GEPA**. On retrospective transfer it outscored both controls and used fewer lookups than either. Compared with full rotation on the same panels, the two-read policy gained seven aggregate passes and saved 13,750 lookups.

A panel must match or exceed the score of each control at equal or lower cost. A score tie requires at least 10% savings. The policy and alternate settings were fixed before replay. All three phases reproduced byte for byte across two offline runs. They reuse recorded outcomes and final holdout cases across seeds, so fresh model-backed results remain open. [Sealed panel results](prompteval-bounded-discovery-results-v1.json)

## Use the selector

The optional selector defaults to the two-read policy. It reports the attempted finalist, the selected prompt, and the count of actual callback lookups. Use a separate qualification panel before promoting a finalist.

```python
from cpo.bounded_discovery import select_with_bounded_discovery

selection = select_with_bounded_discovery(
    incumbent, challengers, validation_rows, evaluate, metric_limit=52,
)
```

## Reproduce

Use pinned GEPA 0.1.4. Preview each phase, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_bounded_discovery --phase finalist-transfer
```

The other phases are `development` and `retrospective-transfer`.
