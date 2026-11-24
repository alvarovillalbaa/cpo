# Isolate promotion and lookup forecasts in terminal backup ranking

Calibration on backup options improved lookup-cost forecasts and weakened one-probe promotion forecasts. The jointly corrected ranker also lost held-out passes. This replay separates the two forecast changes while keeping the same task-balanced allocator, candidates, probe cases, exact qualification and full start quotes. [Calibration benchmark](continuous-backup-calibration.md) · [Ablation runner](../benchmarks/continuous_backup_calibration_ablation.py)

The original ranking divides predicted promotion probability by expected lookup cost. Each empirical or corrected calibration now supplies either the numerator or denominator on its own. Both calibrations use the exact discovery fit from the prior study. The replay reproduces all three original arms and verifies that the forecast error for each retained component is identical over the full offer menu.

Every arm uses the original global allocator's realized backup spend as the cohort ceiling. Actual charges determine whether the next quote fits. The subject-tuned uniform and halving controls are repriced and replayed at each arm's actual lookup count. No transfer result enters the forecast or rank.

## Results

The table gives changes in held-out passes and backup lookups relative to the original ranker. The original gained 54 passes at 285 backup lookups for paid repair and 66 passes at 545 backup lookups for one probe, each relative to joint qualification alone.

| Calibration | Component changed | Paid repair | One probe |
| --- | --- | ---: | ---: |
| Empirical | Cost | −1 / 0 | −1 / +1 |
| Empirical | Probability | −13 / −4 | −20 / +1 |
| Empirical | Both | −12 / −5 | 0 / −1 |
| Corrected | Cost | 0 / +1 | 0 / −1 |
| Corrected | Probability | −14 / −6 | −14 / +5 |
| Corrected | Both | −14 / −6 | −15 / −3 |

Replacing just the corrected probability produced almost the full one-probe score loss of the joint correction. On tie LMentry, changing either probability forecast lost 13 passes in each backup mode, with a paired 95% range of −19 to −7. Both cost-only changes preserved the original score there.

The cost-only correction preserved every one-probe deployment across 2,048 episodes and saved one realized lookup. It kept the original promotion forecast's menu-wide mean squared error of 0.04451 and reduced mean absolute lookup error per offer from 0.903 to 0.856. It added one lookup to paid repair.

[Bounded BBH](continuous-backup-calibration-ablation-bounded-bbh-v1.json) · [Bounded LMentry](continuous-backup-calibration-ablation-bounded-lmentry-v1.json) · [Bounded MMLU](continuous-backup-calibration-ablation-bounded-mmlu-v1.json) · [Four-case MMLU](continuous-backup-calibration-ablation-four-case-mmlu-v1.json) · [Tie BBH](continuous-backup-calibration-ablation-tie-bbh-v1.json) · [Tie LMentry](continuous-backup-calibration-ablation-tie-lmentry-v1.json) · [Additional MMLU](continuous-backup-calibration-ablation-additional-mmlu-v1.json)

These are repeated archive replays on the same transfer cohorts. Live optimization quality remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Preview a different cohort's seal by omitting `--execute` and `--out`. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_backup_calibration_ablation \
  --cohort bounded-LMentry \
  --execute e0ecafa54514e6e696e168db031f25360fdfdd9687675e6419daf24259833421 \
  --out NEW_REPORT.json
```

Twenty-four targeted tests passed. Two CLI replays per cohort matched byte for byte with DNS and outbound sockets blocked. The unchanged forecasting components and all original arms reproduced their recorded errors, spend and scores. A direct, independent replay compared each cost-only one-probe deployment with the original and matched both dispatch receipts. Storage Guard measured 9.9 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_continuous_backup_calibration_ablation.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
