# Choose a first-gain case from cached validation replies

Fresh candidate pools contain different prompts in every cycle, while validation cases can recur. This experiment tests whether CPO can identify a better first-gain case from the earlier replies it already has. A previous witness study evaluated the incumbent on all current validation cases before choosing a failure. This study uses deferred first-gain and makes the choice before the current search sends a request. [Earlier witness study](prompteval-paid-witness.md)

The three cache policies require a current validation case with a recorded failure by the current incumbent on the same case. The known-miss rule takes the first eligible case. The other two require at least one or two passes, respectively, by distinct non-incumbent prompts. They choose the highest smoothed pass rate among eligible cases, adding one pass and one failure. Ties retain the seeded order. The chosen row moves to the front and the other rows keep their order. With no eligible case, the whole panel keeps its seeded order.

Each arm starts with an empty history and records only its own earlier fresh validation callbacks. Repeated prompt and case pairs contribute one observation. Qualification and holdout cases stay outside the history. The recency archive, candidate order, search ceiling, and independent qualification panel are shared. A witness choice costs no additional lookups. The resulting search and qualification can use different numbers of calls. [Replay runner](../benchmarks/cached_miss_witness.py)

## Results

| Witness policy | Holdout passes | Paid lookups | Fresh screens reordered | Panels clearing both GEPA gates / 32 |
| --- | ---: | ---: | ---: | ---: |
| Seeded deferred first-gain | 21,023 | 101,034 | 0 | 15 |
| First known miss | 20,950 | 99,364 | 1,353 | 15 |
| At least one earlier pass | 20,982 | 101,424 | 737 | 15 |
| At least two earlier passes | 21,006 | 100,931 | 63 | 17 |

The known-miss rule saved 1,670 lookups and lost 73 passes. Requiring one earlier pass bought more lookups and still lost passes. Requiring two saved 103 lookups and cleared both official GEPA comparisons on two additional BBH panels. It gained on seven episodes, lost on three, and tied on 1,014. Its largest loss was 25 passes on Flan-T5-XXL ends-with-word, which outweighed gains elsewhere. Deferred first-gain keeps the seeded order by default. [Per-panel results and paired episode counts](cached-miss-witness-results-v1.json)

The experiment uses 1,024 four-cycle episodes across 32 archived model-task panels. The seeded control reproduced the published callback trace, cost, and holdout totals on every panel. Both GEPA comparisons use the controls that reinvest cached lookups under the same paid cap. Each phase reproduced byte for byte in two offline executions. These are recorded prompt-pool outcomes. The replay leaves the benefit for fresh prompts and live provider costs unverified. [Static control](fixed-pool-cycle-replay-results-v1.json) · [GEPA controls](gepa-paid-cap-transfer-results-v1.json)

## Reproduce

Use GEPA 0.1.4. Preview the phase seal, then pass `--execute PLAN_SHA256 --out NEW_REPORT.json`. Phases are `mmlu`, `bbh-lmentry`, and `bbh-lmentry-stress`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.cached_miss_witness --phase mmlu
```
