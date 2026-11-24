# Where CPO missed qualified challengers on language tasks

The [language transfer](reinvested-halving-language-transfer.md) found that the four-challenger, 19-read CPO setting trailed the strongest affordable task-tuned simple schedule in all seven cohorts. This audit reproduces both endpoints and every original CPO paid trajectory across the same 2,048 three-cycle episodes. It then replaces one more leading CPO cycle with the simple control at a time. Each replacement compares the two decisions on the same incumbent and follows both decisions with the remaining CPO cycles. The score and cost differences sum to the original gap. [Attribution runner](../benchmarks/reinvested_halving_gap_attribution.py)

## Source of the gap

| Simple control's action relative to CPO | Cycle replacements | Net final passes gained | Lookup change |
| --- | ---: | ---: | ---: |
| Promoted a challenger outside CPO's roster | 114 | +614 | +279 |
| Promoted a challenger CPO dropped on row one | 57 | +162 | +380 |
| Promoted a challenger CPO dropped on row two | 25 | +68 | +190 |
| Promoted the last survivor without a strict full-panel validation gain | 73 | +48 | +513 |
| Retained the incumbent while CPO promoted | 155 | −38 | −1,143 |
| Deployed the same prompt | 5,720 | 0 | −2,670 |
| **Total** | **6,144** | **+854** | **−2,451** |

Roster coverage accounted for 614 of the 854 net passes, including 510 of the 596-pass bounded LMentry gap. Of the 114 excluded challengers that simple search promoted, 100 would have strictly improved the complete CPO validation panel. Another 74 of the 82 challengers dropped on rows one and two would have done so. CPO rejected its own nominee in 1,135 replacements. In 1,111 of those, both policies deployed the same prompt. These figures describe replacements along the simple-control prefix, with the remaining CPO cycles held fixed. Reordering the replacements could change the allocation of gains across categories.

## Preserve the stronger schedule and skip settled reads

The new `run_quoted_shared_validation_cycle` supports both uniform search and successive halving. It prices the complete eager prefix before opening search. Reading the incumbent on that prefix first gives a fixed threshold. A challenger can be skipped once its best remaining score cannot beat the incumbent or reach the exact next shortlist. With stable boolean replies, every kept candidate has its actual prefix score, and the nominee and qualification match the eager schedule. Critical validation panels use the strict two-sided screen. [Cycle implementation](../cpo/quoted_shared_validation_cycle.py)

Call the cycle with the ordered candidate roster, disjoint validation and qualification rows, and the existing evaluator and qualification callbacks. Set `schedule='uniform'` or `schedule='successive-halving'`, and pass the original search allowance as `metric_limit`. To compare a narrower roster, pass the desired prefix of candidates. [Usage and exhaustive parity tests](../tests/unit/test_quoted_shared_validation_cycle.py)

| Cohort | Final passes | Eager lookups | Quoted lookups | Task-tuned GEPA upper bound at quoted price |
| --- | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,433 | 19,785 | 15,160 | 6,361 |
| Bounded LMentry | 6,547 | 20,026 | 14,719 | 5,931 |
| Bounded MMLU | 7,739 | 11,010 | 8,097 | 7,717 |
| Four-case MMLU | 22,413 | 15,793 | 11,735 | 22,369 |
| Tie BBH | 2,183 | 13,963 | 12,475 | 2,126 |
| Tie LMentry | 1,013 | 6,884 | 5,611 | 919 |
| Additional MMLU | 7,411 | 10,021 | 8,128 | 7,399 |

Quoted validation saved 21,557 lookups out of 97,482, a 22.1% reduction. Every nomination and qualification decision matched the eager schedule in all archived cycles. At the lower realized prices, all seven score totals exceeded the published task-tuned GEPA upper bounds. These bounds come from the original split-safe full-grid sweep. The runner replays the native attainers feasible at the lower prices. The width, schedule and cap for each task came from the earlier search over that task's archived holdout. A policy that selects those settings before seeing evaluation outcomes still needs verification.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview the seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.reinvested_halving_gap_attribution \
  --cohort bounded-LMentry \
  --execute 8c8bcb89cd57863a3262d0c3db1ad02a4ae732eae14d6ff4f81a1f3c3caab072 \
  --out NEW_REPORT.json
```

[Bounded BBH](reinvested-halving-gap-attribution-bounded-bbh-v1.json) · [Bounded LMentry](reinvested-halving-gap-attribution-bounded-lmentry-v1.json) · [Bounded MMLU](reinvested-halving-gap-attribution-bounded-mmlu-v1.json) · [Four-case MMLU](reinvested-halving-gap-attribution-four-case-mmlu-v1.json) · [Tie BBH](reinvested-halving-gap-attribution-tie-bbh-v1.json) · [Tie LMentry](reinvested-halving-gap-attribution-tie-lmentry-v1.json) · [Additional MMLU](reinvested-halving-gap-attribution-additional-mmlu-v1.json)

Fourteen targeted tests passed, including eager parity on all 4,096 three-row boolean matrices at five caps for both schedules. Two replays per cohort matched byte for byte with DNS and outbound sockets blocked. The study issued zero provider requests. Storage Guard measured 10.0 GiB free. The temporary source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
