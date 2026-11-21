# Match retired admission witnesses against fixed budget limits

Allowing **one admission attempt per episode** was the best affordable simple rule on the original nine subjects. It also scored slightly higher and used fewer lookups than retired-admission reuse on the four additional subjects. CPO exposes the attempt limit through an opt-in episode API. [Results and trace hashes](prompteval-witness-budget-controls-results-v1.json) · [Episode API](rotating-witness-cycle.md#limit-admission-attempts-across-cycles)

This replay tests two simpler ways to spend less while keeping the original rotating-witness selection rule. The search-cap controls limit each cycle to 16, 24, 32, 40, or 48 logical search lookups. The admission-cap controls allow one, two, or three nominations per four-cycle episode. A rejection consumes an attempt. Once the attempt cap is used, the episode keeps its incumbent and pays for no more search. The independent qualification rule still applies in full to each nomination. [Runner](../benchmarks/prompteval_witness_budget_controls.py) · [Original case-reuse study](prompteval-retired-admission-witness.md)

Both cohorts keep the sealed candidate rosters, four-cycle seeds, disjoint case assignments, and fixed final holdouts. Costs count paid search and qualification lookups after reuse. GEPA 0.1.4 runs at sequential caps 52, 60, 68, 76, 84, and 88, and batched caps 80, 82, 84, 86, 88, and 96. Its original disjoint train and validation IDs and full-round reserve rule still apply. The runner checks existing CPO and GEPA counts and traces where controls recur.

The simple control is selected on the original nine archived subjects by equal-subject accuracy within the retired-admission policy's realized lookup cost. Ties pick the cheaper measured setting. The four additional archived subjects use that same selected setting. The native comparison picks the highest-scoring affordable fixed GEPA setting or the free starting-prompt control separately within each cohort. It is a retrospective comparison over the measured settings. Paired ranges resample physical cases and optionally subjects, with the reported comparison setting held fixed.

| Method | Original nine subjects | Paid lookups | Four additional subjects | Paid lookups |
| --- | ---: | ---: | ---: | ---: |
| Original rotating witness | 48.214% | 41,359 | 55.685% | 19,305 |
| Retired-admission witnesses | 48.041% | 33,802 | 55.635% | 15,455 |
| One admission attempt | 48.054% | 30,914 | 55.704% | 12,739 |
| Two admission attempts | 48.189% | 39,613 | 55.732% | 17,609 |
| Witness search cap 16 | 48.195% | 39,118 | 55.676% | 18,498 |
| Sequential GEPA, cap 52 | 47.915% | 26,600 | 55.628% | 12,906 |
| Batched GEPA, cap 80 | 48.022% | 39,560 | 55.878% | 20,029 |

Against retired-admission reuse, one attempt saved 2,888 and 2,716 lookups and increased mean accuracy by 0.013 and 0.069 percentage points. The paired 95% ranges, resampling cases and subjects, were −0.120 to +0.155 and −0.182 to +0.368 points. On the original subjects, one attempt gained in the equal-subject average while losing 19 pooled passes. On the additional subjects it gained five pooled passes.

Sequential GEPA at cap 52 was the highest-scoring fixed native setting within the retired-admission budget on both cohorts. The one-attempt rule used 4,314 more lookups for a 0.140-point gain on the original subjects. On the additional subjects it gained 0.076 points and saved 167 lookups. Batched GEPA at cap 80 scored higher on the additional subjects at a higher cost. These are archived prompt-selection results. Fresh-model superiority remains unverified.

## Reproduce

Use Python 3.12 and hash-pinned GEPA 0.1.4. Verification blocked DNS and sockets and used a disposable allocation bounded at 0.2 GiB under the standing LAB exception. Storage Guard measured 6.2 GiB free. [Benchmark wheel](../requirements-benchmark.txt) · [Comparator tests](../tests/unit/test_prompteval_witness_budget_controls.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_witness_budget_controls
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_witness_budget_controls \
  --execute d7b1b8905c008856184a8b1db0a896ec4acfeb9c8a849eae79fe80c1c2e66f05 \
  --out NEW_REPORT.json
```

The results SHA-256 is `7845ae7d22ad98f4c88c93e4560f3b90d6289da4733d123bdce67e42e0b0c819`.
