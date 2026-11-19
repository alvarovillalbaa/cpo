# Defer incumbent validation in the first-gain screen

`select_with_lazy_incumbent` finds an incumbent miss, then starts screening challengers. It reads more incumbent cases only when it needs another miss or needs to settle the finalist's certificate. If the screen finds no nominee, unseen incumbent cases cannot change the selection. The selector still reserves the complete incumbent panel and the finalist's validation suffix when deciding how many challengers it can screen. Every lookup saved stays out of the search budget. [Selector](../cpo/lazy_incumbent.py)

```python
from cpo.lazy_incumbent import select_with_lazy_incumbent

selection = select_with_lazy_incumbent(
    incumbent, challengers, validation_rows, evaluate, metric_limit=52,
)
```

The callback supplies exact boolean outcomes through `Observation`. Use deterministic outcomes or a replay with fixed replies when comparing with the eager screen. Evaluation order can affect stochastic replies. The selector preserves a strict validation gain and critical incumbent passes. It returns the selected prompt, the attempted finalist, and the number of actual callback calls. Use separate qualification cases before promoting a finalist.

## Recorded comparison

The replay compares the opt-in selector with eager first-gain and eager rotation. An additional rotation arm uses the paired proof to settle a strict scalar gain while preserving critical passes. Every cycle keeps the same nominee, selected prompt, archive decisions, and qualification replies as its eager reference. The four-cycle schedules use 12 validation cases at a cap of 52 with independent eight-case qualification. The ordinary sequential and batched GEPA controls use their published decisions and costs. [Rotation benchmark](prompteval-coverage-rotation.md) · [Paired proof](paired-qualification.md)

| Policy | Final holdout passes | Paid lookups | Panels meeting both GEPA gates |
| --- | ---: | ---: | ---: |
| Eager first-gain | 18,791 | 66,481 | 4 / 18 |
| Deferred first-gain | 18,791 | 53,149 | 7 / 18 |
| Eager rotation | 18,845 | 74,069 | 0 / 18 |
| Deferred rotation | 18,845 | 74,069 | 0 / 18 |
| Rotation with paired proof | 18,845 | 74,906 | 0 / 18 |
| Sequential GEPA | 18,830 | 95,895 | — |
| Batched GEPA | 18,860 | 67,971 | — |

Deferred first-gain saved **13,332 lookups (20.1%)** against its eager reference. All savings came from incumbent cases, spread across 1,444 cycles. It used 21.8% fewer lookups than batched GEPA while finishing 69 passes lower. It used 44.6% fewer lookups than sequential GEPA while finishing 39 passes lower.

The original rotation schedule required every incumbent lookup under the eager proof order. The paired rotation proof skipped 365 incumbent lookups and added 1,202 challenger lookups, for a net increase of 837. That leaves the cost of broader coverage open. [Sealed per-panel results](prompteval-lazy-incumbent-results-v1.json)

A follow-up capped extra reads during screening. The two-read policy recovered 61 passes and met both GEPA gates on 10 of 18 panels. [Bounded discovery replay](prompteval-bounded-discovery.md)

Each panel requires at least as many holdout passes at equal or lower cost against both controls. A pass tie requires at least 10% savings. The episodes reuse recorded outcomes and final holdout cases. These measurements cover callback lookups on archived prompts. Two offline executions of each phase produced byte-identical reports.

## Reproduce

Use pinned GEPA 0.1.4. Preview to obtain the phase seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_lazy_incumbent --phase finalist-transfer
```

The other phases are `development` and `retrospective-transfer`.
