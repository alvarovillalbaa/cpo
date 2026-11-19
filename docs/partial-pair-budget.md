# Prove validation gain before both prompts are fully observed

Minimum-proof admission can spend the whole incumbent panel before testing a promising challenger. This replay uses the existing paired qualification bounds as a scalar validation proof. Each known challenger pass or incumbent failure raises the lower gain bound by one. Once the lower bound proves a strict gain and every critical risk is resolved, the proof stops. [Minimum-proof comparison](minimum-proof-budget.md) · [Paired bounds](paired-qualification.md)

The new selector probes the first seeded incumbent miss. It tries the first candidate that passes that case, provided enough lookups remain for the shortest possible proof. The proof visits the known witness, critical cases, and other already observed incumbent cases first. It reuses prior replies within the search. Exhausting the cap keeps the incumbent. The same independent qualification and archive policy still govern promotion.

The paired-first arm uses this procedure for every fresh search. The paired fallback starts with the seeded deferred screen and uses the paired proof only when the seeded screen has no finalist, using unprobed candidates. Both use the committed paired qualifier. The benchmark keeps the published seeded and minimum-proof receipts as controls at caps 24, 28, and 32. [Runner](../benchmarks/partial_pair_budget.py)

## Results

Each cell shows holdout passes and paid lookups. The table shows the cap-32 comparison.

| Scope | Seeded screen | Minimum proof with incumbent read | Paired-first | Paired fallback |
| --- | ---: | ---: | ---: | ---: |
| New MMLU | 8,962 / 18,157 | 8,962 / 25,561 | 8,962 / 21,387 | 8,962 / 21,249 |
| Earlier three cohorts | 20,876 / 88,033 | 20,989 / 104,526 | 21,004 / 100,963 | 21,004 / 99,560 |
| All 40 panels | 29,838 / 106,190 | 29,951 / 130,087 | 29,966 / 122,350 | 29,966 / 120,809 |

The paired fallback gained 15 passes and saved 9,278 lookups against minimum-proof admission at cap 32. It issued 106 additional proof attempts after the seeded screen, found 91 certificates, and issued every one of those certificates before fully reading the incumbent. Compared with the seeded cap-32 screen, it gained 128 passes and used 14,619 more lookups.

On the new MMLU panels at cap 28, the paired fallback tied the previous minimum-proof method at 8,961 passes and saved 2,762 lookups. Seeded CPO scored 8,963 on 14,084 lookups, compared with 20,447 for the paired fallback. On the earlier cohorts at cap 24, the paired fallback gained 35 passes and used 8,002 more lookups than minimum proof. The measured gain from partial proofs depends on the budget and cohort.

The two paired variants tied in passes on all 120 panel-cap combinations. The fallback saved lookups in 103 and tied costs in three. Seeded deferred first-gain remains the default. [Sealed phase results and GEPA cost comparisons](partial-pair-budget-results-v1.json)

Two offline executions of every phase reproduced the report byte for byte. The tests covered 5,120 binary outcome, budget, and search combinations and checked lookup accounting, strict gain, and critical-case preservation. These are archived fixed-pool results. Fresh-prompt quality and provider costs remain unverified.

## Reproduce

Use GEPA 0.1.4. Preview a phase to get the seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`. Phases are `independent`, `mmlu`, `bbh-lmentry`, and `bbh-lmentry-stress`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.partial_pair_budget --phase independent
```
