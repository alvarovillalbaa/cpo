# Reinvest certified shortlist savings at the lowest search ceiling

The [disjoint-case audit](recorded-math-budget-crossfit.md) found that simple search scored higher on both low-ceiling ARC-AGI rotations and paid for more reads. CPO now has a fixed-roster cycle that can use saved slots to compare more shared validation rows. It quotes the incumbent and all active challengers before starting a row. At a halving round or the last row, a challenger read can be skipped only when its best possible grade cannot change the exact shortlist. Every surviving prompt has a measured grade on every shared row. A nominee must beat the incumbent on measured rows and then pass the separate exact qualification proof. Critical validation rows use the original strict two-sided screen. [Cycle implementation](../cpo/reinvested_shared_validation_cycle.py)

Call `run_reinvested_shared_validation_cycle` from `cpo.reinvested_shared_validation_cycle` with an incumbent, an ordered roster, disjoint validation and qualification rows, and the existing evaluator and qualification callbacks. Set `metric_limit` to cap validation lookups. Qualification can read at most two replies per qualification row. The cycle returns the search and qualification decisions, including the prompt to carry forward. [Callback and budget examples](../tests/unit/test_reinvested_shared_validation_cycle.py)

## Low-ceiling audit

The replay retains the earlier case folds, qualification and candidate pools. It tests all integer search caps through 19 that can fund a first shared round, at four challengers and, where available, eight. The full search-plus-qualification ceiling is 31 lookups per ARC-AGI episode and 27 per AIME episode. Within each direction, the expanded CPO menu adopts the new setting only when the calibration fold shows higher score or equal score at lower cost. Every selected audit result uses the setting named on its calibration fold. The previous GEPA, simple and CPO audit points reproduce exactly. [Benchmark runner](../benchmarks/recorded_math_reinvested_halving.py)

The ablation uses the same certified read skipping and keeps the original full-round funding decisions. Its nomination, qualification and paid-read subset match eager halving across the swept calibration paths and every selected audit path. The ablation measures the effect of spending saved slots on additional rounds at the selected cap.

| ARC-AGI start and roster | Old CPO | Expanded CPO | GEPA | Simple search |
| --- | ---: | ---: | ---: | ---: |
| Root, four | 1,023 / 1,759 | 1,023 / 1,957 | 974 / 1,666 | 1,030 / 2,076 |
| Root, eight | 1,023 / 1,759 | 1,061 / 2,049 | 974 / 1,666 | 1,030 / 2,076 |
| Rotated, four | 9,525 / 10,160 | 9,615 / 14,159 | 9,412 / 8,318 | 9,598 / 14,209 |
| Rotated, eight | 9,525 / 10,328 | 9,615 / 14,159 | 9,412 / 8,318 | 9,544 / 13,795 |

Cells give held-out passes and paid lookups across both audit folds. Calibration selected the new cycle in every ARC-AGI configuration and kept the old CPO setting in every AIME configuration. On both ARC-AGI rotations, the new method selected the four-challenger, 19-read setting. Reinvestment bought 531 additional validation rounds on each rotation and gained 17 passes over the same certified screen without reuse. It gained 31 passes and saved 27 lookups against simple search with eight challengers at the root, with a paired 95% range of +19 to +44. With four challengers on rotated starts it gained 17 passes and saved 50 lookups, with a range of +5 to +31. The eight-challenger rotation gained 71 passes for 364 additional lookups. The four-challenger root lost seven passes to simple search.

The expanded CPO menu used more lookups than GEPA in every ARC-AGI comparison. The new method spent more than the previous CPO setting in all four ARC-AGI configurations and improved scores in three. AIME results stayed inconclusive. The audit cases were separate from per-setting calibration. The design was informed by a previous replay on these same archives, so the result still needs independent transfer.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview the seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_math_reinvested_halving \
  --group rotated --width 8 \
  --execute 90f9a9c6a4f00531596aefa2578030af84481dee8e6199686dccd2ea822ed1b3 \
  --out NEW_REPORT.json
```

[Root, four](recorded-math-reinvested-halving-root-4-v1.json) · [Root, eight](recorded-math-reinvested-halving-root-8-v1.json) · [Rotated, four](recorded-math-reinvested-halving-rotated-4-v1.json) · [Rotated, eight](recorded-math-reinvested-halving-rotated-8-v1.json)

Twenty targeted tests passed. Duplicate replays matched byte for byte across 3,040 audit episodes with DNS and outbound sockets blocked. The study issued zero provider requests. Storage Guard measured 10.0 GiB free. The temporary source export, wheel overlay and publication checkout fit within the standing 0.2 GiB LAB exception. [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
