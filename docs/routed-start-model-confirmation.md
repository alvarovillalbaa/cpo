# Confirm the starting-prompt policy on unused model splits

This study fixes the CPO candidate that widens on a third incumbent miss, requires nonnegative gain in both qualification halves before leaving the start, and reserves the start's archive check for the last cycle. The candidate improved the earlier model-transfer score by six passes and saved 577 lookups relative to the same route. It lost passes on both earlier cohorts. The confirmation also runs the route with ordinary qualification and archive policy, the seeded CPO control, and both official GEPA 0.1.4 modes. [Starting-prompt study](routed-start-protection.md)

The archived model splits are Llama 3 8B Instruct and Mistral 7B v0.1. Neither split appeared in the local MMLU correctness inventory. The eight subjects were outside the recent routing pilot and model-transfer cohorts. Their subject matter appeared in older experiments with other models. Before fetching the selected correctness files, the design fixed all 16 Parquet object IDs and sizes at one dataset revision. [Frozen design](routed-start-model-confirmation-design-v1.json) · [PromptEval correctness archive](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness)

Each panel receives the original 32 seeded four-cycle episodes, prompt and case schedules, 12 validation cases, eight independent qualification cases per cycle, and disjoint final holdout. The primary GEPA controls use paid search cap 52. The primary gate requires at least 10% lookup savings against both controls and a nonnegative lower endpoint for the central 95% paired range of the smaller pass difference. Each of 4,096 draws resamples cases within subjects, keeping both models and all trajectories paired. The secondary cost comparison sweeps both GEPA modes at every integer cap from 20 through 68 and reselects the best affordable fixed control per draw. Lookup cost includes distinct search evaluations and qualification replies. [Capture and replay runner](../benchmarks/routed_start_model_confirmation.py)

## Results

The design was published in commit `1129c8a1a2706febbe9a2c7312f800b3f4387697` before the correctness files were fetched. The 421 distinct holdout cases produced 26,944 paired outcomes per arm across the model panels and seeds. [Published design commit](https://github.com/alvarovillalbaa/cpo/commit/1129c8a1a2706febbe9a2c7312f800b3f4387697)

| Setting | Holdout passes | Paid lookups |
| --- | ---: | ---: |
| Retain start | 17,617 | 0 |
| Seeded CPO | 17,708 | 47,065 |
| Ordinary third-miss route | 17,724 | 50,245 |
| CPO with split qualification and final reserve | 17,724 | 49,330 |
| Batched GEPA, cap 52 | 17,694 | 57,271 |
| Sequential GEPA, cap 52 | 17,721 | 81,537 |
| Best affordable fixed GEPA, batched cap 47 | 17,687 | 45,679 |
| Cheapest fixed GEPA reaching the candidate score, sequential cap 47 | 17,727 | 73,050 |
| Subject-specific GEPA with hindsight within candidate cost | 17,767 | 47,402 |

CPO gained **30 passes with 13.9% fewer lookups** against batched GEPA at cap 52. It gained **three passes with 39.5% fewer lookups** against sequential GEPA at cap 52. The joint paired range was **−55 to +58 passes**, so the frozen gate was **inconclusive**. The modification matched the ordinary route's score and saved 915 lookups. Its paired range against the ordinary route was −25 to +26 passes. [Full results and per-panel receipts](routed-start-model-confirmation-results-v1.json)

The candidate led the best affordable fixed setting by 37 passes at the observed totals. The range against the reselected affordable setting was −22 to +88. Dropping high-school psychology removed the 37-pass lead, and the two model splits differed by −1 and +38 passes from that fixed control. The subject-specific comparison could choose a setting or retain the start with hindsight on each subject, and led CPO by 43 passes within its lookup budget. This replay measures transfer to new archived model splits on familiar subjects. Fresh proposal quality and provider charges remain unverified.

A follow-up traced the losing episodes and tested whether exact validation ties could earn independent qualification within the original search cap. [Witnessed validation ties](routed-validation-ties.md)

## Reproduce

Use pinned GEPA 0.1.4. The reduced correctness snapshot supplies all replay inputs. To reproduce capture from the source objects, use DuckDB 1.4.3 in a temporary environment and run `--capture` with the same seal and a fresh snapshot path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.routed_start_model_confirmation --design
PYTHONHASHSEED=0 python -B -m benchmarks.routed_start_model_confirmation \
  --replay benchmarks/data/routed-start-model-confirmation-v1.json \
  --execute eb4046ef1af6ba30fe28ef37aaa06a53801cb41c800f95d587521d3f822544ea \
  --out NEW_REPORT.json
```

Two captures matched byte for byte after verifying all 16 pinned Git objects. A separate check verified that the search, qualification, and holdout cases were disjoint across all 512 schedules and that the captured model IDs were absent from the prior local data files. Two source-export replays matched byte for byte with sockets and DNS blocked. Five focused tests passed. The CLI rejected an incorrect seal and preserved an existing report when given its path. Storage Guard measured 15.0 GiB free. The hash-verified temporary decoder and 54.2 MB scratch overlay were removed under the standing LAB exception. [Reduced correctness snapshot](../benchmarks/data/routed-start-model-confirmation-v1.json)
