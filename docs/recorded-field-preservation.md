# Protecting individual fields on the promotion panel

Protecting every field the incumbent got right on critical promotion cases changed no decisions across the 660 archived replay splits. Protecting the total number of correct fields gave the same result. Either rule would have added nine outage evaluations for CPO, four for sequential GEPA, and three for batched GEPA. All six matched critical loss observations against GEPA remained. [Reproducible result](recorded-field-preservation-results-v1.json) · [Original promotion replay](recorded-promotion-coverage.md)

The audit rescored 1,464 distinct provider replies from the source validation panels with the original grader. It checked receipt IDs and required consistent correct fields when a prompt and case had multiple replies. The new rules extend each arm's original promotion check. They use the incumbent's already paid outcomes to identify critical cases with any correct fields. An arm pays for a challenger reply if its earlier promotion check stopped before that case. Training, search, and the final holdout stay fixed.

Outage produced five distinct finalist pairs. Across those pairs, equal field counts always meant the same fields were correct. In three of the six critical loss observations, the losing and winning prompts returned identical recorded JSON values on every training, validation, and promotion case. Those three observations reuse one directed prompt pair, which lacks replies on the separate provider holdout. A different losing direction has both original provider holdouts and scored 9 versus 18, with four matched critical losses. Neither guard changed a selection. [Independent holdout audit](recorded-independent-holdout.md)

The result rules out this field-preservation check as a fix on these panels. The fixed replies also locate a specific evidence gap. For one losing direction, a stronger choice requires information beyond the observed answers on the nine cases used before holdout.

## Reproduce offline

```sh
python -B -m benchmarks.recorded_field_preservation \
  --replay FULL_PROMOTION_REPLAY.json \
  --independent FULL_INDEPENDENT_HOLDOUT_AUDIT.json \
  --source-plan REWRITE_FIRST_PLAN.json \
  --archive ORIGINAL_OPEN_EVALS_STUDY \
  --grader ORIGINAL_IMPROVEMENT_PLAN.mjs \
  --out NEW_REPORT.json
```

The replay sends no requests and stores no reply text in its report. Two runs produced byte-identical results. Tests verify that the field-identity gate can catch a lost field despite an unchanged count, and that the replay charges only missing protected evaluations. [Runner](../benchmarks/recorded_field_preservation.py) · [Tests](../tests/test_recorded_field_preservation.py)
