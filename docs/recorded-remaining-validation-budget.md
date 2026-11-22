# Test strict certificates with the remaining validation budget

The exact race reserves a complete validation panel before it opens a challenger. This replay tests whether the last few lookups can prove an improvement when they cannot fund a complete panel. It keeps the exact race and its roster order. If fewer than six lookups remain, it considers previously unread challengers. It can replace the exact leader only once the paid pass count exceeds the leader’s score and preserves the original incumbent's critical passes. The chosen nominee then faces the same independent qualification. [Continuation comparison](recorded-paid-validation-continuation.md) · [Replay runner](../benchmarks/recorded_remaining_validation_budget.py)

The two candidate settings use the original cap of 13 and the fixed cap of 32 identified in the continuation comparison. The experiment reuses those 896 archived MMLU trials. The primary cap-13 policy needs a positive point margin and a nonnegative lower paired bound against the best affordable fixed CPO setting, native GEPA setting, or retained starts. Each paired draw resamples cases within subjects and reselects the control at the observed search-plus-qualification cost.

| Search cap | Trials with extra validation reads | Additional lookups | Nominations changed | Held-out passes / total lookups |
| --- | ---: | ---: | ---: | ---: |
| 13 | 385 | 408 | 0 | 26,610 / 10,004 |
| 32 | 180 | 354 | 0 | 26,664 / 20,318 |

The cap-13 policy missed the gate. Retaining the starts led by 15 passes and cost zero lookups. The paired range against the strongest affordable control was −41 to 0. At cap 32, the original exact policy matched the new policy’s score at 19,964 lookups. [Full results and paired comparisons](recorded-remaining-validation-budget-results-v1.json)

## What the remaining budget could fund

The diagnostic fixes the original search prefix and gives the chooser perfect knowledge of unread validation, qualification, and holdout outcomes. It can retain the original deployment or choose any previously unread candidate whose shortest validation certificate fits the remaining allowance, preserves required cases, and passes independent qualification. This gives an optimistic ceiling for changing only the end of the race.

| Search cap | Trials with a fundable strict certificate | Trials with a fundable certificate that also qualifies | Extra held-out passes with hindsight |
| --- | ---: | ---: | ---: |
| 13 | 147 | 39 | 75 |
| 32 | 15 | 2 | 3 |

Cap 13 had room for a different read order or candidate choice, even though the tested order found zero certificates. At cap 32, perfect knowledge of the remaining replies could recover only three passes on these trials. A substantial gain at that cap would require changing the earlier search or the candidate pool. Fresh-model performance remains unverified.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_remaining_validation_budget
python -B -m benchmarks.recorded_remaining_validation_budget \
  --execute 3c3aae464d313d0ed74529fd549c6ad5ea5f20e09ac448b0a3a500da74e5cc06 \
  --out NEW_REPORT.json
```

Two clean-export runs with DNS and sockets blocked matched byte for byte at SHA-256 `e42ac62f5f0777c0fd8969a880c405277af3631fdd0f141dc63a3213fd02caa7`. Thirty-one targeted tests passed. An independent check enumerated the possible terminal read sets across both caps and all 896 trials. The final seal adds the hindsight diagnostic and reproduces the first run’s paths, costs, and grades. The CLI rejected the preceding seal. Storage Guard measured 3.0 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Targeted tests](../tests/unit/test_recorded_remaining_validation_budget.py)
