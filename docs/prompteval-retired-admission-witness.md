# Reuse paid admission grades in later searches

Using retired admission cases as witnesses reduced total paid lookups by **18.3%** on nine original PromptEval subjects and **19.9%** on four additional archived subjects. Mean accuracy declined by 0.173 and 0.050 percentage points respectively compared with the original rotating-witness rule. The cost reduction came partly from fewer challengers reaching independent admission. [Sealed results](prompteval-retired-admission-witness-results-v1.json) · [Runner](../benchmarks/prompteval_retired_admission_witness.py)

The validation-history control selects an incumbent pass and miss from previously paid grades on current validation anchors. The retired-admission variant also considers cases already observed during an earlier admission, giving them priority in the seeded order. Both variants keep the original order when the cache cannot supply both grades. The original validation anchors supply the finalist tie-break. A retired case enters later validation only after a grade is observed and the case is ineligible for later admission. A prompt–case observation is charged once within the episode. The logical search cap, qualification policy, candidate rosters, and final holdout remain the same.

| Method | Original nine subjects | Paid lookups | Four additional subjects | Paid lookups |
| --- | ---: | ---: | ---: | ---: |
| Original rotating witness | 48.214% | 41,359 | 55.685% | 19,305 |
| Reuse validation history | 48.071% | 36,461 | 55.650% | 16,594 |
| Reuse retired admission grades | 48.041% | 33,802 | 55.635% | 15,455 |
| Sequential GEPA, cap 52 | 47.915% | 26,600 | 55.628% | 12,906 |
| Batched GEPA, cap 80 | 48.022% | 39,560 | 55.878% | 20,029 |
| Batched GEPA, cap 88 | 48.139% | 56,164 | 55.937% | 28,217 |

The benchmark weights subjects equally and reconstructs the original four-cycle traces on all 26 model–subject panels. It compares with the previously sealed native GEPA results. The additional archive shares no subjects with the original nine and has appeared in earlier CPO experiments. The replay measures reuse of exact recorded grades within an episode. [Original transfer](prompteval-rotating-witness-transfer.md) · [Additional archive and native controls](prompteval-witness-tie-budget.md)

Compared with validation-only reuse, admitting retired cases added 134 and 166 search lookups, then saved 2,793 and 1,305 admission lookups. The variant reused 674 and 413 paid grades and still made more new search reads overall. Nominations for admission fell from 426 to 252 and from 245 to 158. Promotions fell from 89 to 54 and from 59 to 46.

The paired case-resampling ranges for the accuracy difference versus the original witness were −0.318 to −0.028 percentage points on the nine original subjects and −0.328 to +0.238 on the additional subjects. When subjects were resampled too, they were −0.445 to +0.032 and −0.385 to +0.245. Against batched GEPA at cap 80, the retired-admission policy gained 0.019 points and saved 5,758 lookups on the original subjects. It lost 0.244 points and saved 4,574 lookups on the additional subjects. This adds a lower-cost archived operating point with a quality tradeoff. The evidence favors retaining the original witness rule as the reference for fresh-model testing.

A follow-up compared the same lookup budget with simpler controls. One admission attempt per episode used fewer lookups and scored slightly higher in both subject sets. [Fixed-budget comparison](prompteval-witness-budget-controls.md)

## Reproduce

Use Python 3.12 and the repository's recorded archives and receipts. Verification blocked DNS and sockets and used a disposable overlay bounded at 0.2 GiB under the standing LAB exception. Storage Guard measured 6.1 GiB free. The replay made zero new provider requests. [Boundary and reuse tests](../tests/unit/test_prompteval_retired_admission_witness.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_retired_admission_witness
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_retired_admission_witness \
  --execute 523e95f565f888d551fa484455db9f3908af9bc5c3101214275d0c918380c70a \
  --out NEW_REPORT.json
```

The results SHA-256 is `d4a43e7f6dbce3c986e055c1ff0d9b2545026cc0a9ce0bf48ccb77beec8c740c`.
