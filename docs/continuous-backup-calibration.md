# Calibrate backup qualification forecasts

The task allocation study improved the terminal backup schedule by changing which task received the next attempt. Its within-task ranking still used promotion probability and expected cost derived from the first-choice nomination model. This replay checks whether estimates measured on backup attempts improve that ranking. It fixes the original offer set, witnesses, proofs, quotes and task-balanced allocation. [Task allocation benchmark](continuous-backup-allocation.md) · [Replay runner](../benchmarks/continuous_backup_calibration.py)

The fit reproduces the 70 task-disjoint discovery panels and the previous backup labels. It counts actual promotions and lookups for each option. A failed probe contributes its charge and zero promotions. The ranking uses promotion and cost labels. Held-out pass counts check the original trajectory and measure transfer.

- **Original** uses the joint forecast of a repair followed by independent qualification.
- **Empirical** estimates expected promotions and charges from the backup labels, starting from the pooled average and narrowing the context by probe requirement, incumbent qualification misses, validation pass rates and number of known incumbent proof grades. Each narrower estimate carries the weight of 24 observations from its parent.
- **Corrected** preserves the original offer-specific forecast and multiplies each component by its context's ratio of observed to forecast totals. It shrinks each ratio toward its parent, with prior mass sized by the pooled average forecast for 24 observations.

Both predictions rank promotion probability per expected lookup. Estimated cost stays within the physical quote and dispatch reserves the full quote. All three arms use the original global allocator's realized backup spend as the cohort ceiling, which reproduces the task-balanced control from the previous benchmark. The replay also scores promotion probability with mean squared error and expected charge with mean absolute error over the same complete offer menu. That retrospective diagnostic uses every offer's recorded result and plays no role in dispatch.

## Discovery

| Original offer | Options | Forecast promotions | Observed promotions | Forecast lookups | Observed lookups |
| --- | ---: | ---: | ---: | ---: | ---: |
| Paid repair | 111 | 36.85 | 26 | 424.45 | 380 |
| Needs new probe | 2,535 | 96.77 | 81 | 3,612.11 | 3,717 |
| Total | 2,646 | 133.61 | 107 | 4,036.56 | 4,097 |

The first-choice model overpredicted backup promotion in both groups. Its expected lookup cost was too high for paid repair and too low for offers with a new probe. [Fit receipt](continuous-backup-calibration-fit-v1.json)

## Transfer

Pass gains and lookups are relative to joint qualification without backups. Chance error is the mean squared error of the predicted promotion probability. Cost error is mean absolute lookup error. The diagnostics cover 199 paid-repair offers and 3,186 one-probe offers across the seven archived cohorts.

| Backup mode and ranker | Held-out pass gain | Backup lookups | Chance error | Cost error |
| --- | ---: | ---: | ---: | ---: |
| Paid repair, original | +54 | 285 | 0.18406 | 0.956 |
| Paid repair, empirical | +42 | 280 | 0.16056 | 0.857 |
| Paid repair, corrected | +40 | 279 | 0.16013 | 0.788 |
| One probe, original | +66 | 545 | 0.04451 | 0.903 |
| One probe, empirical | +66 | 544 | 0.04512 | 0.861 |
| One probe, corrected | +51 | 542 | 0.04493 | 0.856 |

Calibration predicted paid repair more accurately and lost between 12 and 14 held-out passes there. The corrected one-probe ranker saved three lookups and lost 15 passes. Tie LMentry accounted for 13 of those passes, with a paired 95% range of −19 to −7. The empirical one-probe ranker tied the original aggregate score and saved one lookup. On bounded LMentry, both calibrated one-probe rankers preserved the original 48-pass gain and saved one or two lookups. Their 6,369 passes exceeded the matched subject-tuned simple score of 6,349, with a paired range of −54 to +92.

[Bounded BBH](continuous-backup-calibration-bounded-bbh-v1.json) · [Bounded LMentry](continuous-backup-calibration-bounded-lmentry-v1.json) · [Bounded MMLU](continuous-backup-calibration-bounded-mmlu-v1.json) · [Four-case MMLU](continuous-backup-calibration-four-case-mmlu-v1.json) · [Tie BBH](continuous-backup-calibration-tie-bbh-v1.json) · [Tie LMentry](continuous-backup-calibration-tie-lmentry-v1.json) · [Additional MMLU](continuous-backup-calibration-additional-mmlu-v1.json)

The evidence uses previously examined transfer tasks with archived validation, qualification and held-out grades. Paired ranges resample cases within tasks with the selected settings fixed. Live performance remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Preview a different cohort's seal by omitting `--execute` and `--out`. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_backup_calibration --fit NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_backup_calibration \
  --fitted NEW_FIT.json --cohort bounded-LMentry \
  --execute 4a161342ae608056fbdfb44a57a25d4d4830b944c0a032bb54d9b9c34f270d48 \
  --out NEW_REPORT.json
```

Twenty-two targeted tests passed. Two fits and two CLI replays per cohort matched byte for byte with DNS and outbound sockets blocked. Storage Guard measured 10.1 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_continuous_backup_calibration.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
