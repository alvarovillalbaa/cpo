# Fit search choices from paid incumbent evidence

The frozen transfer showed that the same search breadth could help one archived cohort and waste lookups in another. This replay fits a search rule on the 134 discovery panels, then applies it to the 56 separate model and task pairs from the frozen transfer. The fit uses only the discovery archive's outcomes. The transfer panels and their scores stay outside fitting. The transfer includes tasks previously studied on other checkpoints. [Discovery results](paired-repair-race.md) · [Frozen transfer bank](shared-validation-archive-transfer.md) · [Runner](../benchmarks/paid_prefix_archive_routing.py)

Every policy starts with the ordinary independent incumbent precheck. A passing incumbent on all four cases closes the search. If a miss opens it, the fitted static policy uses one action for every trial. The prefix policy uses the position of that first miss. The prefix-and-validation policy also buys the incumbent's first validation reply. The chosen screen reuses that reply, and choosing to retain the start still pays for it. Each fitted action can retain the incumbent, run certified wide, run incumbent-first, use single repair, or use preserve one. The selected finalist must still pass exact independent qualification.

The fit maximizes aggregate discovery holdout passes under the same 65,728-lookup discovery limit for all three choices. The fitted static choice is incumbent-first. The prefix policy fitted 109,786 passes / 65,588 lookups and the prefix-and-validation policy fitted 109,921 / 65,268. The static fit scored 109,706 / 65,728. These are training scores. The frozen action table and discovery state counts are in the [fit receipt](paid-prefix-archive-routing-fit-v1.json).

## Frozen transfer

Each cell gives held-out passes / paid lookups at one qualification gain. The last column uses the best subject-tuned split-safe GEPA setting within the prefix-and-validation budget.

| Cohort | Fitted static | Qualification prefix | Prefix and validation | Subject-tuned GEPA |
| --- | ---: | ---: | ---: | ---: |
| [Bounded BBH](paid-prefix-archive-routing-bounded-bbh-v1.json) | 6,254 / 6,451 | 6,264 / 5,744 | 6,270 / 5,789 | 6,296 / 5,749 |
| [Bounded LMentry](paid-prefix-archive-routing-bounded-lmentry-v1.json) | 5,514 / 6,974 | 5,488 / 6,694 | 5,530 / 6,634 | 5,213 / 6,613 |
| [Bounded MMLU](paid-prefix-archive-routing-bounded-mmlu-v1.json) | 7,705 / 3,187 | 7,715 / 3,205 | 7,716 / 3,114 | 7,716 / 2,026 |
| [Four-case MMLU](paid-prefix-archive-routing-four-case-mmlu-v1.json) | 22,345 / 4,659 | 22,358 / 4,759 | 22,365 / 4,738 | 22,348 / 0 |
| [Tie BBH](paid-prefix-archive-routing-tie-bbh-v1.json) | 2,053 / 4,972 | 2,072 / 4,889 | 2,066 / 4,891 | 2,073 / 4,874 |
| [Tie LMentry](paid-prefix-archive-routing-tie-lmentry-v1.json) | 796 / 2,579 | 813 / 2,697 | 822 / 2,673 | 815 / 2,008 |

The prefix-and-validation policy scored 102 more passes and used 983 fewer lookups in the pooled descriptive totals versus fitted static. It gained passes in all six cohorts and saved lookups in four. The transfers reuse some tasks across checkpoints and some across archives, so the pooled totals have no reported confidence interval. The prefix-only fit gained 43 passes and saved 834 lookups versus fitted static across the six cohorts.

The primary missed the joint gate in every cohort. The gate requires a positive paired lower endpoint against fitted static, no additional lookups versus static, a positive lower endpoint against the best affordable common GEPA setting, and a higher point score than the subject-tuned ceiling. On bounded LMentry the primary gained 317 passes versus subject-tuned GEPA, with a case-resampled 95% range of +243 to +389 holding the native schedule fixed. Its range against fitted static was −7 to +38, at 340 fewer lookups. On four-case MMLU the native ceiling was simply retaining the start. The primary gained 17 passes against retention with a range of +2 to +33 and used 4,738 lookups. Its 20-pass gain over fitted static used 79 more lookups. The tie LMentry gain over static also used more lookups. The router remains benchmark-only. Fresh-model performance remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.paid_prefix_archive_routing --fit NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.paid_prefix_archive_routing \
  --fitted NEW_FIT.json --cohort bounded-LMentry
PYTHONHASHSEED=0 python -B -m benchmarks.paid_prefix_archive_routing \
  --fitted NEW_FIT.json --cohort bounded-LMentry \
  --execute 21bf7bf079d1aff945ffa7093b49cdf76baf88b4017eaca9ec35669c5f6b03d5 \
  --out NEW_REPORT.json
```

Two independent discovery fits and two source replays per cohort matched byte for byte with DNS and sockets blocked. Every original CPO transfer control path and the complete native GEPA subject totals reproduced before repricing. Twenty-seven targeted tests passed, including checks that the router sees only paid signal and charges the optional probe once. Storage Guard measured 10.5 GiB free at preflight. The source export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_paid_prefix_archive_routing.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
