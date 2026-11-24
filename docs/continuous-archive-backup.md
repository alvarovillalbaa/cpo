# Use qualification savings to fund one terminal backup

Joint reply ordering saved 587 lookups while preserving every decision in the three-cycle benchmark. This replay verifies those trajectories and gives each backup policy the same per-cohort savings as its entire allowance. Backups run after the frozen three cycles have settled. Only a proved rejection in the final cycle can open a backup. This creates a known budget and leaves earlier incumbents and all first-choice promotions intact. [Joint-order results](joint-archive-proof.md) · [Replay runner](../benchmarks/continuous_archive_backup.py)

The comparison covers three ways to admit a backup.

- **Paid certificate** requires enough already paid validation grades to prove a positive full-panel gain.
- **Paid repair** requires a paid challenger pass on an incumbent miss and no observed paired loss. A complete validation gain must still be possible.
- **One probe** uses the paid-repair rule and can buy one missing challenger grade at an observed incumbent miss. A failed probe ends the attempt.

All three require an exact net gain on the original independent qualification cases. They reuse the incumbent grades from the rejected proof, exclude the failed nominee, and reserve all possibly unread replies before starting an attempt. They rank options by estimated qualification probability per expected additional lookup using the jointly fitted weights. The one-probe estimate uses conditional repair probability as a proxy. The scheduler refunds unused reserve and attempts at most one backup per episode. It never uses held-out grades to dispatch a lookup.

The comparison reprices and directly replays the best common and subject-tuned uniform and halving controls at each policy's actual spend. The earlier subject-tuned GEPA score at the original router's higher lookup ceiling is a conservative bound. The hindsight analysis gives each eligible candidate its recorded holdout and qualification outcomes and the minimum proof price. It relaxes reserve timing after the initial affordability check. It bounds upside under the same cohort allowance and can overstate what a prospective scheduler could attain.

## Results

The paid-certificate policy found zero eligible backups. The table gives each other policy's change in final held-out passes and its added lookups against joint proof ordering.

| Cohort | Lookup allowance | Paid repair | One probe | One-probe hindsight upper bound |
| --- | ---: | ---: | ---: | ---: |
| [Bounded BBH](continuous-archive-backup-bounded-bbh-v1.json) | 82 | −6 / 79 | −6 / 79 | +62 |
| [Bounded LMentry](continuous-archive-backup-bounded-lmentry-v1.json) | 53 | +42 / 51 | +42 / 51 | +103 |
| [Bounded MMLU](continuous-archive-backup-bounded-mmlu-v1.json) | 4 | 0 / 0 | 0 / 0 | 0 |
| [Four-case MMLU](continuous-archive-backup-four-case-mmlu-v1.json) | 105 | 0 / 31 | +2 / 101 | +2 |
| [Tie BBH](continuous-archive-backup-tie-bbh-v1.json) | 224 | +1 / 88 | +7 / 220 | +18 |
| [Tie LMentry](continuous-archive-backup-tie-lmentry-v1.json) | 65 | +11 / 32 | +7 / 61 | +16 |
| [Additional MMLU](continuous-archive-backup-additional-mmlu-v1.json) | 54 | +3 / 18 | +2 / 50 | +8 |
| Total | 587 | +51 / 299 | +54 / 562 | +209 |

Paid repair opened 80 backups, promoted 17, and finished 288 lookups below the original router. One probe attempted 246 backups, promoted 23, and finished 25 lookups below the original router. The positive paired 95% ranges for paid repair against joint proof ordering were +30 to +53 on bounded LMentry and +3 to +19 on tie LMentry. Its paired range on bounded BBH was −17 to +5.

On bounded LMentry both policies scored 6,363 passes in 15,709 lookups, above the subject-tuned GEPA bound of 5,931 and the subject-tuned simple controls' 6,349. The paired range against the simple controls was −58 to +85, and static CPO still scored 6,513 at the higher cost of 19,377. The subject-tuned simple controls also stayed ahead on bounded BBH and the three MMLU cohorts. The large gaps to hindsight on bounded BBH and bounded LMentry identify where better ranking could matter. In four-case and additional MMLU the one-probe upper bounds of two and eight passes were too small to close the score gap to the simple controls at the measured one-probe prices.

Paired ranges resample cases within task with the selected schedules fixed. These cohorts reuse archived prompt rosters and grades. Fresh proposal quality and live improvement remain unverified.

## Reproduce offline

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel. Preview a different cohort by omitting `--execute` and `--out`. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_archive_backup \
  --cohort bounded-LMentry \
  --execute 79e7ac10c052c107476cde5112c0d4b987af914b70d5aea54de9f94895b36a3f \
  --out NEW_REPORT.json
```

Two CLI replays per cohort matched byte for byte with DNS and outbound sockets blocked. The combined backup and proof suite passed 13 tests. All policies conserved their lookup allowances and all promoted backups passed a separately checked exact gain on the original qualification cases. Storage Guard measured 10.1 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Focused tests](../tests/unit/test_continuous_archive_backup.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
