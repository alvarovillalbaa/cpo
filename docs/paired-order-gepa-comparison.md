# Compare CPO and GEPA with the same qualification order

The paired-order CPO cycle uses a paid reply on one side of a qualification case to estimate the other side. This study gives the same scheduler to sequential and batched GEPA at every integer search cap from 6 through 180. It applies to all three published qualification wrappers and keeps the original variants available. The replay holds each incumbent precheck, search, nominee, deployment, and held-out grade fixed. The paid qualification order and cost can change. [CPO cycle](paired-order-certificate-cycle.md) · [Original GEPA settings](deferred-certificate-subject-ceiling.md)

The analysis prices the expanded control menu at the realized paired-order CPO budget for each margin and cohort. It records the best affordable common setting and the exact subject-tuned ceiling. Subject tuning chooses a setting using held-out grades for each subject, shared across both checkpoints and all seeds. All chosen subjects share one total budget. [Replay driver](../benchmarks/paired_order_gepa_comparison.py)

## Results

The table compares CPO with the strongest subject-tuned GEPA schedule drawn from both qualification orders. Each GEPA schedule fits the lookup budget used by its CPO counterpart. [Exact costs, controls, and attaining schedules](paired-order-gepa-comparison-results-v1.json)

| Cohort | One-gain CPO passes / lookups | GEPA passes / lookups | CPO margin | Two-gain CPO passes / lookups | GEPA passes / lookups | CPO margin |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BBH, original | 9,548 / 16,083 | 9,646 / 16,077 | −98 | 8,998 / 15,062 | 9,601 / 15,039 | −603 |
| BBH, other checkpoints on previously studied tasks | 4,843 / 9,059 | 4,917 / 8,946 | −74 | 4,790 / 8,403 | 4,906 / 8,283 | −116 |
| BBH, causal judgment | 591 / 1,118 | 590 / 956 | +1 | 569 / 1,007 | 590 / 956 | −21 |
| LMentry, original | 5,650 / 8,751 | 5,417 / 8,740 | +233 | 5,192 / 8,368 | 5,388 / 8,348 | −196 |
| LMentry, other checkpoints on previously studied tasks | 5,307 / 6,151 | 5,117 / 6,084 | +190 | 4,963 / 5,363 | 5,016 / 5,337 | −53 |
| LMentry, ends-with-word | 263 / 1,168 | 233 / 1,000 | +30 | 256 / 1,184 | 233 / 1,000 | +23 |
| Disjoint MMLU | 56,094 / 12,792 | 56,116 / 11,534 | −22 | 56,094 / 8,962 | 56,112 / 8,913 | −18 |
| Earlier MMLU | 26,619 / 13,583 | 26,654 / 10,802 | −35 | 26,630 / 9,751 | 26,653 / 8,941 | −23 |

Same-case ordering made 6,492 of 8,400 GEPA cohort settings cheaper, made 658 dearer, and tied 1,250. The count includes each cap even when several caps share a realized path. At the paired-order CPO budgets, the expanded menu raised the attainable GEPA score by two passes on original BBH at one gain. The other ceilings kept the same scores and often used fewer lookups.

One-gain CPO stayed ahead on all three LMentry groups after GEPA received the same scheduler. The previously studied BBH and both MMLU groups still favored subject-tuned GEPA. These margins use fixed archived candidate rosters. Fresh-model performance remains unverified.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. [Pinned wheel requirement](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.paired_order_gepa_comparison
PYTHONHASHSEED=0 python -B -m benchmarks.paired_order_gepa_comparison \
  --execute 90de1ef71b10625a67fe9b5427dbff456ba69aa9e00fb32234b970a74493dfea \
  --out NEW_REPORT.json
```

Two clean-source runs matched byte for byte at SHA-256 `2b6ac95cfae9361a380aa9eb2a38858e8b03c8a7dfebd11268736ff537b63fd8`. They verified all 8,400 original GEPA cost and score totals, all 8,400 paired counterparts, and the earlier subject schedules. A separate verification used 11,712 direct schedule-setting executions to check the selected common settings and every contribution to the new subject-tuned scores. All 14 targeted tests and four subtests passed. DNS and outbound sockets were blocked, and the CLI rejected the predecessor seal before creating a report. Storage Guard measured 3.2 GiB free. The export, GEPA wheel overlay, and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [GEPA parity tests](../tests/unit/test_paired_order_gepa_comparison.py)
