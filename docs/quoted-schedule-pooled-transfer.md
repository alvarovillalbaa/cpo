# Fit a shared lookup budget before the audit

The [realized-budget frontier](quoted-schedule-realized-frontier.md) showed that a fixed budget could buy more archived passes if a selector shifted spending across tasks and models. This study fits that allocation before the audit. It uses the original opposite-model calibration folds and seeds. The audit retains the separate model, scoring cases, seeds, prompt rosters, and independent qualification panels. [Runner](../benchmarks/quoted_schedule_pooled_transfer.py)

The fit can select a uniform or successive-halving schedule, the frozen discovery prefix, or retention for each direction. The pooled fit maximizes calibration passes under one cohort lookup allowance. The local control splits that same allowance in proportion to the calibration router's spend and chooses independently within each share. An eager pooled control uses the same choice menu and fit procedure with eager prices. The fitter uses the smaller of the calibration router's total spend and the cohort audit ceiling. The published guarded CPO spend supplies the fixed audit ceiling for every arm. The choice uses calibration grades and the aggregate ceiling only.

Audit directions are interleaved by seed. Before a search cycle can start, the runner reserves both sides of its entire qualification panel and limits search to the rest of the pooled budget. If the remaining balance cannot fund the validation minimum and this reserve, the cycle retains its incumbent. Audit spend includes all actual validation and qualification reads. Selection uses archived grades. [Budget tests](../tests/unit/test_quoted_schedule_pooled_transfer.py)

The first replay found losses concentrated in a few reallocated directions. A follow-up fit admits only settings that match or beat the local setting on both halves of that direction's calibration cases. The local portfolio remains feasible by construction. The optimizer can still use the shared budget to fund more expensive settings. Both halves are used for this constraint. The audit uses the original separate model, cases and seeds.

## Audit results

Each cell gives held-out passes and actual paid lookups. The prior guarded CPO spend is the hard ceiling for the other three columns.

| Cohort | Local quoted | Pooled quoted | Pooled with local score floor | Guarded CPO |
| --- | ---: | ---: | ---: | ---: |
| Bounded BBH | 1,628 / 2,989 | 1,630 / 4,759 | 1,630 / 4,759 | 1,643 / 5,860 |
| Bounded LMentry | 1,509 / 6,608 | 1,403 / 7,327 | 1,534 / 7,708 | 1,590 / 7,720 |
| Bounded MMLU | 1,924 / 478 | 1,924 / 1,404 | 1,924 / 1,404 | 1,922 / 1,913 |
| Four-case MMLU | 5,538 / 0 | 5,538 / 1,285 | 5,538 / 1,088 | 5,544 / 2,257 |
| Tie BBH | 485 / 4,548 | 484 / 6,225 | 494 / 6,085 | 495 / 6,230 |
| Tie LMentry | 261 / 3,153 | 220 / 3,382 | 243 / 3,381 | 244 / 3,393 |
| Additional MMLU | 1,802 / 0 | 1,802 / 1,141 | 1,802 / 1,141 | 1,803 / 1,467 |

Unconstrained quoted pooling gained 160 passes over local allocation in calibration. On audit it lost 146 passes and spent 7,747 more lookups. In bounded LMentry, replacing the local schedule on one rhyming-word direction with retention lost 73 of the 106 missing passes. The hard budget never clipped a cycle in that cohort for the unconstrained quote, so the loss followed from the selected settings. Relative to pooled eager execution and fitting, pooled quoted selection gained 105 pooled audit passes and used 1,636 fewer lookups. The counts are descriptive because cohorts reuse some tasks.

The local score floor gained 164 pooled audit passes over unconstrained pooling for 43 more lookups. It gained 131 on bounded LMentry, with a paired range of +102 to +159. The protected allocation also gained 25 passes over local allocation there, with a range of +4 to +45, spending 1,100 more lookups. In tie BBH it gained nine passes over local allocation, with a range of +1 to +17. It still lost 18 passes to local allocation on tie LMentry and 76 pooled passes to the previous guarded CPO policy. The task-tuned native and quoted-simple hindsight portfolios scored higher at the protected policy's budget ceiling in every cohort. Fresh-task performance remains unverified.

Every audit finished within its cohort ceiling. The hard budget clipped 13 cycles in unconstrained quoted pooling and 17 with the local score floor. All attempts preserved their independent qualification reserve.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview each seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.quoted_schedule_pooled_transfer \
  --cohort bounded-LMentry \
  --execute 9e545e1f45513db8aa29bcf2ebfd60ff85d382caf082d069d42da6cec5756f3a \
  --out NEW_REPORT.json
```

[Bounded BBH](quoted-schedule-pooled-transfer-bounded-bbh-v1.json) · [Bounded LMentry](quoted-schedule-pooled-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](quoted-schedule-pooled-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](quoted-schedule-pooled-transfer-four-case-mmlu-v1.json) · [Tie BBH](quoted-schedule-pooled-transfer-tie-bbh-v1.json) · [Tie LMentry](quoted-schedule-pooled-transfer-tie-lmentry-v1.json) · [Additional MMLU](quoted-schedule-pooled-transfer-additional-mmlu-v1.json)

Nineteen targeted tests passed. Two replays per cohort matched byte for byte with DNS and outbound sockets blocked. A separate replay verified all 64 directions' calibration selections, prices and local floors. The study covered 1,024 audit episodes and issued zero provider requests. Storage Guard measured 9.8 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
