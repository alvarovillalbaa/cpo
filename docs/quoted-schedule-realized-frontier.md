# Price the strongest archived alternatives at CPO's actual audit spend

The [guarded checkpoint transfer](quoted-schedule-guarded-transfer.md) kept calibration budgets equal across methods while their audit spending differed. This replay compares alternatives at three realized audit budgets from that study. It exactly reproduces the guarded schedule, the original task-calibrated quoted schedule, and the frozen CPO prefix on the same models, scoring folds and audit seeds. [Benchmark runner](../benchmarks/quoted_schedule_realized_frontier.py)

The native GEPA menu uses split-safe train and validation caches, the two native search modes, full and half validation, and six qualification wrappers. It sweeps every funded integer cap through 180, the original full-grid limit. The simple menus use fixed uniform and successive-halving schedules at four and eight challengers. Both eager and quoted accounting are compared on the same simple settings. Each menu includes free retention. All methods see the same original per-cycle prompt pools and role boundaries, and carry the deployed prompt through all three cycles.

For each cohort and budget, the common control picks one setting for every direction. The mixed control can use one setting per audit direction and a single pooled lookup budget. Both maximize archived holdout passes and then minimize realized cost. The runner verifies every chosen setting by direct replay. These are retrospective optima within the measured menus. The mixed result measures headroom for task and model selection using grades that a deployed policy would not yet have. The paired ranges describe the attained settings, conditional on those choices.

## Guarded CPO budget

Cells give final held-out passes and actual paid lookups. Each control fits within the guarded budget shown for that cohort.

| Cohort | Guarded CPO | Common GEPA | Mixed GEPA | Mixed eager simple | Mixed quoted simple |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 1,643 / 5,860 | 1,636 / 4,901 | 1,677 / 5,747 | 1,705 / 5,770 | 1,712 / 5,708 |
| Bounded LMentry | 1,590 / 7,720 | 1,278 / 7,072 | 1,611 / 7,688 | 1,670 / 7,618 | 1,692 / 7,603 |
| Bounded MMLU | 1,922 / 1,913 | 1,928 / 0 | 1,932 / 1,190 | 1,932 / 1,898 | 1,932 / 1,450 |
| Four-case MMLU | 5,544 / 2,257 | 5,538 / 0 | 5,539 / 425 | 5,554 / 1,786 | 5,557 / 2,241 |
| Tie BBH | 495 / 6,230 | 485 / 4,847 | 512 / 6,024 | 519 / 6,172 | 522 / 6,101 |
| Tie LMentry | 244 / 3,393 | 223 / 3,311 | 253 / 2,800 | 275 / 3,273 | 285 / 3,047 |
| Additional MMLU | 1,803 / 1,467 | 1,802 / 0 | 1,804 / 423 | 1,807 / 1,281 | 1,807 / 929 |

Guarded CPO scored above the best common GEPA setting in six cohorts. It scored above the best mixed GEPA setting only in four-case MMLU, by five passes. In bounded LMentry, CPO beat the common GEPA setting by 312 passes, while mixed GEPA scored 21 more than CPO using 32 fewer lookups. The mixed quoted simple menu scored 102 more than CPO there and used 117 fewer lookups. Its paired range was +74 to +129.

The best mixed quoted simple schedule scored higher and used fewer lookups in all 21 comparisons across the three CPO budgets and seven cohorts. At the guarded budgets its pooled gap was 266 passes and 1,761 fewer lookups. It retained the incumbent in 27 of 64 directions. Of the 37 active directions, 20 used eight challengers and 17 used four. The pooled totals describe the prior archive mix, where cohorts can reuse tasks. The headroom requires choosing when to retain, which roster to fund, and how much to spend before seeing the audit outcomes.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview each seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.quoted_schedule_realized_frontier \
  --cohort bounded-LMentry \
  --execute 2531d4524890fa9db512e9325958775fe28301dadab2998f1f48bc3dec01bece \
  --out NEW_REPORT.json
```

[Bounded BBH](quoted-schedule-realized-frontier-bounded-bbh-v1.json) · [Bounded LMentry](quoted-schedule-realized-frontier-bounded-lmentry-v1.json) · [Bounded MMLU](quoted-schedule-realized-frontier-bounded-mmlu-v1.json) · [Four-case MMLU](quoted-schedule-realized-frontier-four-case-mmlu-v1.json) · [Tie BBH](quoted-schedule-realized-frontier-tie-bbh-v1.json) · [Tie LMentry](quoted-schedule-realized-frontier-tie-lmentry-v1.json) · [Additional MMLU](quoted-schedule-realized-frontier-additional-mmlu-v1.json)

Eighteen targeted tests passed, including a brute-force check of both matching rules on a fixture. Two replays per cohort matched byte for byte with DNS and outbound sockets blocked. Each audit direction swept 4,237 native settings including retention. The study verified 1,024 audit episodes and issued zero provider requests. Storage Guard measured 9.9 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_quoted_schedule_realized_frontier.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
