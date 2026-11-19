# Match CPO and GEPA by realized cost on the new MMLU panels

A shared search ceiling leaves the methods with different paid costs. This replay runs official sequential and batched GEPA 0.1.4 at every integer paid search ceiling from 20 through 68 on the eight previously captured MMLU panels. It also runs seeded CPO at five logical ceilings and replays the published wider schedules at their original ceiling of 52. Each optimizer keeps the same starting prompt, proposal roster, separate qualification cases, episode-local cache, and holdout. [Independent transfer](independent-mmlu-transfer.md) · [Wider schedules](single-wide-cycle.md)

Search costs count distinct paid lookups. Qualification costs include archive checks and independent qualification through the decisive reply. Each GEPA proposal requires its original full-round reserve. The replay verifies all original cap-52 control traces and costs and every wider CPO trace. [Paid-search implementation](gepa-paid-cap-transfer.md) · [Runner](../benchmarks/independent_mmlu_cost_frontier.py)

For each realized CPO cost, the fixed comparison selects the highest-scoring measured GEPA method and ceiling affordable across all eight panels. The task-specific comparison can choose a different setting for each subject, shared by its two model panels, or retain the starting prompts for zero cost. Both comparisons use holdout results after replay and measure hindsight bounds over the tested settings. They do not estimate a deployable cap-selection rule. The holdout cases recur across seeds.

## Results

Each cell shows holdout passes and paid lookups across all eight panels.

| CPO setting | CPO | Best affordable fixed GEPA | GEPA task-specific hindsight |
| --- | ---: | ---: | ---: |
| Seeded, cap 28 | 8,963 / 14,084 | 8,920 / 11,884 | 8,973 / 13,711 |
| Seeded, cap 36 | 8,967 / 20,861 | 8,966 / 20,701 | 9,001 / 20,719 |
| Seeded, cap 40 | 8,971 / 21,271 | 8,966 / 20,701 | 9,004 / 21,006 |
| Seeded, cap 44 or 52 | 8,971 / 21,477 | 8,975 / 21,282 | 9,004 / 21,006 |
| Final with credit | 8,978 / 23,868 | 8,979 / 23,420 | 9,015 / 22,766 |
| Late at start | 8,980 / 26,730 | 8,988 / 26,730 | 9,020 / 25,415 |
| Wide in the final cycle | 8,975 / 27,244 | 8,988 / 26,730 | 9,023 / 26,949 |
| Wide in the first cycle | 8,984 / 28,012 | 8,988 / 26,730 | 9,023 / 26,949 |
| Wide in every fresh cycle | 9,009 / 44,447 | 9,000 / 43,277 | 9,044 / 36,453 |

The largest CPO lead against a single affordable fixed setting was 43 passes at cap 28. The cheapest fixed GEPA setting to match that score was sequential at cap 31, scoring 8,966 for 20,701 lookups. CPO used 32.0% fewer lookups against that score-matched point. At the default CPO setting, batched GEPA at cap 44 scored four more passes and used 195 fewer lookups. This lower ceiling improves the comparison available from the original cap-52 transfer.

For the late-at-start variant, batched GEPA at cap 48 matched its score at 2,703 fewer lookups, and cap 51 gained eight passes at exactly the same realized cost. Task-specific GEPA hindsight scored more passes within every CPO budget. Its low-budget allocation used batched GEPA on nutrition, sequential GEPA on machine learning, and retained the starts on both other subjects.

Both offline executions produced byte-identical reports across 784 GEPA model-panel settings. The results describe recorded prompt selection. Fresh-prompt superiority and actual provider cost remain unverified. [Sealed full points, trace hashes, and task allocations](independent-mmlu-cost-frontier-results-v1.json)

A follow-up tested whether a shorter strict validation proof improves CPO's low-budget results. [Minimum-proof search](minimum-proof-budget.md)

## Reproduce

Use GEPA 0.1.4. Preview the seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`. The packaged archive supplies all inputs.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.independent_mmlu_cost_frontier
```
