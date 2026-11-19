# How sensitive is the fixed-budget CPO lead to the holdout cases?

At cap 28, seeded CPO scored 43 more passes than the strongest fixed GEPA setting affordable within its realized cost. The 15,360 holdout decisions reuse the same 240 cases across both model panels and 32 seeds. This replay measures sensitivity to the case mix without treating those repeated decisions as independent. [Original cost frontier](independent-mmlu-cost-frontier.md)

The runner verifies the published search and qualification traces, costs, and scores for both seeded CPO settings and 37 fixed GEPA settings from the original sweep. It recovers the final prompts and counts their passes separately for each holdout case. Each of 4,096 draws resamples cases with replacement within each subject, keeping both models and all seeds together for a sampled case. The subjects, selected prompts, and paid lookup costs stay fixed. [Replay runner](../benchmarks/independent_mmlu_cost_uncertainty.py)

The affordable comparison reselects the highest-scoring fixed GEPA setting within CPO's cost in each draw. The score-matched comparison keeps the cheapest fixed GEPA setting that matched or beat CPO on the original holdout. That setting stays fixed throughout the resampling. The intervals are the central empirical 95% of differences on these archives. The GEPA cap and CPO setting have already seen these panels through the original report, so these are descriptive sensitivity intervals. They do not estimate transfer to new subjects, models, or proposal streams.

## Results

Positive differences favor CPO. Paid lookup costs are measured on the original paths.

| CPO setting | Comparison | Observed pass difference | Central 95% range |
| --- | --- | ---: | ---: |
| Cap 28 | Reselect affordable GEPA | +43 | −7 to +82 |
| Cap 28 | Score-matched sequential GEPA, cap 31 | −3 | −46 to +39 |
| Cap 28 | Retain starting prompt | +45 | −1 to +89 |
| Cap 52 | Reselect affordable GEPA | −4 | −49 to +37 |
| Cap 52 | Score-matched batched GEPA, cap 44 | −4 | −48 to +37 |
| Cap 52 | Retain starting prompt | +53 | +4 to +101 |

Cap-28 CPO scored higher than the reselected affordable GEPA setting in 3,888 draws and scored lower in 196. The middle 95% ranges for both GEPA comparisons include zero. Sequential cap 31 used 20,701 lookups, compared with CPO's 14,084, for a measured 32.0% saving at the observed three-pass deficit. That cost saving is conditional on the archived trajectories. No CPO default changed. [Sealed counts and GEPA selection frequencies](independent-mmlu-cost-uncertainty-results-v1.json)

Two offline executions produced byte-identical reports. All 312 replayed panel settings matched their published score, cost, and callback trace. Fresh-model superiority remains unverified.

## Reproduce

Use GEPA 0.1.4. Preview the seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.independent_mmlu_cost_uncertainty
```
