# Can a shorter opening fund a second validation case?

The [second-row repair replay](second-row-validation-transfer.md) recovered challengers on BBH and LMentry, with higher lookup costs. This experiment tests whether paying fewer challenger checks on an opening incumbent miss can fund those repairs. The original one-row screen may read eight challengers in order. An opening limit of two, four or six still stops at the first passing challenger. It retains the incumbent if every challenger within the limit fails. On an opening incumbent pass, the optional second-row search keeps its full original repair roster. Neither branch changes the nine-lookup validation cap or the independent qualification proof. [Screen](../cpo/bounded_opening_repair.py) · [Benchmark](../benchmarks/bounded_opening_repair_transfer.py)

The fit preserves the incumbent-first screen when the first paid qualification reply fails. At each of the three later first-miss positions it can choose any of the original three screens or six new combinations of opening limit and second-row repair. Every choice uses the same 70 discovery panels across 31 tasks, with all target tasks excluded. The fit verifies the outcomes and prices of all 27 earlier tables before considering the expanded 729-table menu.

## Discovery

All three fits selected the same schedule. After a fourth-position qualification miss, the schedule tests at most two challengers if the incumbent fails the opening validation case. At the other positions, it retains the previous screen. It never buys the second row.

| Fit | Feasible tables | Discovery passes / lookups |
| --- | ---: | ---: |
| Original first-reply policy | 1 | 84,037 / 67,684 |
| Expanded menu within router budgets | 222 of 729 | 84,043 / 67,022 |
| Width-only menu within router budgets | 64 of 64 | 84,043 / 67,022 |
| Expanded menu within original first-reply spend | 127 of 729 | 84,043 / 67,022 |

The chosen table used fewer lookups in every discovery cohort. Its extra passes came from BBH/new-task and the disjoint transfer discovery cohort. The two budgeted fits use realized cost ceilings from discovery only. [Frozen fit](bounded-opening-repair-fit-v1.json)

## Transfer

Cells show final held-out passes and actual lookups. All three fitted policies produce identical traces. The full-width second-row control reproduces its earlier archived replay. The last two columns price the controls at the fitted policy's actual spend. Task-tuned simple settings use target holdout grades to choose an affordable portfolio.

| Cohort | Original first-reply | Fitted opening limit | Full-width second row | Task-tuned GEPA upper bound | Task-tuned simple |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,347 / 13,501 | 6,347 / 13,421 | 6,376 / 14,551 | 6,350 | 6,395 / 13,081 |
| Bounded LMentry | 6,338 / 15,666 | 6,338 / 15,636 | 6,399 / 16,461 | 5,931 | 6,341 / 15,401 |
| Bounded MMLU | 7,719 / 6,630 | 7,719 / 6,554 | 7,718 / 7,295 | 7,717 | 7,732 / 6,001 |
| Four-case MMLU | 22,369 / 10,728 | 22,369 / 10,591 | 22,369 / 11,550 | 22,369 | 22,409 / 10,430 |
| Tie BBH | 2,145 / 12,541 | 2,145 / 12,521 | 2,154 / 12,882 | 2,126 | 2,169 / 12,460 |
| Tie LMentry | 992 / 6,976 | 992 / 6,971 | 992 / 7,053 | 919 | 1,013 / 6,884 |
| Additional MMLU | 7,399 / 6,468 | 7,398 / 6,354 | 7,399 / 7,190 | 7,399 | 7,405 / 5,354 |

The fitted limit saved 462 lookups across 2,048 episodes, with one fewer pass. The additional MMLU loss had a paired 95% range of −3 to 0. Compared with [retaining immediately after a fourth-position miss](qualification-prefix-depth-transfer.md), the two-probe limit recovered 12 passes on tie LMentry for 10 more lookups. The pooled counts describe the archived mix of tasks.

The fitted limit exceeded the task-tuned native GEPA upper bound in four cohorts and tied in one. The simple portfolio still scored higher at lower cost in all seven. The opening limit reduced spend with nearly unchanged archived quality. The fitted policy found no quality gain from using those savings to buy a second row. Fresh live quality remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview each seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.bounded_opening_repair_transfer --fit \
  --execute bb2b42920aea83045dc4552761ce50e867ad393c80fd2d2264382f56567629d5 \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.bounded_opening_repair_transfer \
  --cohort tie-LMentry --fitted NEW_FIT.json \
  --execute 520ec2f7e7899a08ee2cfd333146f66aa8b12b75dfe176d1ee6521105b43941c \
  --out NEW_REPORT.json
```

[Bounded BBH](bounded-opening-repair-transfer-bounded-bbh-v1.json) · [Bounded LMentry](bounded-opening-repair-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](bounded-opening-repair-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](bounded-opening-repair-transfer-four-case-mmlu-v1.json) · [Tie BBH](bounded-opening-repair-transfer-tie-bbh-v1.json) · [Tie LMentry](bounded-opening-repair-transfer-tie-lmentry-v1.json) · [Additional MMLU](bounded-opening-repair-transfer-additional-mmlu-v1.json)

Forty-seven targeted tests passed. Duplicate fits and target replays matched byte for byte with DNS and outbound sockets blocked. Source hashes and the original router, first-reply and full-width second-row paths reproduced. The benchmark issued zero provider requests. Storage Guard measured 9.8 GiB free. The temporary source export, wheel overlay and publication checkout fit under the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_bounded_opening_repair.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
