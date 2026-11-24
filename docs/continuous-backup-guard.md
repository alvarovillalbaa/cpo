# Check that a terminal backup preserves an incumbent pass

The previous experiment found that choosing a different single repair case left deployments unchanged. Most of the hindsight headroom remained in choosing which backups to fund. This experiment tests whether stronger paid validation evidence improves that choice. It keeps the three settled primary cycles, the saved lookup allowance, and the earlier backup probability ranking. [Witness and allocation diagnosis](continuous-backup-witness.md) · [Replay runner](../benchmarks/continuous_backup_guard.py)

Before independent qualification, a backup must pass a case the incumbent was observed to miss and preserve a case it was observed to pass. The replay compares three policies.

- **Cached pass** uses a previously paid validation pass for both prompts. The challenger can still buy the original repair probe.
- **One read** can buy the missing preservation grade for an already-paid repair. It permits at most one new validation grade per attempt.
- **Two reads** can buy the original repair probe and then the missing preservation grade in one attempt.

A failed repair or preservation check stops the attempt. The start quote reserves both possible validation reads and every unread proof grade. The independent proof uses the original joint order and exact net gain on the original qualification cases. The replay reproduces the unguarded paid-repair and one-probe controls, then reprices the best subject-tuned simple controls at each new policy's actual spend. The settled-price hindsight bounds use recorded outcomes to select backups and retain the full start quotes for the feasible lower bound.

## Results

Cells show final held-out pass change and additional lookups versus joint qualification without backups. The last column gives the maximum hindsight gain for the two-read menu at its full cohort allowance. Its feasible lower bound and settled-charge upper bound agreed in every cohort.

| Cohort | Cached pass | One read | Two reads | Two-read hindsight gain |
| --- | ---: | ---: | ---: | ---: |
| [Bounded BBH](continuous-backup-guard-bounded-bbh-v1.json) | 0 / 36 | −7 / 77 | −7 / 77 | +23 |
| [Bounded LMentry](continuous-backup-guard-bounded-lmentry-v1.json) | 0 / 8 | +3 / 29 | +4 / 48 | +23 |
| [Bounded MMLU](continuous-backup-guard-bounded-mmlu-v1.json) | 0 / 0 | 0 / 0 | 0 / 0 | 0 |
| [Four-case MMLU](continuous-backup-guard-four-case-mmlu-v1.json) | 0 / 21 | 0 / 33 | 0 / 69 | 0 |
| [Tie BBH](continuous-backup-guard-tie-bbh-v1.json) | +1 / 11 | +1 / 19 | +9 / 93 | +12 |
| [Tie LMentry](continuous-backup-guard-tie-lmentry-v1.json) | 0 / 0 | 0 / 4 | 0 / 16 | +3 |
| [Additional MMLU](continuous-backup-guard-additional-mmlu-v1.json) | +3 / 11 | +3 / 17 | +3 / 48 | +5 |
| Total | +4 / 87 | 0 / 179 | +9 / 351 | +66 |

Two reads performed best on tie BBH. It added two passes over unguarded one probe and saved 127 lookups, with a paired 95% range of −8 to +11. On bounded LMentry it lost 38 passes against either unguarded rule, with a range of −52 to −24. Even using recorded outcomes to choose the attempts, the two-read menu could recover only 23 passes there. Either earlier rule had already recorded a 42-pass gain.

The hard preservation condition reduced the seven-cohort hindsight capacity from 194–197 passes with the original one-probe candidates to 66 passes with two reads. The cached and one-read menus had settled-price maxima of four and 14 passes respectively. The previous paid-repair policy gained 51 passes at 299 added lookups, compared with nine passes at 351 lookups for two reads. The evidence uses archived candidate rosters and grades. Live quality remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Preview a different cohort's seal by omitting `--execute` and `--out`. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_backup_guard \
  --cohort bounded-LMentry \
  --execute 5585a9d98331e6c10a8fc0e58e62a2c278989b19672b7a3d1c05618c1a765bec \
  --out NEW_REPORT.json
```

Seventeen targeted tests passed. Two CLI replays per cohort matched byte for byte with DNS and outbound sockets blocked. All backup attempts stayed within their reserved budgets. Storage Guard measured 10.0 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_continuous_backup_guard.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
