# Choose a CPO episode schedule from paid opening training replies

The [language roster audit](language-roster-budget-frontier.md) found that, in hindsight, the same search menu gains 1,403 passes when choosing a setting per episode instead of per subject. This experiment tests an observable signal before opening search. It reads one or two cases from the first cycle's training panel. An incumbent probe uses the number of incumbent passes. A paired probe compares the same cases under the incumbent and the first ordered challenger, using only the sign of the paired gain. The chosen schedule runs for all three cycles. The probe is charged even when the table retains the incumbent. Training grades stay outside validation and independent qualification. [Probe](../cpo/episode_probe.py) · [Benchmark](../benchmarks/episode_training_probe_transfer.py)

The fit uses 70 discovery panels from 31 tasks, excluding all target tasks. The menu is the original quoted uniform and halving schedule menu, the bounded opening, the earlier router, and retention. It enumerates the state-to-schedule tables, counting probes and search against the bounded opening's actual discovery spend for each cohort. States supported by fewer than three discovery subjects retain. The no-probe control uses the same fit and budget with one constant setting.

## Discovery

| Setting | Discovery passes / lookups |
| --- | ---: |
| Bounded opening and no-probe fit | 84,043 / 67,022 |
| One incumbent check | 83,981 / 63,609 |
| Two incumbent checks | 84,026 / 61,618 |
| One paired check | 83,887 / 55,519 |
| Two paired checks | 83,868 / 59,293 |

The two-incumbent-check rule retains after two passes, selects eight-challenger halving with a cap of 17 after one pass, and uses the bounded opening after two misses. Its three states have support from 30, 31 and 30 discovery subjects, respectively, in ascending pass-count order. All four probe fits use fewer lookups on discovery and score below the no-probe fit. The discovery fit keeps the bounded opening. [Frozen fit](episode-training-probe-fit-v1.json)

## Target replay

Cells show held-out passes and total paid lookups. The original bounded opening and the fitted no-probe control take the same actions. All probes are included in the realized lookup totals.

| Cohort | Bounded opening | One incumbent check | Two incumbent checks | One paired check | Two paired checks |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,347 / 13,421 | 6,326 / 12,069 | 6,335 / 13,212 | 6,355 / 12,578 | 6,338 / 12,501 |
| Bounded LMentry | 6,338 / 15,636 | 6,288 / 15,192 | 6,313 / 15,502 | 6,086 / 12,370 | 6,096 / 13,153 |
| Bounded MMLU | 7,719 / 6,554 | 7,714 / 5,989 | 7,721 / 5,275 | 7,712 / 5,653 | 7,707 / 6,178 |
| Four-case MMLU | 22,369 / 10,591 | 22,367 / 9,608 | 22,393 / 9,797 | 22,370 / 8,658 | 22,369 / 9,241 |
| Tie BBH | 2,145 / 12,521 | 2,142 / 11,856 | 2,131 / 13,165 | 2,096 / 10,353 | 2,113 / 10,057 |
| Tie LMentry | 992 / 6,971 | 993 / 6,665 | 991 / 7,042 | 898 / 5,310 | 884 / 5,401 |
| Additional MMLU | 7,398 / 6,354 | 7,398 / 6,071 | 7,396 / 5,600 | 7,397 / 5,339 | 7,398 / 5,810 |
| **Pooled** | **53,308 / 72,048** | **53,228 / 67,450** | **53,280 / 69,593** | **52,914 / 60,261** | **52,905 / 62,341** |

Two incumbent checks skip search in 558 of 2,048 episodes. They gain 24 passes and save 794 lookups on four-case MMLU, with a paired 95% range of +7 to +41 passes. On bounded MMLU they save 1,279 lookups and gain two passes, with a range of −11 to +15. They lose 28 passes across the replay, save 2,455 lookups, and exceed the bounded opening's budget on tie BBH and tie LMentry. Pooled counts describe the archive because cohorts reuse tasks.

Both paired rules save more lookups but lose more than 240 passes on bounded LMentry. Two incumbent checks exceed the task-tuned GEPA upper bound in four cohorts at their realized spend. The task-tuned simple point score stays higher in all seven. The two incumbent checks provide a measurable search admission signal on four-case MMLU. The discovery fit keeps the bounded opening, and fresh live superiority remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview a seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.episode_training_probe_transfer --fit \
  --execute 72800e9a554fa3e67ab9d0f873645f90c8b3e1dd2c3799e5060eac8e557221f7 \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.episode_training_probe_transfer \
  --cohort four-case-MMLU --fitted NEW_FIT.json \
  --execute 4b578b2250998d3abdda00a7eb87e62c05cae35ce7b200d9d5630db49cefcf4a \
  --out NEW_REPORT.json
```

[Bounded BBH](episode-training-probe-transfer-bounded-bbh-v1.json) · [Bounded LMentry](episode-training-probe-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](episode-training-probe-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](episode-training-probe-transfer-four-case-mmlu-v1.json) · [Tie BBH](episode-training-probe-transfer-tie-bbh-v1.json) · [Tie LMentry](episode-training-probe-transfer-tie-lmentry-v1.json) · [Additional MMLU](episode-training-probe-transfer-additional-mmlu-v1.json)

Thirty-two targeted tests passed. Duplicate fits and target replays matched byte for byte with DNS and outbound sockets blocked. Source and baseline trajectory hashes reproduced. The receipts include each method's training lookup total and the paired score comparisons at realized cost. No provider requests were made. Storage Guard measured 9.7 GiB free. The source export, dependency overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_episode_training_probe.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
