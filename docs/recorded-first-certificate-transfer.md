# Transfer the first-certificate rule to MMLU, BBH, and LMentry

The first-certificate rule lowered costs on AIME, with a small observed quality lead over both GEPA controls and a paired range that crossed zero. This replay freezes that rule and applies it to 26 model panels covering 13 archived subjects in MMLU, BBH, and LMentry. It retains each subject's published holdout. Both models for a subject share 32 seeded starts, eight-challenger rosters, and disjoint panels of ten training, six validation, and four qualification cases. The earlier archive studies used these recorded outputs. This test applies the new rule to those outputs without fitting its settings there. [AIME and ARC result](recorded-first-training-certificate.md) · [First MMLU archive](prompteval-transfer.md) · [Second MMLU archive](independent-mmlu-transfer.md) · [BBH and LMentry archive](tie-extension-cross-benchmark.md) · [Replay runner](../benchmarks/recorded_first_certificate_transfer.py)

CPO runs the same incumbent precheck, first strict validation certificate, training corroboration, and independent qualification as on AIME. The seeded CPO reference and both official GEPA modes use the same candidate pools and search cap. All search arms use the same expected-cost order when settling their nomination on the separate qualification cases. Lookup totals count search and qualification, including the incumbent precheck. Each paired draw resamples original holdout cases within subjects, keeping both model panels and all recurring seed observations together. The joint range takes the smaller CPO margin against the two native controls in each draw.

| Cohort | First certificate passes / lookups | Seeded CPO | Sequential GEPA | Batched GEPA | Joint paired 95% range | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| MMLU | 13,431 / 10,578 | 13,434 / 12,821 | 13,444 / 14,404 | 13,445 / 14,182 | −37 to 0 | Inconclusive |
| BBH | 2,054 / 8,102 | 2,063 / 12,243 | 2,099 / 11,062 | 2,086 / 10,707 | −82 to −14 | Failed |
| LMentry | 822 / 4,354 | 916 / 6,686 | 833 / 5,246 | 839 / 5,181 | −43 to +3 | Inconclusive |

The first-certificate rule saved 25.4% to 26.6% of lookups against native GEPA on MMLU, 24.3% to 26.8% on BBH, and 16.0% to 17.0% on LMentry. All cohorts cleared the 10% cost requirement. Each had a lower observed score than both controls. On BBH the paired range remained below zero. On LMentry, seeded CPO gained 94 passes relative to the first certificate and used 2,332 additional lookups. On MMLU, the first certificate gained three passes over retaining the start, with a paired range of −7 to +13. The transfer gate failed. The outcomes measure selection from fixed recorded pools. [Panel-level results and paired case counts](recorded-first-certificate-transfer-results-v1.json)

A follow-up spent a bounded number of reads looking for a stronger certificate. It recovered LMentry passes and left the BBH score unchanged. [Validation lookahead](recorded-certificate-lookahead.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With sockets and DNS blocked, 30 targeted tests passed and two full runs matched byte for byte. The archive and roster tests checked alignment and separation of the four case roles. The CLI rejected a stale seal and the ordered live plan reproduced. Storage Guard measured 5.9 GiB free. The 39 MiB export and publication worktree fit the standing 0.2 GiB LAB exception. The replay sent zero provider requests. [Transfer tests](../tests/unit/test_recorded_first_certificate_transfer.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_first_certificate_transfer
python -B -m benchmarks.recorded_first_certificate_transfer \
  --execute d6a37dd0755e1dbc2ed0cc8919db5cc9d25f92e7b6d227d43055ee7f9c61399a \
  --out NEW_REPORT.json
```
