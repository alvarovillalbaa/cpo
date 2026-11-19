# Admit a challenger when the shortest strict proof fits

Seeded deferred first-gain reserves enough logical lookups for a full incumbent panel and a full finalist panel before it probes a challenger. Under a tight cap, that reserve can stop search while a shorter exact proof is still affordable. This replay tests admission using the minimum number of replies required for a strict gain on the same validation cases. [Low-budget result](independent-mmlu-cost-frontier.md)

The method measures the incumbent while checking whether the remaining allowance can still fund the missing incumbent cases and the smallest possible challenger certificate. The challenger needs at least one more pass than the incumbent, including every critical pass the incumbent protected. Candidates get the same first-miss probe in the original order. Once a candidate passes it, the existing certificate either proves the gain, rules it out, or stops when the remaining budget cannot prove it. The independent qualification gate still decides promotion.

The first variant applies minimum-proof admission from the start. The fallback variant tries the seeded screen first and uses minimum-proof admission on unprobed candidates only when the seeded screen has no finalist. Both variants share the original archive, qualification rows, proposal schedule, and per-cycle budget with their seeded controls. [Runner](../benchmarks/minimum_proof_budget.py) · [Exact certificate](../cpo/challenger.py)

## Results

Both minimum-proof variants produced the same measured costs and holdout passes on all 120 panel-cap combinations. Their callback trace hashes differed on all 120 combinations. The table reports either variant's totals.

| Cap | New MMLU seeded | New MMLU minimum proof | Earlier cohorts seeded | Earlier cohorts minimum proof |
| --- | ---: | ---: | ---: | ---: |
| 24 | 8,937 / 7,659 | 8,945 / 18,669 | 19,061 / 35,230 | 20,792 / 76,146 |
| 28 | 8,963 / 14,084 | 8,961 / 23,209 | 20,471 / 68,675 | 20,949 / 94,173 |
| 32 | 8,962 / 18,157 | 8,962 / 25,561 | 20,876 / 88,033 | 20,989 / 104,526 |

On the new MMLU panels, minimum proof at cap 28 lost two passes and used 9,125 more paid lookups than seeded CPO. At that realized cost, the best affordable fixed GEPA setting scored 8,977, ahead of minimum proof's 8,961. Seeded CPO at cap 24 used 7,659 lookups, below every fixed GEPA point in the measured sweep. The task-specific GEPA hindsight comparison still reached 8,947 within that budget.

On the earlier cohorts, most gains at cap 28 came from BBH and LMentry. The two cohorts gained 93 and 384 passes, respectively. Their extra lookups account for 17,892 of the 25,498 additional lookups across all earlier cohorts. The stronger admission rule improves nominal-cap coverage on those archives. It does not improve the realized-cost tradeoff on the newer MMLU panels. Seeded deferred first-gain remains the default. [Sealed panel costs, traces, and GEPA comparisons](minimum-proof-budget-results-v1.json)

The seeded cap-28 traces reproduced on all 40 panels. Both offline executions of every phase were byte-identical. The tests exercised 5,120 binary panel, budget, and admission combinations and verified strict gain, critical-case protection, and lookup accounting. Fresh-model superiority and provider cost remain unverified.

## Reproduce

Use GEPA 0.1.4. Preview the phase seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`. Phases are `independent`, `mmlu`, `bbh-lmentry`, and `bbh-lmentry-stress`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.minimum_proof_budget --phase independent
```
