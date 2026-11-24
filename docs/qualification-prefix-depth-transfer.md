# Choose a CPO search schedule from the paid qualification prefix

The [first-reply fit](quoted-schedule-discovery-transfer.md) picked a validation schedule from the incumbent's first paid qualification reply. The same precheck already reads through the first miss before opening search. This study tests whether the miss position can guide the schedule. Each cycle chooses from the same four-position table. A perfect incumbent ends the precheck without search. The selected schedule receives only validation rows, and independent exact qualification still decides promotion. [Dispatcher](../cpo/qualification_prefix_cycle.py) · [Benchmark](../benchmarks/qualification_prefix_depth_transfer.py)

The fit starts from the frozen first-reply policy and considers every single-position change across the 29 existing actions. It permits up to two improving updates and maximizes final held-out passes, breaking score ties by spending fewer lookups. Every choice must stay within the original discovery router's budget in each cohort. All 70 discovery model-and-task panels across 31 tasks exclude every target task. The precheck, three-cycle layouts, 32 seeds and separate case roles are inherited. For each cached transition, the fit verifies that the real call ledger starts with the qualification prefix that exposes its routing decision.

The first round changes only the fourth position, from halving to retention. An incumbent that first fails on the opening case still gets incumbent-first search. A miss on the second or third case still gets halving with eight challengers and a cap of nine. A miss on the fourth case now retains the incumbent after paying for its precheck. The second round finds no improvement. Discovery passes rise from 84,037 to 84,046 and paid lookups fall from 67,684 to 66,229. Both rounds compare 113 tables.

## Transfer results

Cells show final held-out passes and total paid lookups. The last two columns price the archived controls at the fitted position policy's actual spend. The GEPA column gives the directly attained lower bound and the full-grid upper bound when they differ. The task-tuned simple control uses target holdout grades to select its affordable portfolio of archived uniform and halving schedules.

| Cohort | Miss position | First reply | Existing router | Task-tuned GEPA passes | Task-tuned simple |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,344 / 13,285 | 6,347 / 13,501 | 6,389 / 13,797 | 6,350 | 6,395 / 13,081 |
| Bounded LMentry | 6,338 / 15,559 | 6,338 / 15,666 | 6,321 / 15,711 | 3,855–5,931 | 6,341 / 15,401 |
| Bounded MMLU | 7,719 / 6,442 | 7,719 / 6,630 | 7,725 / 7,696 | 7,706–7,717 | 7,732 / 6,001 |
| Four-case MMLU | 22,369 / 10,465 | 22,369 / 10,728 | 22,381 / 12,145 | 22,369 | 22,409 / 10,430 |
| Tie BBH | 2,145 / 12,480 | 2,145 / 12,541 | 2,204 / 13,130 | 1,944–2,126 | 2,169 / 12,460 |
| Tie LMentry | 980 / 6,961 | 992 / 6,976 | 1,028 / 7,195 | 919 | 1,013 / 6,884 |
| Additional MMLU | 7,396 / 6,211 | 7,399 / 6,468 | 7,384 / 7,257 | 7,399 | 7,405 / 5,354 |

The position policy saves 1,107 lookups and loses 18 passes relative to the first-reply policy. It saves lookups in every cohort and falls below the first-reply policy in three. Tie LMentry accounts for 12 of those 18 passes, with a paired 95% range of −19 to −4 and just 15 lookups saved. The four cohorts with unchanged totals account for 619 saved lookups. The aggregate counts describe this archive because some tasks occur in multiple cohorts.

The position policy exceeds the task-tuned native GEPA upper bound in four cohorts, ties it in four-case MMLU, and falls below the verified feasible native score in bounded BBH and additional MMLU. The affordable task-tuned simple schedule scores higher in every cohort and spends fewer lookups. Keep the first-reply schedule as the benchmark baseline. The first miss position supplies a zero-extra-probe signal for saving reads, but the discovery result did not establish that fourth-position retention protects quality on separate tasks. Fresh live performance remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview each seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.qualification_prefix_depth_transfer --fit \
  --execute 4c53e2edb436e727106f1dc58af2b0769dc60930f646caec1ab04db7290037f6 \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.qualification_prefix_depth_transfer \
  --cohort tie-LMentry --fitted NEW_FIT.json \
  --execute 4cb8df7789513b66bf6db8a5d8abd5112b6eb7cfa9704db3d03261a4e78145a2 \
  --out NEW_REPORT.json
```

[Frozen fit](qualification-prefix-depth-fit-v1.json) · [Bounded BBH](qualification-prefix-depth-transfer-bounded-bbh-v1.json) · [Bounded LMentry](qualification-prefix-depth-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](qualification-prefix-depth-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](qualification-prefix-depth-transfer-four-case-mmlu-v1.json) · [Tie BBH](qualification-prefix-depth-transfer-tie-bbh-v1.json) · [Tie LMentry](qualification-prefix-depth-transfer-tie-lmentry-v1.json) · [Additional MMLU](qualification-prefix-depth-transfer-additional-mmlu-v1.json)

Eighteen targeted tests passed. Two independent fits and two replays of all 2,048 target episodes matched byte for byte with DNS and outbound sockets blocked. The replay verified the prior first-reply and router scores, costs and paid trajectories. It issued zero provider requests. Storage Guard measured 9.8 GiB free. The temporary source export, wheel overlay and publication checkout fit under the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_qualification_prefix_cycle.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
