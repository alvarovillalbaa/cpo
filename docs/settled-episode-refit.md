# Refit CPO episode schedules after lowering uniform validation cost

The [case-order replay](ordered-uniform-transfer.md) showed that reading incumbent misses first lowers uniform lookup cost at the tested depths. This refit applies that order to every funded uniform case set in the existing episode menu. Halving keeps the earlier perfect-challenger shortcut. The replay verifies that each repriced uniform cycle preserves its original nomination, qualification receipt, and deployment. [Replay and fitter](../benchmarks/settled_episode_refit.py)

The fitter compares a constant setting, a full two-incumbent-probe table, and a table that can stop buying probes early. The settled probe calls `choose_schedule` from `cpo.settled_episode_schedule`. After each paid reply it checks the possible final pass counts. If every remaining count chooses the same schedule, it returns that schedule immediately. A constant table buys zero probes. The fitter charges exact early-stop costs, and target replay checks both the chosen action and the recorded prefix against the full-probe version of the same table. [Probe implementation](../cpo/settled_episode_schedule.py)

## Discovery

The original 70 panels from 31 discovery tasks exclude the target subjects. Every discovery cohort keeps its original bounded opening budget. The fitter reproduces the prior full-probe table and costs before using the new prices.

| Fit | Discovery passes / lookups | Feasible tables |
| --- | ---: | ---: |
| Constant setting | 84,043 / 67,022 | 9 |
| Full two-probe table | 84,046 / 64,938 | 2,128 |
| Settled two-probe table | 84,046 / 64,938 | 2,150 |

The two probe fits choose the same table. Two misses use the bounded opening. One pass uses eight-candidate, two-row uniform validation with misses first. Two passes use four-candidate halving with a cap of six. All three actions differ, so the selected table buys both probes in every episode. Early stopping makes 22 additional tables feasible. The change in the selected policy comes from the new uniform prices. [Frozen fit](settled-episode-refit-v1.json)

## Target results

Cells show held-out passes and realized lookups, with all training probes included. The refit has the same score, spend and schedule choices under the full and settled probe modes. Native and simple controls are priced at the refit's actual lookups.

| Cohort | Bounded opening | Previous two-probe fit | New two-probe fit | Native GEPA upper bound | Task-tuned simple |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,347 / 13,421 | 6,335 / 12,906 | 6,338 / 12,340 | 6,350 | 6,390 |
| Bounded LMentry | 6,338 / 15,636 | 6,313 / 15,351 | 6,390 / 15,146 | 5,931 | 6,302 |
| Bounded MMLU | 7,719 / 6,554 | 7,721 / 5,170 | 7,715 / 5,956 | 7,717 | 7,728 |
| Four-case MMLU | 22,369 / 10,591 | 22,393 / 9,724 | 22,366 / 10,522 | 22,369 | 22,409 |
| Tie BBH | 2,145 / 12,521 | 2,131 / 13,123 | 2,138 / 12,520 | 2,126 | 2,169 |
| Tie LMentry | 992 / 6,971 | 991 / 7,030 | 1,004 / 6,863 | 919 | 1,011 |
| Additional MMLU | 7,398 / 6,354 | 7,396 / 5,526 | 7,397 / 6,211 | 7,399 | 7,405 |
| **Pooled** | **53,308 / 72,048** | **53,280 / 68,830** | **53,348 / 69,558** | — | — |

Across 2,048 archived episodes, the refit adds 40 passes and saves 2,490 lookups relative to the bounded opening. It fits every cohort budget. Relative to the previous two-probe fit, it adds 68 passes and uses 728 more lookups. Pooled counts describe the archived mix because tasks can recur across cohorts.

Bounded LMentry gains 52 passes and saves 490 lookups relative to the bounded opening, with a paired 95% range of +21 to +83 passes. The refit scores 88 more than the affordable task-tuned simple setting there, with a paired range of +29 to +146. Tie LMentry gains 12 passes and saves 108 lookups versus the bounded opening, with a range of +2 to +21. The refit exceeds the native GEPA upper bound in three cohorts and the task-tuned simple score in one. Four-case MMLU loses 27 passes versus the previous two-probe fit. Live quality remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview a seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.settled_episode_refit --fit \
  --execute c4226fa3e1ed64a6e11be0dcfd346a5d811925d12a4bf3d87148d4b57208c2be \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.settled_episode_refit \
  --cohort bounded-LMentry --fitted NEW_FIT.json \
  --execute bfa32c76084faf8fba80fbfa7d60641240b97aad5e698cb77d619d506d58d220 \
  --out NEW_REPORT.json
```

[Bounded BBH](settled-episode-refit-transfer-bounded-bbh-v1.json) · [Bounded LMentry](settled-episode-refit-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](settled-episode-refit-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](settled-episode-refit-transfer-four-case-mmlu-v1.json) · [Tie BBH](settled-episode-refit-transfer-tie-bbh-v1.json) · [Tie LMentry](settled-episode-refit-transfer-tie-lmentry-v1.json) · [Additional MMLU](settled-episode-refit-transfer-additional-mmlu-v1.json)

Fifty-five targeted tests passed. They include exhaustive probes and action tables for up to four binary cases, plus brute-force checks of the budget-constrained two-probe fitter. Duplicate fits and target replays matched byte for byte with DNS and outbound sockets blocked. No provider requests were made. Storage Guard measured 9.7 GiB free. The source export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_settled_episode_schedule.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
