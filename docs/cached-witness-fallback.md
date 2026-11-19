# Use a cached witness only after the seeded screen stalls

Replacing the seeded witness caused a large ends-with-word loss whether archive retries ran before or after fresh search. This replay keeps the seeded path intact on cycles where it produces a validation certificate. It tests a cached witness only after the seeded screen keeps the incumbent in validation. [Archive-order comparison](archive-after-fresh-search.md)

The fallback looks for a different validation case where the incumbent failed earlier in the episode. It requires one or two prior passes by distinct non-incumbent prompts. The selected case comes from the current validation cohort. The policy scans candidates in the original order, skips the already failed finalist, and tries to certify at most one additional candidate. It reuses validation replies already read in that cycle. The extra allowance is eight or 16 logical validation lookups within the original search ceiling.

The same independent qualification gate applies to the fallback candidate. A rejected fallback pays for the replies it read and stays out of the archive. A qualified fallback may promote. The fixed-pool qualification panel, recency archive policy, and final holdout remain the same. [Replay runner](../benchmarks/cached_witness_fallback.py)

## Results

| Fallback | Holdout passes | Paid lookups | Fallback promotions | Panels clearing both GEPA gates / 32 |
| --- | ---: | ---: | ---: | ---: |
| Seeded only | 21,023 | 101,034 | 0 | 15 |
| One prior pass, eight extra reads | 21,024 | 102,772 | 1 | 15 |
| One prior pass, 16 extra reads | 21,018 | 105,296 | 19 | 15 |
| Two prior passes, 16 extra reads | 21,023 | 101,332 | 0 | 15 |

The eight-read fallback gained one pass across 1,024 matched episodes at a cost of 1,738 extra paid lookups. Extending the allowance to 16 found 54 certificates and 19 promotions, but lost five aggregate holdout passes. Requiring two earlier passes produced five certificates and zero promotions. Seeded deferred first-gain remains the default.

All three fallbacks preserved the 30-of-30 score on the Flan-T5-XXL ends-with-word episode at seed 47690. The 16-read arms produced an alternate certificate in that episode. Qualification rejected it, and the next cycle could still select prompt 61, as the seeded control did. This recovers the diagnostic episode while the full replay shows weak returns from retries. [Sealed results and episode trace](cached-witness-fallback-results-v1.json)

Both GEPA comparisons use the published controls that reinvest cache hits under the paid cap. The seeded CPO control reproduced the static callback traces and lookup totals on all 32 panels. Two offline runs reproduced each phase byte for byte. These results cover archived fixed prompt pools. Fresh-model superiority and provider costs remain unverified. [GEPA paid-cap controls](gepa-paid-cap-transfer.md)

## Reproduce

Use GEPA 0.1.4. Preview the seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`. Phases are `mmlu`, `bbh-lmentry`, and `bbh-lmentry-stress`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.cached_witness_fallback --phase bbh-lmentry-stress
```
