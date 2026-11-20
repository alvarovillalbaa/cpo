# Compare CPO and GEPA at realized lookup costs

Requiring a second validation signal reduced CPO's lookup bill and lost some holdout passes. The original comparison used GEPA at a paid search cap of 52. This replay tests whether the savings persist as a quality advantage when GEPA can spend up to each CPO policy's realized budget. [Validation results](independent-witness-validation.md) · [Earlier cost sweep](routed-model-cost-frontier.md)

The comparison reruns the original CPO route, expected-cost qualification ordering, the second-repair rule, and the independent-gain rule. For both official GEPA 0.1.4 modes, it evaluates every integer paid search cap from 20 through 68. It uses the same 44 archived model and subject panels, with 32 four-cycle episodes per panel and the original starting prompts, proposal blocks, and case splits. Search and qualification replies both count toward each method's realized cost. The replay checks the recorded CPO and cap-52 GEPA traces before comparing cost points. [Qualification ordering](family-qualification-order.md) · [Runner](../benchmarks/witness_validation_cost_frontier.py)

For each cohort and CPO policy, the comparison selects the highest-scoring GEPA mode and cap whose total lookups fit the CPO budget. Retaining every starting prompt is also eligible at zero cost. This selection uses archived holdout scores in hindsight. In each of 4,096 paired case resamples, it recomputes the highest-scoring affordable setting under the original realized costs. Each case carries both models and every episode for that subject. The 95% ranges measure sensitivity to these held-out cases with the completed search paths fixed.

## Results

Scores and costs are shown as holdout passes / paid lookups.

| Cohort | CPO policy | CPO score / cost | Best affordable GEPA | GEPA score / cost | Pass difference | Paired 95% range |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| Llama and Mistral | Original | 17,724 / 49,330 | Batched, cap 47 | 17,687 / 45,679 | +37 | −24 to +86 |
| Llama and Mistral | Expected-cost ordering | 17,724 / 48,822 | Batched, cap 47 | 17,687 / 45,679 | +37 | −24 to +86 |
| Llama and Mistral | Second repair | 17,697 / 44,654 | Batched, cap 45 | 17,686 / 42,510 | +11 | −45 to +57 |
| Llama and Mistral | Independent gain | 17,697 / 43,556 | Batched, cap 45 | 17,686 / 42,510 | +11 | −35 to +53 |
| Gemma and Flan | Original | 17,435 / 35,496 | Batched, cap 49 | 17,418 / 34,383 | +17 | −36 to +58 |
| Gemma and Flan | Expected-cost ordering | 17,435 / 35,127 | Batched, cap 49 | 17,418 / 34,383 | +17 | −36 to +58 |
| Gemma and Flan | Second repair | 17,421 / 32,126 | Batched, cap 41 | 17,415 / 20,303 | +6 | −38 to +44 |
| Gemma and Flan | Independent gain | 17,425 / 31,696 | Batched, cap 41 | 17,415 / 20,303 | +10 | −34 to +46 |
| Mixtral and Falcon | Original | 29,616 / 46,981 | Sequential, cap 35 | 29,596 / 45,863 | +20 | −40 to +76 |
| Mixtral and Falcon | Expected-cost ordering | 29,616 / 46,428 | Sequential, cap 35 | 29,596 / 45,863 | +20 | −40 to +76 |
| Mixtral and Falcon | Second repair | 29,599 / 41,550 | Sequential, cap 31 | 29,583 / 37,238 | +16 | −33 to +55 |
| Mixtral and Falcon | Independent gain | 29,591 / 40,861 | Sequential, cap 31 | 29,583 / 37,238 | +8 | −38 to +43 |

Every CPO point estimate exceeded the strongest affordable fixed control. All 12 paired ranges include zero. Expected-cost qualification ordering preserved the original scores and reduced total lookups on every cohort. The stricter validation rules widened the savings and reduced the point-estimate lead. The cheapest swept GEPA points to match expected-cost CPO's scores used 73,050, 53,293, and 57,619 lookups respectively. These are retrospective comparisons over fixed archived prompt pools and the swept caps. Fresh model quality remains unverified. [Complete sweep and per-mode comparisons](witness-validation-cost-frontier-results-v1.json)

The follow-up froze expected-cost CPO on unused BBH and LMentry model splits and let both GEPA modes use the same qualification ordering. [Cross-benchmark transfer](qualification-order-transfer.md)

## Reproduce offline

Use pinned GEPA 0.1.4. The first command prints the design seal. Use a fresh output path for the sweep.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.witness_validation_cost_frontier
PYTHONHASHSEED=0 python -B -m benchmarks.witness_validation_cost_frontier \
  --execute ff19661a60db142577a082c7badbf2ba8cc42ba68db2ac29fa66564af5e4daa8 \
  --out NEW_REPORT.json
```

Two runs from a clean source export produced byte-identical reports with sockets and DNS blocked. They measured 4,312 GEPA panel settings and reproduced 264 published CPO and GEPA control records. Three focused tests checked affordability, reselection, and deterministic ties. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 11.5 GiB free. The 24.3 MB scratch overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_witness_validation_cost_frontier.py) · [Verification receipt](witness-validation-cost-frontier-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
