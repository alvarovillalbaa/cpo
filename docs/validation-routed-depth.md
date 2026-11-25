# Limit uniform validation depth on two-challenger CPO rosters

The earlier roster-width replay found that uniform validation could buy six cases on a two-challenger roster and two cases on an eight-challenger roster. Routing added 7,076 lookups over settled CPO at the smaller width. This benchmark tests capping uniform validation at two or four cases on two-challenger cycles. Throughout the replay, halving, critical validation panels, the opening probes, and independent qualification use their existing rules. The benchmark runs outside the optimizer package. [Width analysis](validation-routed-roster-width.md) · [Benchmark](../benchmarks/validation_routed_depth.py) · [Sealed results](validation-routed-depth-v1.json)

Each cell shows held-out passes and paid lookups. The 2,048 language episodes use the same BBH, LMentry, and MMLU panels as the width replay. Some cohorts reuse cases, so the language total describes this recorded mix. The 64 Promptolution episodes use the original GSM8K and SST5 holdouts. All recorded baseline totals reproduced. [Promptolution comparison](validation-routed-promptolution.md)

| Suite | Settled CPO | Uncapped routed CPO | Two-case cap | Four-case cap |
| --- | ---: | ---: | ---: | ---: |
| Language mix | 52,396 / 71,741 | 52,566 / 78,817 | 52,213 / 41,588 | 52,482 / 60,623 |
| Promptolution GSM8K | 2,472 / 906 | 2,440 / 850 | 2,379 / 628 | 2,404 / 728 |
| Promptolution SST5 | 1,452 / 1,549 | 1,439 / 1,598 | 1,368 / 793 | 1,434 / 1,229 |
| Promptolution total | 3,924 / 2,455 | 3,879 / 2,448 | 3,747 / 1,421 | 3,838 / 1,957 |

The four-case cap saved 11,118 lookups and gained 86 passes over settled CPO on the language mix. Compared with uncapped routing, it saved 18,194 lookups and lost 84 passes. The largest losses were 79 passes in bounded LMentry and 44 in tie LMentry. Their paired 95% case-bootstrap ranges against uncapped routing were −111 to −47 and −61 to −26 passes. Against settled CPO, both LMentry ranges included zero. The two-case cap recorded fewer passes than settled CPO in both LMentry cohorts, with paired ranges of −156 to −48 and −72 to −17 passes.

On the pooled Promptolution replay, the four-case cap used 498 fewer lookups than settled CPO and lost 86 passes. The paired 95% range was −2.12 to −0.89 percentage points. At each capped policy's budget, the strongest affordable control across both tasks was a halving setting. The two-case cap gained 79 passes with 153 additional lookups over that control, and the four-case cap gained 120 passes with 409 additional lookups. The paired ranges were +0.50 to +2.19 and +1.27 to +2.92 percentage points. The strongest affordable native GEPA setting recorded 3,345 passes at 1,331 lookups for both budgets. The receipt also reports matched controls and paired differences for each cohort and task.

Both caps reduced lookup cost and gave up some of the uncapped LMentry gains. They also reduced Promptolution accuracy relative to settled CPO. The caps are benchmark variants. Fresh-model performance remains unverified.

## Reproduce offline

Use Python 3.12, the pinned GEPA 0.1.4 wheel, and the archived Promptolution corpus identified in the previous comparison. Running the benchmark without arguments previews its seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.validation_routed_depth \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute 6d64a37a872b89444f747827fa98c81e917292893840e53f96f929ba9bc7d9ae \
  --out NEW_REPORT.json
```

Three socket-blocked replays agreed on all measured fields. The final plan explicitly names the four measured arms and the two-challenger width. All 39 focused tests passed. Additional checks exercised critical-row, wider-roster and halving behavior, and the CLI refused a stale seal and an existing output. The replay sent zero provider requests. Storage Guard measured 9.1 GiB free before the experiment. The isolated source export, pinned GEPA overlay, and publication worktree used 123 MiB under the standing LAB exception. [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
