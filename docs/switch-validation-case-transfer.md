# Switch validation cases after repeated failures

The [bounded opening](bounded-opening-repair-transfer.md) saved lookups by stopping after two unsuccessful challengers when qualification had reached its last case. This experiment tests a different response to repeated failure. When the incumbent and the first two, four, or six challengers all fail an opening validation case, the screen spends one lookup on the incumbent's next case. If the incumbent passes, search resumes on the opening case. If it fails, the screen probes challengers on the next case, either in original order or with unopened challengers first. The first passing challenger is nominated on the observed repair. Deployment still requires the existing independent qualification. The screen preserves the nine-lookup cap, leaves a passing first case alone, and defers critical panels to the original screen. [Screen](../cpo/switch_validation_case.py) · [Benchmark](../benchmarks/switch_validation_case_transfer.py)

The first paid qualification miss keeps incumbent-first search. At the remaining three miss positions the fitter can select the original quote, the shorter opening, or any of the six switching actions. It tests all 512 tables on the frozen 70 discovery panels from 31 tasks, with every target task excluded. One fit uses the existing router budgets. The other limits each discovery cohort to the bounded opening's observed spend. A fixed switch after two challenger failures, prioritizing unopened challengers, is evaluated on all three eligible positions.

## Discovery

The bounded opening scored 84,043 passes for 67,022 lookups. Both fits selected it again. Under router budgets, 458 of the 512 tables were feasible. At the bounded opening's cost, 83 were feasible. The fixed switch scored 84,020 passes for 67,921 lookups. The fits reproduced the first-reply and bounded opening scores and prices in every discovery cohort. [Frozen discovery receipt](switch-validation-case-fit-v1.json)

## Target results

Cells show held-out passes and paid lookups. Both fitted schedules reproduce every paid path of the bounded opening. The last two columns price the task-tuned controls at the fixed switch's realized spend. The simple control uses target holdout grades to choose an affordable schedule per subject. The native column is an upper bound from the previous split-safe full-grid sweep.

| Cohort | Bounded opening and both fits | Fixed switch | Router lookups | Fixed switch GEPA upper bound | Fixed switch task-tuned simple |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,347 / 13,421 | 6,327 / 13,551 | 13,797 | 6,350 | 6,397 / 13,505 |
| Bounded LMentry | 6,338 / 15,636 | 6,368 / 15,648 | 15,711 | 5,931 | 6,341 / 15,401 |
| Bounded MMLU | 7,719 / 6,554 | 7,724 / 6,634 | 7,696 | 7,717 | 7,732 / 6,001 |
| Four-case MMLU | 22,369 / 10,591 | 22,369 / 10,739 | 12,145 | 22,369 | 22,409 / 10,430 |
| Tie BBH | 2,145 / 12,521 | 2,146 / 12,588 | 13,130 | 2,126 | 2,169 / 12,460 |
| Tie LMentry | 992 / 6,971 | 995 / 6,996 | 7,195 | 919 | 1,013 / 6,884 |
| Additional MMLU | 7,398 / 6,354 | 7,398 / 6,485 | 7,257 | 7,399 | 7,405 / 5,354 |

Across 2,048 archived episodes, the fixed switch gained 19 passes and spent 593 more lookups than the bounded opening. It stayed within all seven router budgets. On bounded LMentry it gained 30 passes for 12 more lookups, with a paired 95% range of +13 to +46. It also gained 47 passes over the router at 63 fewer lookups there. The switch exceeded the simple schedule's point score by 27 at the switch's budget, with a paired range of −38 to +89. On bounded BBH it lost 20 passes against the bounded opening and used 130 additional lookups. The paired range was −41 to +1.

The fixed switch exceeded the task-tuned GEPA upper bound in four cohorts, tied in one, and fell below the verified affordable native score in two. It led the task-tuned simple point score only on bounded LMentry. Discovery retained the bounded opening, so the switch remains an experimental option. Fresh live superiority remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview either seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.switch_validation_case_transfer --fit \
  --execute f8051882ae58810a49eba2f761d02016fb8c2f18d2203b50fe290dc3d70ff659 \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.switch_validation_case_transfer \
  --cohort bounded-LMentry --fitted NEW_FIT.json \
  --execute 440aa9c531a60daedc69729009d71ed1b5f1c77f90c2f4995a2e78212e674e33 \
  --out NEW_REPORT.json
```

[Bounded BBH](switch-validation-case-transfer-bounded-bbh-v1.json) · [Bounded LMentry](switch-validation-case-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](switch-validation-case-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](switch-validation-case-transfer-four-case-mmlu-v1.json) · [Tie BBH](switch-validation-case-transfer-tie-bbh-v1.json) · [Tie LMentry](switch-validation-case-transfer-tie-lmentry-v1.json) · [Additional MMLU](switch-validation-case-transfer-additional-mmlu-v1.json)

Sixty targeted tests passed. Duplicate fits and target replays matched byte for byte with DNS and outbound sockets blocked. The runner reproduced the original router, first-reply, and bounded opening traces, and made zero provider requests. Storage Guard measured 9.7 GiB free. The source export, dependency overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Focused tests](../tests/unit/test_switch_validation_case.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
