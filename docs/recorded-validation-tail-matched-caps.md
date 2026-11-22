# Sweep CPO’s validation caps against the paid GEPA frontier

The prior language comparison swept native GEPA but ran each CPO policy at one search cap. This replay gives the strict validation race and both reserved-tail policies the same opportunity to use lower caps. It tests every integer CPO cap from 6 to 54, the cost of all nine prompts on six validation cases. It verifies that cap 54 reproduces the cap-180 costs, grades, and path for every episode. Both methods keep the same 26 archived model panels, seeded rosters, independent qualification, and held-out cases. The native comparison retains both GEPA modes and all 350 settings from the prior replay. [Prior comparison](recorded-validation-tail-language-frontier.md) · [Runner](../benchmarks/recorded_validation_tail_matched_caps.py)

Both sides can use one setting across a whole cohort or keep the starts at zero cost. The table uses realized search plus qualification lookups within budgets taken from the prior report. Each paired draw resamples cases within subjects, keeps both models and all seeds together, and reselects the best affordable common setting for each suite. The paired ranges describe those archived frontiers. Choosing a cap on these same grades uses hindsight.

| Cohort | Lookup budget | Best common CPO passes / lookups | Best common GEPA passes / lookups | CPO margin and paired 95% range |
| --- | ---: | ---: | ---: | ---: |
| BBH | 9,309 | 2,107 / 8,546 | 2,089 / 9,101 | +18, −9 to +57 |
| BBH | 10,569 | 2,126 / 10,560 | 2,096 / 10,287 | +30, −1 to +60 |
| LMentry | 4,182 | 882 / 4,017 | 837 / 4,084 | +45, +18 to +71 |
| LMentry | 5,219 | 924 / 4,930 | 842 / 4,571 | +82, +47 to +112 |
| MMLU | 5,714 | 13,443 / 4,907 | 13,429 / 4,885 | +14, +4 to +27 |
| MMLU | 8,776 | 13,452 / 8,079 | 13,447 / 8,776 | +5, −11 to +29 |
| MMLU | 11,814 | 13,453 / 9,879 | 13,447 / 8,776 | +6, −12 to +28 |

At the lowest MMLU budget, a cap of 13 on the strict CPO race led the common comparison. When both suites could choose a separate setting per subject with hindsight, CPO reached 13,460 passes at 5,362 lookups and GEPA reached 13,455 at 5,714. At the 11,814 budget, the one-case tail at cap 28 gained four passes and saved 1,935 lookups versus that policy’s original cap. The common comparison at that budget remained inconclusive. Cap 13 is a candidate for transfer to disjoint archived subjects and model checkpoints. Fresh-prompt performance remains unverified. [All budgets, fixed caps, and attaining subject schedules](recorded-validation-tail-matched-caps-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

Two clean-export runs with sockets and DNS blocked produced identical reports with SHA-256 `b2a7ad3681ebbc05fe199d70f1c008e1072188aa5831146254ba7670cf0ccb78`. Direct replay confirmed 28 selected schedules across 192 panel endpoints. Ten targeted tests passed and the CLI rejected the stale seal. This used zero provider requests. Storage Guard measured 2.7 GiB free. The source export and publication worktree fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_recorded_validation_tail_matched_caps.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_validation_tail_matched_caps
python -B -m benchmarks.recorded_validation_tail_matched_caps \
  --execute 8c12c1e0cc1922a80189aeea87403868d9813f68ecff549ac9969399030369f2 \
  --out NEW_REPORT.json
```
