# Rank terminal backups by predicted held-out gain

The terminal backup benchmark recovered 51 held-out passes by reusing paid repair evidence. Its one-probe policy had larger hindsight headroom, especially on bounded BBH and LMentry. This experiment tests a different ranking under the same savings-funded ceilings. It preserves the three primary cycles, eligibility rules, backup quotes, incumbent qualification cache, and exact independent gain required for promotion. [Terminal backup benchmark](continuous-archive-backup.md) · [Replay runner](../benchmarks/continuous_backup_value.py)

The discovery fit replays every eligible terminal one-probe option on the 70 panels used to fit joint reply ordering. It excludes every task name in the seven transfer cohorts. Each label records the actual additional lookups and signed held-out pass-rate change after the probe and the proof. A failed probe or rejection leaves the incumbent in place and contributes zero gain with its charged cost. The estimate uses the pooled mean, then narrows by probe requirement, one or multiple observed incumbent qualification misses, and the coarse validation rates. Each narrower estimate carries 24 prior observations from its parent group. Unseen contexts inherit their parent's estimate.

At transfer, the scheduler ranks expected pass-rate gain per additional lookup and declines options with a nonpositive estimate. The controls reproduce both earlier, qualification-probability rankings before applying the new rule. The paired comparison gives all versions their original cohort lookup ceilings. It also reprices the best common and subject-tuned simple controls to each new policy's actual spend. No transfer holdout grade is used to fit or rank a backup.

## Results

Discovery produced 2,646 labeled options with 107 promotions. All fitted contexts predicted positive gain, so the transfer differences came from reordering. The table gives the change in held-out passes and actual lookups from each earlier probability ranking. [Discovery receipt](continuous-backup-value-fit-v1.json)

| Cohort | Value-ranked paid repair | Value-ranked one probe |
| --- | ---: | ---: |
| [Bounded BBH](continuous-backup-value-bounded-bbh-v1.json) | −6 / 0 | +1 / +2 |
| [Bounded LMentry](continuous-backup-value-bounded-lmentry-v1.json) | −14 / +2 | −20 / 0 |
| [Bounded MMLU](continuous-backup-value-bounded-mmlu-v1.json) | 0 / 0 | 0 / 0 |
| [Four-case MMLU](continuous-backup-value-four-case-mmlu-v1.json) | 0 / 0 | 0 / −1 |
| [Tie BBH](continuous-backup-value-tie-bbh-v1.json) | 0 / 0 | −2 / −1 |
| [Tie LMentry](continuous-backup-value-tie-lmentry-v1.json) | 0 / 0 | +6 / −1 |
| [Additional MMLU](continuous-backup-value-additional-mmlu-v1.json) | 0 / 0 | −3 / +1 |
| Total | −20 / +2 | −18 / 0 |

The one-probe ranker made 305 attempts and 12 promotions at 562 lookups. Its probability control made 246 attempts and 23 promotions at the same price. On bounded LMentry the paired 95% ranges against the original rankings were −22 to −6 for paid repair and −29 to −11 for one probe. The new ranker's six-pass gain on tie LMentry had a paired range of −5 to +16. It finished 28 passes ahead of the matched subject-tuned simple score there, with a range of −2 to +60.

The earlier probability ranking remains the stronger archived comparison. Paired ranges resample cases within task with selected comparator settings held fixed. The transfer cohorts had already been used to compare earlier policies, and this replay uses archived prompt rosters and grades. Live quality remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Preview a different cohort's seal by omitting `--execute` and `--out`. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_backup_value --fit NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_backup_value \
  --fitted NEW_FIT.json --cohort bounded-LMentry \
  --execute edabec87ff44015e66ab407117da6e7e8191016e2e6afdef730c08b4efab530f \
  --out NEW_REPORT.json
```

Two fits and two CLI replays per cohort matched byte for byte with DNS and outbound sockets blocked. Fifteen targeted tests passed, and a fit with a changed source checksum was rejected. Storage Guard measured 10.0 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_continuous_backup_value.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
