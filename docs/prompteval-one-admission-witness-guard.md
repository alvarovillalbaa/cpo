# Check an extra witness before spending the only admission

Requiring an extra witness reduced independent admission work but increased total lookups on all three archived cohorts. On BBH and LMentry, both variants scored lower than the original one-attempt rule. [Sealed results](prompteval-one-admission-witness-guard-results-v1.json)

The rotating-witness rule finds an incumbent pass and miss in seeded order and nominates one of up to two eligible challengers. This replay checks one additional validation case when the original incumbent scan has already graded it. It takes the last such case in seeded order after excluding the initial witnesses. The finalist must pass that case to use the admission attempt. The check reuses any finalist grade already read and buys at most one additional logical lookup for that nominee. When the case is unavailable or its grade cannot fit, the original nomination proceeds. [Runner](../benchmarks/prompteval_one_admission_witness_guard.py)

The second variant can send the other original finalist to admission if that finalist passes the additional case within the same search cap. A veto with no replacement leaves the one-attempt allowance available for a later cycle. An admitted challenger still has to pass the original gate on disjoint cases. There are no new incumbent reads, proposal changes, or admission cases.

The replay covers the three archived cohorts from the matched-admission study. It reproduces the original CPO one-attempt score and paid cost on all 70 model panels. Native controls come from the two earlier sealed receipts, including the narrower GEPA settings for BBH and LMentry. Paired ranges group the model and episode outcomes from each physical case. [One-attempt comparison](prompteval-matched-admission-attempt.md) · [Narrower native validation](prompteval-narrow-native-admission.md)

| Cohort | Original accuracy / lookups | Extra witness | Extra witness with finalist fallback |
| --- | ---: | ---: | ---: |
| Original nine PromptEval subjects | 48.054% / 30,914 | 48.016% / 31,514 | 48.016% / 31,546 |
| Four additional PromptEval subjects | 55.704% / 12,739 | 55.732% / 13,101 | 55.732% / 13,114 |
| BBH and LMentry | 39.979% / 68,125 | 38.232% / 76,741 | 38.658% / 76,167 |

On BBH and LMentry, the check without fallback saved 4,150 admission reads and added 12,766 paid search reads. It checked 1,167 additional witnesses, 1,007 of which the incumbent had missed. The fallback recovered 66 nominees and improved the holdout score by 180 passes relative to the veto alone. Its accuracy still trailed the original by 1.321 percentage points, with a paired range of −2.311 to −0.374 after resampling subjects and cases. The original rule retains the better archived operating point.

## Check only known incumbent passes

After seeing how often the extra witness was another incumbent miss, a second experiment restricted the check to known incumbent passes. It reproduced every original panel trace and kept the same independent admission gate. The narrower check used 915 more lookups on BBH and LMentry and lost 16 passes, a mean change of −0.038 percentage points. Its paired range was −0.135 to +0.052 points. It gained five passes and used 84 more lookups on the original PromptEval subjects. It tied the score and used 43 more lookups on the additional subjects. The follow-up also favors retaining the original one-attempt rule. [Follow-up sealed results](prompteval-one-admission-witness-guard-results-v2.json)

## Reproduce the original experiment

Use Python 3.12 and the original sealed source revision `4857a68fa66143c8df1527c2af18bed5bbad3c26`. Verification blocked DNS and sockets. Storage Guard measured 5.0 GiB free. The temporary source exports were bounded at 0.2 GiB under the standing LAB exception. [Focused tests](../tests/unit/test_prompteval_one_admission_witness_guard.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_one_admission_witness_guard \
  --execute 30d07921cfe7fd4b2f284ada96df62c2a9cd4be9976d4a3d73ef0caf7bfb413c \
  --out NEW_REPORT.json
```

The results SHA-256 is `3d305c6ad9b7db5853c55311939e5aee44c67f26f0ae631785b7de1bdd024267`.

## Reproduce the follow-up

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_one_admission_witness_guard \
  --execute 9fb93559c6a96e8d3462f0304ef95277478821ab57ff2ae974f8805a23c25308 \
  --out NEW_REPORT.json
```

The follow-up SHA-256 is `1e58ab7a1f7f1e914eeabb0e962685bd19a96599e5650df7a1cae34aa372c636`. Both versions used recorded outcomes and made zero provider requests. Fresh-model performance remains unverified.
