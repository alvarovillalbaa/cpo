# Allocate validation lookups using the scores already paid for

The earlier comparison tested scored history and a demonstration grid with scripted evaluations. This replay asks whether a probability-guided allocation helps CPO choose from recorded AIME and ARC-AGI prompt pools under tighter budgets. Every trial uses eight seeded challengers, a rotated incumbent, and the original disjoint training, validation, qualification, and holdout cases. Search caps are 36 and 52 lookups. [Scripted alternatives](alternative-controls.md) · [Recorded outcome sources](recorded-math-validation-ties.md)

## Protocol

- **Strict CPO** races candidates in roster order with exact bounds and adaptive rejection.
- **Full-score history** reads complete validation panels in roster order and retains the strongest exact score so far. It tests the cost of complete scores when the prompt pool is fixed.
- **Successive Halving** extends the shared validation prefix for surviving prompts. Its finalist can have partial validation evidence.
- **Posterior allocation** starts each prompt at a uniform beta prior and updates it with its paid validation replies. It chooses the eligible prompt with the greatest estimated probability of reaching the current validation target. Fewer unread cases and roster order break ties. Among that prompt’s cases, it reads protected critical cases first and then cases with the lowest smoothed observed pass rates. It funds a read only when it could finish the candidate’s panel with the remaining budget. The exact completed score and critical-passage checks determine which nominee advances.
- **Sequential and batched GEPA** use the official 0.1.4 adapter and the shared roster. Their own search can spend on the supplied training cohort.

Every search arm receives the same paid incumbent qualification precheck and can nominate one challenger for independent qualification. Retaining the starting prompt supplies a zero-lookup control. This replay isolates allocation and ranking over a fixed pool. The scored-history control is inspired by OPRO, and the probability-guided policy tests a simple model-based allocation mechanism. The joint demonstration search and proposal stages of MIPROv2 remain separate. [Benchmark runner](../benchmarks/recorded_score_allocation.py)

## Results

Each cell reports holdout passes / total paid lookups, including qualification. The 40 seeds provide 360 paired trials per cap on ARC and 320 on AIME. Paired ranges resample the original held-out case IDs and keep every occurrence of each case together.

| Method | ARC, cap 36 | ARC, cap 52 | AIME, cap 36 | AIME, cap 52 |
| --- | ---: | ---: | ---: | ---: |
| Retain start | 12,944 / 0 | 12,944 / 0 | 4,056 / 0 | 4,056 / 0 |
| Strict CPO | 13,915 / 8,039 | 13,932 / 8,422 | 4,007 / 10,260 | 4,002 / 10,959 |
| Full-score history | 13,839 / 9,002 | 13,890 / 11,752 | 4,030 / 12,215 | 4,023 / 15,643 |
| Successive Halving | 13,862 / 9,885 | 13,898 / 11,227 | 4,045 / 9,374 | 4,036 / 10,271 |
| Posterior allocation | 13,952 / 7,976 | 13,932 / 8,128 | 4,001 / 10,275 | 4,002 / 10,777 |
| Batched GEPA | 13,641 / 6,045 | 13,744 / 9,517 | 4,066 / 7,437 | 4,065 / 12,211 |
| Sequential GEPA | 13,768 / 8,385 | 13,789 / 11,169 | 4,079 / 9,970 | 4,074 / 13,376 |

At cap 52 on ARC, posterior allocation matched strict CPO’s score and used 294 fewer lookups. It scored 188 more passes than batched GEPA and 143 more than sequential GEPA, with 14.6% and 27.2% fewer lookups. Its recorded evaluator cost was lower than both GEPA controls and its joint paired range was +53 to +237, clearing the archived gate. It also scored higher than full-score history and Successive Halving with fewer lookups. At cap 36, it scored 37 passes above strict CPO with 63 fewer lookups. Its recorded evaluator cost was 0.2% higher than strict CPO’s. It used 31.9% more lookups than batched GEPA and missed the cost requirement.

At both AIME caps, posterior allocation lost held-out passes to both GEPA controls. Successive Halving also beat it on passes and paid lookups at both caps. At 52 lookups, the posterior policy saved 11.7% against batched GEPA and 19.4% against sequential GEPA while the joint paired range was −116 to −34 passes. The ARC result establishes a useful allocation improvement on the recorded pool. The same rule does not address AIME’s quality gap. [Full ranges and historical ARC costs](recorded-score-allocation-results-v1.json)

The follow-up compared the same allocator with the original wider screen on a four-cycle archived MMLU schedule. [MMLU allocation transfer](routed-score-allocation.md)

## Reproduce

Use GEPA 0.1.4 and the bundled archives.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_score_allocation
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_score_allocation \
  --execute 66cb2e3592d55e6177bfffdf9f1ceda64aae77c9d9a4338428512fb9e9d10bcd \
  --out NEW_REPORT.json
```

Two source-export replays matched byte for byte with sockets and DNS blocked. Six focused tests passed, including all 512 three-prompt by three-case binary matrices with a funded search. Those cases verified exact ranking, roster-order ties, and protection of critical incumbent passes. The CLI rejected a wrong seal and refused to overwrite a report. Storage Guard measured 20.6 GiB free. The 15.6 MB temporary overlay was removed under the standing LAB exception. Fresh-model performance remains unverified. [Focused tests](../tests/unit/test_recorded_score_allocation.py)
