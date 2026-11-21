# Spending extra validation reads on tied finalists

The original rotating-witness rule remains the reference. Extending tied comparisons increased lookup costs on both sets of archived subjects. It yielded a small score gain on the original subjects and a small loss on the additional subjects. [Sealed results](prompteval-witness-tie-budget-results-v1.json) · [Runner](../benchmarks/prompteval_witness_tie_budget.py)

The original screen finds up to two candidates that repair an observed incumbent failure and preserve its first observed success, when one exists. It compares both on one validation case. The tie-only rule spends up to three more pairs of validation reads, stops at the first score difference, and preserves proposal order as the final tie-break. The always-extend control uses any of the same three pairs it can fund. Both spend within the original 56-read search cap per cycle. Each sends at most one nominee to qualification on the original separate case bank. The final holdout scores the selected prompt after four cycles and supplies no search feedback.

| Rule | Original nine subjects | Paid lookups | Four additional subjects | Paid lookups |
| --- | ---: | ---: | ---: | ---: |
| Retain starting prompt | 47.891% | 0 | 55.463% | 0 |
| Original rotating witness | 48.214% | 41,359 | 55.685% | 19,305 |
| Extend ties only | 48.237% | 42,999 | 55.670% | 20,235 |
| Always extend | 48.237% | 43,224 | 55.660% | 20,464 |
| Sequential GEPA, cap 52 | 47.915% | 26,600 | 55.628% | 12,906 |
| Batched GEPA, cap 80 | 48.022% | 39,560 | 55.878% | 20,029 |
| Batched GEPA, cap 88 | 48.139% | 56,164 | 55.937% | 28,217 |
| Batched GEPA, cap 136 | 48.356% | 125,720 | 56.350% | 61,764 |

Accuracy weights each subject equally. Paid lookups include search and qualification after reuse. Across 18 original model/subject panels, the tie-only rule changed 27 cycle nominations and added 1,640 paid lookups. Across eight additional panels, it changed 19 and added 930. Those nomination counts compare with the original tiebreak on the same cycle inputs. Earlier decisions can change the incumbent and the candidate set in later cycles. Batched GEPA at cap 80 scored 0.208 percentage points higher than the tie-only rule on the additional subjects and used 206 fewer lookups.

The 4,096 paired resamples kept all decisions for the same held-out case together. The 95% ranges for the tie-only score difference versus the original were −0.018 to +0.064 percentage points on the original subjects and −0.105 to +0.075 on the additional subjects. Resampling subjects and cases gave −0.033 to +0.080 and −0.147 to +0.130 respectively. The additional archive covers college biology, machine learning, nutrition, and security studies. These subjects differ from the original nine and have appeared in other CPO archive experiments. The benchmark reused recorded binary prompt outcomes and made zero provider requests. Fresh-model effectiveness remains unverified. [Original transfer](prompteval-rotating-witness-transfer.md) · [Case-level evidence](prompteval-rotating-witness-case-evidence.md)

## Reproduce

Use Python 3.12, the checked-in archives, and the hash-pinned GEPA 0.1.4 wheel. The runner checks the original rotating-witness panel scores and traces against the prior sealed receipt. It reuses the native control receipts for the prior panels and executes the controls on the four additional subjects. Verification blocked DNS and sockets and used a disposable overlay within the 0.2 GiB LAB exception. Storage Guard measured 6.2 GiB free. [Benchmark requirement](../requirements-benchmark.txt) · [Paired-read tests](../tests/unit/test_prompteval_witness_tie_budget.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_witness_tie_budget
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_witness_tie_budget \
  --execute bbd62450dadd7f72d463955154bc5ce5c80b340dfd1eb1a2fba7df9b1fc688c5 \
  --out NEW_REPORT.json
```

The results SHA-256 is `68b9055a4d3fc42bbfaa9a3e27cf9cabaca863c5fbc720d2e86448d050f92578`.
