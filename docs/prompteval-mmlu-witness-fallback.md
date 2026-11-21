# Transfer the capped witness fallback to MMLU

This replay transfers the published 16-lookup fallback to the 26 model–subject panels in the two earlier MMLU cohorts. It keeps their exact starting prompts, rosters, training, shared validation, independent admission, and holdout. The cohorts contain nine and four subject areas respectively, with two model panels per subject. These archives were used in earlier CPO studies. They provide a comparison separate from the BBH, LMentry, GSM8K, and SST‑5 fallback results. [Matched-admission inputs](prompteval-matched-admission-attempt.md) · [Selection of the 16-lookup variant](bounded-halving-fallback.md)

Only episodes that use no witness admission can invoke cap‑8 certified Halving. The fallback reuses paid validation grades, reads at most 16 more, and carries the same single independent proof. The control grid includes retaining the start, original one-admission CPO, six certified Halving caps, and official GEPA with validation widths from two to 24. All use the original admission rule. Narrower GEPA uses the first enrolled validation anchors and reserves the full proposal round. Training and validation IDs remain distinct. [Runner](../benchmarks/prompteval_mmlu_witness_fallback.py) · [GEPA budget protocol](prompteval-narrow-native-admission.md)

Scores weight each subject equally. The paired bootstrap keeps both models and all repeated decisions for a case together. It reselects the highest-scoring fixed control within the candidate's measured lookup budget. Joint resampling also reweights subject costs. The transfer gate requires a positive lower endpoint in both cohorts. Pooled figures and hindsight allocation by subject describe the recorded frontier.

## Results

The capped fallback missed the gate on both MMLU cohorts. It gained four passes over original one-admission CPO across 64,896 recorded decisions and used 4,669 more lookups. The pooled difference in equal-subject accuracy was +0.006 percentage points. Cap‑24 Halving scored more passes with 7,767 fewer lookups than the fallback. [Sealed results and panel traces](prompteval-mmlu-witness-fallback-results-v1.json)

| Cohort | Capped fallback passes / lookups | Original CPO | Strongest affordable fixed control | Paired 95% range against reselected controls |
| --- | ---: | ---: | ---: | ---: |
| Nine prior subjects | 21,180 / 34,511 | 21,177 / 30,914 | Halving cap 24, 21,229 / 28,546 | −0.292 to +0.009 pp |
| Four additional subjects | 8,976 / 13,811 | 8,975 / 12,739 | Original CPO, 8,975 / 12,739 | −0.392 to +0.092 pp |
| Pooled | 30,156 / 48,322 | 30,152 / 43,653 | Halving cap 24, 30,188 / 40,555 | −0.198 to +0.033 pp |

The pooled strongest affordable fixed GEPA was batched with 16 anchors and cap 56. It scored 30,127 passes on 46,190 lookups. The fallback's +0.045 percentage-point mean advantage against that point was within the paired range of −0.122 to +0.179 against reselected native controls. Picking separately for each subject in hindsight raised native GEPA to 50.537% at 47,047 lookups. The fallback reached 50.414% at 48,322 lookups.

The fallback activated in 337 episodes, produced 17 promotions, and hit its validation cap in 77 episodes. It paid for 3,910 validation and 759 proof lookups. On BBH and LMentry, the same cap produced 48 promotions in 254 eligible episodes and gained 181 passes. The MMLU evidence supports retaining the fallback as an opt-in candidate and testing it across task types before choosing a default. Both experiments use recorded grades and fixed supplied prompts. [BBH and LMentry cap sweep](bounded-halving-fallback.md)

A later replay fitted screening rules outside each held-out benchmark family. The rule for MMLU removed 4,459 of the extra lookups and lost one pass against original CPO. [Paid-grade routing](witness-fallback-routing.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Both offline runs reproduced the original witness, retain-start, and wide GEPA scores and costs on every MMLU panel. Eleven targeted tests passed. Storage Guard measured 6.0 GiB free. The disposable export and wheel overlay used the standing LAB exception for a bounded 0.2 GiB operation. The replay made zero provider requests. [GEPA dependency](../requirements-benchmark.txt) · [Boundary tests](../tests/unit/test_prompteval_mmlu_witness_fallback.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.prompteval_mmlu_witness_fallback
python -B -m benchmarks.prompteval_mmlu_witness_fallback \
  --execute 4bc48ef0d197ca9baf1460c10c885708a414f8a4cd0eaaf0de9ee5046a0dc63f \
  --out MMLU_FALLBACK.json
```
